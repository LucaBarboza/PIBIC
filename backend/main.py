import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile
from concurrent.futures import ThreadPoolExecutor
from fastapi.middleware.cors import CORSMiddleware
import uuid
import re
import io
import shutil
import firebase_admin
from firebase_admin import credentials, firestore
from pydantic import BaseModel
import gerador_conteudo
import orquestrador_editorial
import agente_validador_latex
import agente_extrator
from macro_roteirista import MacroRoteirista

import json
from logger_agentes import AgentLogger

# Diretório para armazenamento seguro de uploads de PDFs (100% nativo)
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "data_local", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def resolver_caminho_pdf(id_ou_ref: str) -> Optional[str]:
    """
    Localiza o caminho em disco de um PDF enviado pelo professor.
    Aceita:
    - Marcador: [PDF_ID:...] ou [PDF_SALVO_ID:...]
    - ID do arquivo salvo em data_local/uploads
    - Caminho de arquivo absoluto existente
    """
    if not id_ou_ref or not isinstance(id_ou_ref, str):
        return None
    s = id_ou_ref.strip()
    if not s:
        return None

    if s.startswith("[PDF_ID:") and s.endswith("]"):
        arq_id = s[len("[PDF_ID:"): -1].strip()
        caminho = os.path.join(UPLOAD_DIR, arq_id)
        if os.path.exists(caminho):
            return caminho
    if s.startswith("[PDF_SALVO_ID:") and s.endswith("]"):
        arq_id = s[len("[PDF_SALVO_ID:"): -1].strip()
        caminho = os.path.join(UPLOAD_DIR, arq_id)
        if os.path.exists(caminho):
            return caminho

    caminho_direto = os.path.join(UPLOAD_DIR, s)
    if os.path.exists(caminho_direto) and os.path.isfile(caminho_direto):
        return caminho_direto

    if os.path.isabs(s) and os.path.exists(s) and os.path.isfile(s):
        return s

    return None

def _parse_firebase_credentials(raw_val: str) -> dict:
    if not raw_val:
        raise ValueError("Credenciais vazias")
    s = raw_val.strip()
    if s.startswith("FIREBASE_CREDENTIALS="):
        s = s[len("FIREBASE_CREDENTIALS="):].strip()
    if s.startswith("'") and s.endswith("'"):
        s = s[1:-1].strip()
    elif s.startswith('"') and s.endswith('"') and not s.startswith('{"'):
        s = s[1:-1].strip()
    
    # 1. Tenta JSON direto
    try:
        data = json.loads(s)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
        
    # 2. Tenta Base64
    try:
        import base64
        decoded = base64.b64decode(s).decode('utf-8').strip()
        data = json.loads(decoded)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
        
    # 3. Tenta corrigir newlines escapados
    try:
        fixed_s = s.replace('\\\\n', '\\n')
        data = json.loads(fixed_s)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
        
    raise ValueError(f"Formato de credencial inválido (tamanho: {len(s)})")

# Inicialização do Firebase Admin
firebase_error = None
try:
    cred = None
    if os.environ.get("FIREBASE_CREDENTIALS_BASE64"):
        cred_dict = _parse_firebase_credentials(os.environ.get("FIREBASE_CREDENTIALS_BASE64"))
        cred = credentials.Certificate(cred_dict)
    elif os.environ.get("FIREBASE_CREDENTIALS"):
        cred_dict = _parse_firebase_credentials(os.environ.get("FIREBASE_CREDENTIALS"))
        cred = credentials.Certificate(cred_dict)
    else:
        cred_path = os.path.join(os.path.dirname(__file__), "serviceAccountKey.json")
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            raise FileNotFoundError("Credenciais (arquivo ou ENV) não encontradas.")
            
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(cred)
        
    db = firestore.client()
    print("[OK] Firebase Admin inicializado com sucesso.")
except Exception as e:
    firebase_error = str(e)
    print(f"[ERRO] Falha ao inicializar o Firebase: {e}")
    db = None

app = FastAPI(title="Plataforma de Aulas UFBA - API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from typing import Optional, List

class AulaManual(BaseModel):
    titulo: str
    descricao: str
    texto_base_pdf: Optional[str] = ""
    texto_base_notacoes: Optional[str] = ""
    arquivo_base_id: Optional[str] = ""
    arquivo_notacoes_id: Optional[str] = ""
    nome_arquivo: Optional[str] = ""
    nome_arquivo_notacoes: Optional[str] = ""
    gerar_exercicios: bool = True
    gerar_simulador: bool = False

class SemestreRequest(BaseModel):
    id_sala: str
    id_disciplina: str
    modelo_llm: str = "2.5"
    modo: str = "inteligente" # "inteligente" ou "manual"
    instrucoes_personalizadas: str = ""
    max_aulas: int = 30 # Usado apenas se tipo_carga_horaria == padrao_30
    limite_execucao: Optional[int] = None # Limita quantas aulas serão passadas para os micro agentes gerarem o conteúdo. None = Todas.
    tipo_carga_horaria: str = "padrao_30" # "padrao_30", "auto_ementa" ou "manual"
    permitir_aprofundamento: bool = False
    tipo_crie_seu_jeito: str = "bloco_a_bloco"
    arquivo_global_pdf: str = ""
    aulas_manuais: Optional[List[AulaManual]] = []

import time
from storage import StorageManager
storage = StorageManager(db=db)

def log_debug(sala_id, msg):
    print(f"[{sala_id}] {msg}")
    try:
        storage.update_classroom(sala_id, {
            "debug_logs": firestore.ArrayUnion([f"{time.strftime('%H:%M:%S')} - {msg}"]) if db else [f"{time.strftime('%H:%M:%S')} - {msg}"]
        })
    except Exception:
        pass

def obter_ementa_texto(id_disciplina: str):
    """Busca ementa no Firestore com fallback para arquivos TXT locais da pasta ementas/"""
    disc_data = storage.get_disciplina(id_disciplina)
    if disc_data and disc_data.get("ementa_texto"):
        return disc_data["ementa_texto"], disc_data.get("nome", id_disciplina)

    ementas_dir = os.path.join(os.path.dirname(__file__), "ementas")
    if os.path.exists(ementas_dir):
        for fname in os.listdir(ementas_dir):
            if fname.lower().startswith(id_disciplina.lower()) and fname.endswith(".txt"):
                try:
                    fpath = os.path.join(ementas_dir, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        texto = f.read().strip()
                        if texto:
                            print(f"[FALLBACK] Ementa da disciplina {id_disciplina} carregada direto de: {fname}")
                            return texto, id_disciplina
                except Exception as e:
                    print(f"[ERRO] Falha ao ler ementa TXT local {fname}: {e}")

    return "", id_disciplina

def processar_semestre_background(req: SemestreRequest):
    print(f"[BACKGROUND] Iniciando orquestração do semestre para a sala: {req.id_sala}")
    try:
        # 1. Recuperar ementa (Firestore ou Fallback PDF)
        ementa_texto, nome_disciplina = obter_ementa_texto(req.id_disciplina)
        if not ementa_texto and req.modo != "manual" and not req.arquivo_global_pdf:
            storage.update_classroom(req.id_sala, {"status": "erro_disciplina_nao_encontrada"})
            print(f"[ERRO] Ementa para disciplina {req.id_disciplina} não encontrada.")
            return
        
        cronograma = []
        
        if req.modo == "manual" or req.modo == "livre":
            if req.tipo_crie_seu_jeito == "bloco_a_bloco" and req.aulas_manuais:
                log_debug(req.id_sala, "Modo Manual: Utilizando blocos fornecidos pelo professor.")
                storage.update_classroom(req.id_sala, {"status": "processando_aulas_manuais"})
                for idx, aula_manual in enumerate(req.aulas_manuais):
                    cronograma.append({
                        "numero_aula": idx + 1,
                        "titulo": aula_manual.titulo,
                        "objetivo_principal": aula_manual.descricao,
                        "topicos_abordados": [aula_manual.descricao],
                        "texto_base_pdf": aula_manual.texto_base_pdf,
                        "texto_base_notacoes": aula_manual.texto_base_notacoes,
                        "arquivo_base_id": aula_manual.arquivo_base_id or "",
                        "arquivo_notacoes_id": aula_manual.arquivo_notacoes_id or "",
                        "nome_arquivo": aula_manual.nome_arquivo or "",
                        "nome_arquivo_notacoes": aula_manual.nome_arquivo_notacoes or "",
                        "gerar_exercicios": aula_manual.gerar_exercicios,
                        "gerar_simulador": aula_manual.gerar_simulador
                    })
            elif req.tipo_crie_seu_jeito == "automatico":
                print("[BACKGROUND] Modo Crie do Seu Jeito Automático: Usando PDF do professor como ementa.")
                storage.update_classroom(req.id_sala, {"status": "fatiando_ementa_pdf", "detalhe_progresso": "Extraindo ementa do PDF com IA multimodal..."})
                
                texto_global_ementa = req.arquivo_global_pdf
                caminho_global = resolver_caminho_pdf(req.arquivo_global_pdf)
                if caminho_global:
                    log_debug(req.id_sala, f"Extraindo ementa de PDF global '{os.path.basename(caminho_global)}' com IA multimodal...")
                    texto_extraido = agente_extrator.extrair_texto_base_pdf(
                        caminho_global,
                        tema_aula=f"Ementa Geral {nome_disciplina}",
                        modelo_llm=req.modelo_llm
                    )
                    if texto_extraido:
                        texto_global_ementa = texto_extraido

                macro = MacroRoteirista()
                diretrizes_macro = ""
                if req.instrucoes_personalizadas:
                    diretrizes_macro += f"Instruções e Persona do Professor:\n{req.instrucoes_personalizadas}\n\n"
                if texto_global_ementa and not texto_global_ementa.startswith("[PDF_ID:"):
                    diretrizes_macro += f"Material / PDF Completo do Professor:\n{texto_global_ementa}\n\n"
                
                cronograma = macro.gerar_cronograma(
                    ementa_texto=texto_global_ementa if (texto_global_ementa and not texto_global_ementa.startswith("[PDF_ID:")) else ementa_texto, 
                    instrucoes_personalizadas=req.instrucoes_personalizadas, 
                    diretrizes_texto=diretrizes_macro,
                    tipo_carga_horaria=req.tipo_carga_horaria,
                    permitir_aprofundamento=req.permitir_aprofundamento,
                    max_aulas=req.max_aulas
                )
                if not cronograma:
                    storage.update_classroom(req.id_sala, {"status": "erro_macro_roteirista"})
                    return
        else:
            # 2. Agente Macro Roteirista fatia o semestre
            log_debug(req.id_sala, "Acionando Macro Roteirista para fatiar o semestre...")
            storage.update_classroom(req.id_sala, {"status": "fatiando_ementa"})
            
            diretrizes_macro = ""
            if req.instrucoes_personalizadas:
                diretrizes_macro += f"Instruções e Persona do Professor:\n{req.instrucoes_personalizadas}\n\n"
            if req.arquivo_global_pdf:
                diretrizes_macro += f"Material / PDF Completo do Professor:\n{req.arquivo_global_pdf}\n\n"

            macro = MacroRoteirista()
            cronograma = macro.gerar_cronograma(
                ementa_texto=ementa_texto, 
                instrucoes_personalizadas=req.instrucoes_personalizadas, 
                diretrizes_texto=diretrizes_macro,
                tipo_carga_horaria=req.tipo_carga_horaria,
                permitir_aprofundamento=req.permitir_aprofundamento,
                max_aulas=req.max_aulas
            )
            
            if not cronograma:
                storage.update_classroom(req.id_sala, {"status": "erro_macro_roteirista"})
                return
            
        # Salva o cronograma mestre na sala
        storage.update_classroom(req.id_sala, {
            "cronograma_oficial": cronograma,
            "status": "gerando_aulas",
            "total_aulas": len(cronograma),
            "aulas_geradas": 0,
            "debug_logs": []
        })
        
        # 3. Loop: Agentes Micro geram as aulas individualmente
        limite = req.limite_execucao if req.limite_execucao is not None else len(cronograma)
        limite = min(limite, len(cronograma))
        print(f"[BACKGROUND] Gerando {limite} aulas na fábrica de conteúdo (cronograma total: {len(cronograma)})...")
        
        for idx, aula in enumerate(cronograma[:limite]):
            numero = aula.get("numero_aula", idx + 1)
            titulo = aula.get("titulo", "Aula")
            objetivo = aula.get("objetivo_principal", "")
            topicos = ", ".join(aula.get("topicos_abordados", []))
            
            # --- COLETA DE TÓPICOS PROIBIDOS ---
            topicos_proibidos_lista = []
            for futura_aula in cronograma[idx+1:]:
                topicos_proibidos_lista.extend(futura_aula.get("topicos_abordados", []))
            topicos_proibidos = ", ".join(topicos_proibidos_lista)
            
            # Constrói o "Tema Global" para a Fábrica
            tema_montado = f"Disciplina: {nome_disciplina}. Aula: {titulo}. Objetivo: {objetivo}. Tópicos: {topicos}"
            log_debug(req.id_sala, f"Gerando Aula {numero}: {titulo}...")
            
            # Pipeline de Redação
            diretrizes = f"Foque nestes tópicos: {topicos}. Adapte a profundidade para atingir este objetivo: {objetivo}. Use notação matemática rigorosa e seja didático."
            if topicos_proibidos:
                diretrizes += f"\nATENÇÃO ESTRITA - TÓPICOS PROIBIDOS: {topicos_proibidos}. Você NÃO PODE abordar NENHUM desses assuntos nesta aula, pois serão dados futuramente. Fique apenas nos seus tópicos."
            
            logger = AgentLogger(db, req.id_sala, numero)
            logger.log(f"Iniciando geracao da Aula {numero}", "info")

            from telemetry import TokenTracker
            tracker = TokenTracker(modo_llm=req.modelo_llm)

            # 1. Material de Apoio do Professor (Texto ou PDF processado por IA multimodal em background)
            material_apoio = ""
            material_ref = aula.get("arquivo_base_id") or aula.get("texto_base_pdf", "")
            caminho_mat_pdf = resolver_caminho_pdf(material_ref)
            if caminho_mat_pdf:
                nome_arq_pdf = aula.get("nome_arquivo") or os.path.basename(caminho_mat_pdf)
                log_debug(req.id_sala, f"Aula {numero}: Agente Extrator lendo PDF '{nome_arq_pdf}' com IA multimodal...")
                storage.update_classroom(req.id_sala, {"detalhe_progresso": f"Aula {numero}: Agente Extrator lendo PDF '{nome_arq_pdf}' com IA..."})
                material_apoio = agente_extrator.extrair_texto_base_pdf(
                    caminho_mat_pdf,
                    tema_aula=titulo,
                    logger=logger,
                    modelo_llm=req.modelo_llm,
                    tracker=tracker
                )
            elif aula.get("texto_base_pdf") and not str(aula.get("texto_base_pdf", "")).startswith("[PDF_ID:"):
                material_apoio = aula.get("texto_base_pdf", "")

            if material_apoio and material_apoio.strip():
                diretrizes += f"\nATENÇÃO ESTRITA - MATERIAL DE APOIO DO PROFESSOR: Baseie toda a estrutura desta aula, os exemplos, as explicações e o contexto exclusivamente ou prioritariamente no material a seguir fornecido pelo professor:\n\n{material_apoio}\n\n[FIM DO MATERIAL DO PROFESSOR]."

            # 2. Notações e Diretrizes do Professor (Texto ou PDF processado por IA multimodal em background)
            override_prompt_block = ""
            notacoes_ref = aula.get("arquivo_notacoes_id") or aula.get("texto_base_notacoes", "")
            caminho_notacoes_pdf = resolver_caminho_pdf(notacoes_ref)
            override_dict = None

            if caminho_notacoes_pdf:
                nome_arq_not = aula.get("nome_arquivo_notacoes") or os.path.basename(caminho_notacoes_pdf)
                log_debug(req.id_sala, f"Aula {numero}: Agente Extrator mapeando notações do PDF '{nome_arq_not}' com IA...")
                storage.update_classroom(req.id_sala, {"detalhe_progresso": f"Aula {numero}: Agente Extrator mapeando notações de PDF com IA..."})
                override_dict = agente_extrator.extrair_regras_override_pdf(
                    caminho_notacoes_pdf,
                    logger=logger,
                    modelo_llm=req.modelo_llm,
                    tracker=tracker
                )
            else:
                notacoes_raw = aula.get("texto_base_notacoes", "")
                if notacoes_raw and notacoes_raw.strip() and not str(notacoes_raw).startswith("[PDF_ID:"):
                    log_debug(req.id_sala, f"Aula {numero}: Extraindo notações e diretrizes específicas com Agente Extrator...")
                    override_dict = agente_extrator.extrair_regras_override(
                        notacoes_raw,
                        logger=logger,
                        modelo_llm=req.modelo_llm,
                        tracker=tracker
                    )

            if override_dict:
                override_prompt_block = agente_extrator.formatar_override_para_prompt(override_dict)
                diretrizes = f"{override_prompt_block}\n\n{diretrizes}"

            conteudo_bruto = gerador_conteudo.gerar_conteudo_aula(
                nome_professor="Professor UFBA",
                codigo_disciplina=req.id_disciplina,
                tema_solicitado=tema_montado,
                ementa_texto=ementa_texto,
                diretrizes_texto=diretrizes,
                logger=logger,
                modelo_llm=req.modelo_llm,
                tracker=tracker
            )
            
            if conteudo_bruto:
                conteudo_final = orquestrador_editorial.lapidar_conteudo_global(conteudo_bruto, logger=logger, modelo_llm=req.modelo_llm, tracker=tracker)
                if conteudo_final:
                    flag_exercicios = aula.get("gerar_exercicios", True)
                    flag_simulador = aula.get("gerar_simulador", True)
                    conteudo_final = rodar_agentes_paralelos(
                        conteudo_final,
                        titulo,
                        modelo_llm=req.modelo_llm,
                        diretrizes_override=override_prompt_block,
                        logger=logger,
                        flag_exercicios=flag_exercicios,
                        flag_simulador=flag_simulador,
                        tracker=tracker
                    )

                    # Valida LaTeX antes de salvar
                    storage.update_classroom(req.id_sala, {"detalhe_progresso": f"Aula {numero}: Agente Validador LaTeX (Fase Final)..."})
                    conteudo_final = agente_validador_latex.validar_e_corrigir_aula_completa(conteudo_final, logger=logger, modelo_llm=req.modelo_llm, tracker=tracker)

                    # Anexa telemetria e custo oficial de tokens
                    conteudo_final["telemetria_custo"] = tracker.obter_resumo()

                    # Salva a aula no Storage (Firestore e Local)
                    storage.save_aula(req.id_sala, numero, {
                        "numero_aula": numero,
                        "titulo": titulo,
                        "conteudo_json": conteudo_final,
                        "publicada": False
                    })
                else:
                    raise Exception(f"Falha na lapidação (orquestrador) para a aula {numero}")
            else:
                raise Exception(f"API do Gemini bloqueada ou falhou ao gerar o conteúdo bruto da aula {numero}. Verifique os logs.")
        
        # 4. Finalização
        storage.update_classroom(req.id_sala, {"status": "pronto"})
        print(f"[BACKGROUND] Semestre {req.id_sala} concluído com sucesso!")
        
    except Exception as e:
        print(f"[ERRO] Exceção no semestre background: {e}")
        storage.update_classroom(req.id_sala, {"status": f"erro: {str(e)}"})

@app.get("/health")
def health_check():
    return {
        "status": "ok", 
        "firebase": db is not None,
        "firebase_error": firebase_error,
        "env_firebase_set": bool(os.environ.get("FIREBASE_CREDENTIALS") or os.environ.get("FIREBASE_CREDENTIALS_BASE64")),
        "env_gemini_set": bool(os.environ.get("GEMINI_API_KEY"))
    }

@app.post("/api/gerar_semestre")
def gerar_semestre(req: SemestreRequest, background_tasks: BackgroundTasks):
    if not db:
        raise HTTPException(status_code=500, detail="Banco de dados não conectado")
    
    background_tasks.add_task(processar_semestre_background, req)
    
    return {"message": "Semestre em processamento", "sala": req.id_sala}

@app.post("/api/upload_pdf")
async def upload_pdf(
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None)
):
    """
    Upload 100% nativo e ultrarrápido (< 100ms) sem pypdf.
    Salva o arquivo binário em data_local/uploads.
    A extração do conteúdo com OCR, fórmulas em LaTeX e regras estruturadas
    é realizada pelo Agente Extrator com IA multimodal em background.
    """
    lista_arquivos = []
    if files:
        lista_arquivos.extend(files)
    if file:
        lista_arquivos.append(file)
        
    if not lista_arquivos:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    salvos = []
    for f in lista_arquivos:
        if not f.filename:
            continue
        nome_limpo = re.sub(r'[^a-zA-Z0-9_.-]', '_', f.filename)
        ext = os.path.splitext(nome_limpo)[1].lower()
        if ext != ".pdf":
            continue
            
        arquivo_id = f"{uuid.uuid4().hex[:12]}_{nome_limpo}"
        caminho_destino = os.path.join(UPLOAD_DIR, arquivo_id)
        
        try:
            with open(caminho_destino, "wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            tamanho = os.path.getsize(caminho_destino)
            if tamanho == 0:
                if os.path.exists(caminho_destino):
                    os.remove(caminho_destino)
                continue
                
            salvos.append({
                "id": arquivo_id,
                "nome": f.filename,
                "tamanho_bytes": tamanho,
                "caminho": caminho_destino
            })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo {f.filename}: {str(e)}")

    if not salvos:
        raise HTTPException(status_code=400, detail="Nenhum arquivo PDF válido foi enviado.")

    primeiro = salvos[0]
    return {
        "status": "sucesso",
        "arquivo_id": primeiro["id"],
        "nome_arquivo": primeiro["nome"],
        "texto_extraido": f"[PDF_ID:{primeiro['id']}]",
        "arquivos": salvos
    }

class EditarBlocoRequest(BaseModel):
    sala_id: str
    aula_id: str
    caminho_bloco: str # ex: "conteudo_json.paginas_conteudo.0.discussao_teorica_prosa"
    novo_conteudo: str
    prompt_ia: str = "" # Se vier preenchido, usa IA para editar


def rodar_agentes_paralelos(conteudo_final, titulo_aula, modelo_llm="hibrido", diretrizes_override=None, logger=None, flag_exercicios=True, flag_simulador=True, tracker=None):
    import agente_exercicios
    import agente_simulador
    
    def task_exercicios():
        return agente_exercicios.gerar_caderno_exercicios(
            conteudo_final, 
            logger=logger, 
            modelo_llm=modelo_llm, 
            diretrizes_override=diretrizes_override,
            tracker=tracker
        )
        
    def task_simulador(idx_pag, nome_sim):
        sub_idx_int = int(idx_pag) - 1 if str(idx_pag).isdigit() else 0
        sub_info = ""
        paginas = conteudo_final.get("paginas_conteudo", [])
        if 0 <= sub_idx_int < len(paginas):
            pag = paginas[sub_idx_int]
            sub_info = f"Subtópico: {pag.get('titulo_subtopico', '')}\nTeoria/Conceito: {pag.get('discussao_teorica_prosa', '')[:1000]}\nFórmulas: {pag.get('formalismo_latex', 'N/A')}"

        html = agente_simulador.gerar_simulador_html(
            tema_aula=titulo_aula, 
            nome_simulador=nome_sim, 
            contexto_subtopico=sub_info,
            logger=logger, 
            modelo_llm=modelo_llm, 
            tracker=tracker
        )
        if html:
            return {"indice_pagina": str(idx_pag), "nome_simulador": nome_sim, "codigo_html_gerado": html}
        return None

    tasks_simuladores = []
    if flag_simulador:
        # 1. Tenta obter do campo simuladores_da_aula (gerado pelo Orquestrador)
        sims_orquestrador = conteudo_final.get("simuladores_da_aula", [])
        if sims_orquestrador:
            for s in sims_orquestrador:
                if isinstance(s, dict):
                    idx = s.get("indice_pagina", "1")
                    nome = s.get("nome_simulador")
                    if nome and str(nome).strip():
                        tasks_simuladores.append((idx, str(nome)))
                        
        # 2. Fallback: Se não encontrou no Orquestrador, busca em paginas_conteudo
        if not tasks_simuladores:
            for i, pag in enumerate(conteudo_final.get("paginas_conteudo", [])):
                if isinstance(pag, dict):
                    rec = pag.get("simulador_interativo_recomendado") or pag.get("simuladores_interativos_recomendados")
                    if isinstance(rec, list):
                        for item in rec:
                            if item and str(item).strip():
                                tasks_simuladores.append((str(i + 1), str(item)))
                    elif rec and str(rec).lower() != "none" and str(rec).strip() != "":
                        tasks_simuladores.append((str(i + 1), str(rec)))

        # 3. Fallback Final Garantido: Se ainda não tiver simulador e flag_simulador for True, cria para a página 1
        if not tasks_simuladores and conteudo_final.get("paginas_conteudo"):
            primeiro_subtopico = conteudo_final["paginas_conteudo"][0].get("titulo_subtopico", titulo_aula)
            tasks_simuladores.append(("1", f"Laboratório Visual: {primeiro_subtopico}"))

    executor = ThreadPoolExecutor(max_workers=5)
    future_exercicios = executor.submit(task_exercicios) if flag_exercicios else None
    futures_sim = [executor.submit(task_simulador, idx, rec) for idx, rec in tasks_simuladores]
    
    if not flag_exercicios and logger:
        logger.update_agent("exercicios", "ignorado")

    if (not flag_simulador or not tasks_simuladores) and logger:
        logger.update_agent("simulador", "ignorado")
        
    if future_exercicios:
        try:
            caderno = future_exercicios.result()
            if caderno:
                conteudo_final["exercicios_da_aula"] = caderno
        except Exception as e:
            print(f"[ERRO] Agente de Exercícios falhou: {e}")
            if logger:
                logger.update_agent("exercicios", "erro")
                logger.log(f"Agente de Exercícios: Falha - {str(e)[:200]}", "error")
        
    simuladores_resultado = []
    for f in futures_sim:
        try:
            res = f.result()
            if res:
                simuladores_resultado.append(res)
        except Exception as e:
            print(f"[ERRO] Agente Simulador falhou: {e}")
            if logger:
                logger.update_agent("simulador", "erro")
                logger.log(f"Agente Simulador: Falha - {str(e)[:200]}", "error")
            
    if simuladores_resultado:
        conteudo_final["simuladores_da_aula"] = simuladores_resultado
        
    executor.shutdown(wait=False)
    return conteudo_final

@app.post("/api/editar_aula_bloco")
def api_editar_aula_bloco(req: EditarBlocoRequest):
    try:
        conteudo_final = req.novo_conteudo
        
        # Se mandou prompt_ia, passa pela IA para reescrever o bloco
        if req.prompt_ia:
            from client_factory import get_genai_client
            client = get_genai_client()
            resp = client.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=f"Reescreva o seguinte texto baseando-se nestas instruções do professor: '{req.prompt_ia}'.\n\nTexto atual:\n{req.novo_conteudo}"
            )
            if resp.text:
                conteudo_final = resp.text

        doc_ref = db.collection("classrooms").document(req.sala_id).collection("aulas").document(req.aula_id)
        doc_ref.update({
            req.caminho_bloco: conteudo_final
        })
        return {"status": "sucesso", "novo_conteudo": conteudo_final}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SimuladorRequest(BaseModel):
    tema_aula: str
    nome_simulador: str

@app.post("/api/gerar_simulador")
def api_gerar_simulador(req: SimuladorRequest):
    import agente_simulador
    html = agente_simulador.gerar_simulador_html(req.tema_aula, req.nome_simulador)
    if not html:
        raise HTTPException(status_code=500, detail="Erro ao gerar simulador")
    return {"html_code": html}

class VisibilidadeRequest(BaseModel):
    sala_id: str
    aula_id: str
    publicada: bool

class AulaAvulsaRequest(BaseModel):
    sala_id: str
    id_disciplina: str
    numero_aula: int
    aula_manual: AulaManual
    modelo_llm: str = "2.5"

@app.post("/api/toggle_visibilidade")
def toggle_visibilidade(req: VisibilidadeRequest):
    try:
        doc_ref = db.collection("classrooms").document(req.sala_id).collection("aulas").document(req.aula_id)
        doc_ref.update({"publicada": req.publicada})
        return {"status": "sucesso", "publicada": req.publicada}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def processar_aula_avulsa_background(req: AulaAvulsaRequest):
    try:
        disc_ref = db.collection("disciplinas").document(req.id_disciplina).get()
        ementa_texto = disc_ref.to_dict().get("ementa_texto", "") if disc_ref.exists else ""
        nome_disciplina = disc_ref.to_dict().get("nome", req.id_disciplina) if disc_ref.exists else req.id_disciplina
        
        topicos = req.aula_manual.descricao
        objetivo = req.aula_manual.descricao
        titulo = req.aula_manual.titulo
        tema_montado = f"Disciplina: {nome_disciplina}. Aula: {titulo}. Objetivo: {objetivo}. Tópicos: {topicos}"
        
        diretrizes = f"Foque nestes tópicos: {topicos}. Adapte a profundidade para atingir este objetivo: {objetivo}. Use notação matemática rigorosa e seja didático."
        
        db.collection("classrooms").document(req.sala_id).update({"status": "gerando_aulas", "detalhe_progresso": f"Aula Avulsa: Agente Escritor (Fase 1/3)..."})
        
        from logger_agentes import AgentLogger
        logger = AgentLogger(db, req.sala_id, req.numero_aula)
        logger.log(f"Iniciando geracao da Aula Avulsa {req.numero_aula}", "info")
        
        from telemetry import TokenTracker
        tracker = TokenTracker(modo_llm=req.modelo_llm)

        # 1. Extração do Material de Apoio (se houver PDF ou texto)
        material_apoio = ""
        mat_ref = req.aula_manual.arquivo_base_id or req.aula_manual.texto_base_pdf or ""
        caminho_mat_pdf = resolver_caminho_pdf(mat_ref)
        if caminho_mat_pdf:
            nome_arq = req.aula_manual.nome_arquivo or os.path.basename(caminho_mat_pdf)
            db.collection("classrooms").document(req.sala_id).update({"detalhe_progresso": f"Aula Avulsa: Agente Extrator lendo PDF '{nome_arq}' com IA..."})
            material_apoio = agente_extrator.extrair_texto_base_pdf(
                caminho_mat_pdf,
                tema_aula=titulo,
                logger=logger,
                modelo_llm=req.modelo_llm,
                tracker=tracker
            )
        elif req.aula_manual.texto_base_pdf and not str(req.aula_manual.texto_base_pdf).startswith("[PDF_ID:"):
            material_apoio = req.aula_manual.texto_base_pdf

        if material_apoio and material_apoio.strip():
            diretrizes += f"\nATENÇÃO ESTRITA - MATERIAL DE APOIO DO PROFESSOR: Baseie toda a estrutura desta aula, os exemplos, as explicações e o contexto exclusivamente ou prioritariamente no material a seguir fornecido pelo professor:\n\n{material_apoio}\n\n[FIM DO MATERIAL DO PROFESSOR]."

        # 2. Extração de Notações e Diretrizes Específicas
        override_prompt_block = ""
        not_ref = req.aula_manual.arquivo_notacoes_id or req.aula_manual.texto_base_notacoes or ""
        caminho_not_pdf = resolver_caminho_pdf(not_ref)
        override_dict = None

        if caminho_not_pdf:
            nome_arq_not = req.aula_manual.nome_arquivo_notacoes or os.path.basename(caminho_not_pdf)
            db.collection("classrooms").document(req.sala_id).update({"detalhe_progresso": f"Aula Avulsa: Agente Extrator mapeando notações de PDF com IA..."})
            override_dict = agente_extrator.extrair_regras_override_pdf(
                caminho_not_pdf,
                logger=logger,
                modelo_llm=req.modelo_llm,
                tracker=tracker
            )
        else:
            notacoes_raw = req.aula_manual.texto_base_notacoes or ""
            if notacoes_raw.strip() and not str(notacoes_raw).startswith("[PDF_ID:"):
                override_dict = agente_extrator.extrair_regras_override(
                    notacoes_raw,
                    logger=logger,
                    modelo_llm=req.modelo_llm,
                    tracker=tracker
                )

        if override_dict:
            override_prompt_block = agente_extrator.formatar_override_para_prompt(override_dict)
            diretrizes = f"{override_prompt_block}\n\n{diretrizes}"

        conteudo_bruto = gerador_conteudo.gerar_conteudo_aula(
            nome_professor="Professor UFBA",
            codigo_disciplina=req.id_disciplina,
            tema_solicitado=tema_montado,
            ementa_texto=ementa_texto,
            diretrizes_texto=diretrizes, 
            logger=logger, 
            modelo_llm=req.modelo_llm,
            tracker=tracker
        )
        if conteudo_bruto:
            db.collection("classrooms").document(req.sala_id).update({"detalhe_progresso": f"Aula Avulsa: Agente Orquestrador (Fase 2/3)..."})
            conteudo_final = orquestrador_editorial.lapidar_conteudo_global(conteudo_bruto, logger=logger, modelo_llm=req.modelo_llm, tracker=tracker)
            if conteudo_final:
                db.collection("classrooms").document(req.sala_id).update({"detalhe_progresso": f"Aula Avulsa: Agentes Paralelos (Simulador/Exercícios) (Fase 3/3)..."})
                conteudo_final = rodar_agentes_paralelos(
                    conteudo_final, 
                    titulo, 
                    modelo_llm=req.modelo_llm, 
                    diretrizes_override=override_prompt_block, 
                    logger=logger,
                    flag_exercicios=req.aula_manual.gerar_exercicios,
                    flag_simulador=req.aula_manual.gerar_simulador,
                    tracker=tracker
                )

                db.collection("classrooms").document(req.sala_id).update({"detalhe_progresso": "Aula Avulsa: Agente Validador LaTeX (Fase Final)..."})
                conteudo_final = agente_validador_latex.validar_e_corrigir_aula_completa(conteudo_final, logger=logger, modelo_llm=req.modelo_llm, tracker=tracker)

                # Anexa telemetria e custo oficial de tokens
                conteudo_final["telemetria_custo"] = tracker.obter_resumo()

                storage.save_aula(req.sala_id, req.numero_aula, {
                    "numero_aula": req.numero_aula,
                    "titulo": titulo,
                    "conteudo_json": conteudo_final,
                    "publicada": False
                })
                if db:
                    db.collection("classrooms").document(req.sala_id).update({
                        "total_aulas": firestore.Increment(1),
                        "status": "pronto",
                        "detalhe_progresso": "Aula concluída com sucesso!",
                        "cronograma_oficial": firestore.ArrayUnion([{
                            "numero_aula": req.numero_aula,
                            "titulo": titulo,
                            "objetivo_principal": objetivo,
                            "topicos_abordados": [topicos]
                        }])
                    })
    except Exception as e:
        print(f"[ERRO] Erro ao gerar aula avulsa: {e}")

@app.post("/api/gerar_aula_avulsa")
def gerar_aula_avulsa(req: AulaAvulsaRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(processar_aula_avulsa_background, req)
    return {"message": "Gerando aula avulsa", "sala": req.sala_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
