import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile
from concurrent.futures import ThreadPoolExecutor
from fastapi.middleware.cors import CORSMiddleware
import pypdf
import io
import firebase_admin
from firebase_admin import credentials, firestore
from pydantic import BaseModel
import gerador_conteudo
import orquestrador_editorial
import agente_validador_latex
from macro_roteirista import MacroRoteirista

import json
from logger_agentes import AgentLogger

# Inicialização do Firebase Admin
try:
    if os.environ.get("FIREBASE_CREDENTIALS"):
        # Modo Produção: Ler da Variável de Ambiente (Render.com)
        cred_dict = json.loads(os.environ.get("FIREBASE_CREDENTIALS"))
        cred = credentials.Certificate(cred_dict)
    else:
        # Modo Local: Ler do Arquivo
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
    """Busca ementa no Firestore com fallback automático para os PDFs locais da pasta ementas/"""
    disc_data = storage.get_disciplina(id_disciplina)
    if disc_data and disc_data.get("ementa_texto"):
        return disc_data["ementa_texto"], disc_data.get("nome", id_disciplina)

    ementas_dir = os.path.join(os.path.dirname(__file__), "ementas")
    if os.path.exists(ementas_dir):
        for fname in os.listdir(ementas_dir):
            if fname.lower().startswith(id_disciplina.lower()) and fname.endswith(".pdf"):
                try:
                    fpath = os.path.join(ementas_dir, fname)
                    with open(fpath, "rb") as f:
                        reader = pypdf.PdfReader(f)
                        texto = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
                        if texto:
                            print(f"[FALLBACK] Ementa da disciplina {id_disciplina} carregada direto do PDF local: {fname}")
                            return texto, id_disciplina
                except Exception as e:
                    print(f"[ERRO] Falha ao ler PDF local {fname}: {e}")

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
                        "gerar_exercicios": aula_manual.gerar_exercicios,
                        "gerar_simulador": aula_manual.gerar_simulador
                    })
            elif req.tipo_crie_seu_jeito == "automatico":
                print("[BACKGROUND] Modo Crie do Seu Jeito Automático: Usando PDF do professor como ementa.")
                storage.update_classroom(req.id_sala, {"status": "fatiando_ementa_pdf"})
                macro = MacroRoteirista()
                cronograma = macro.gerar_cronograma(
                    ementa_texto=req.arquivo_global_pdf, 
                    instrucoes_personalizadas=req.instrucoes_personalizadas, 
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
            
            macro = MacroRoteirista()
            cronograma = macro.gerar_cronograma(
                ementa_texto=ementa_texto, 
                instrucoes_personalizadas=req.instrucoes_personalizadas, 
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
            
            # Adiciona o arquivo pdf/texto se tiver (modo manual)
            material_apoio = aula.get("texto_base_pdf", "")
            if material_apoio:
                diretrizes += f"\nATENÇÃO ESTRITA - MATERIAL DE APOIO DO PROFESSOR: Baseie toda a estrutura desta aula, os exemplos, as explicações e o contexto exclusivamente ou prioritariamente no material a seguir fornecido pelo professor:\n\n{material_apoio}\n\n[FIM DO MATERIAL DO PROFESSOR]."
            
            logger = AgentLogger(db, req.id_sala, numero)
            logger.log(f"Iniciando geracao da Aula {numero}", "info")
            
            notacoes_raw = aula.get("texto_base_notacoes", "")
            override_prompt_block = ""
            if notacoes_raw and notacoes_raw.strip():
                import agente_extrator
                log_debug(req.id_sala, f"Aula {numero}: Extraindo notações e diretrizes específicas com Agente Extrator...")
                override_dict = agente_extrator.extrair_regras_override(notacoes_raw, logger=logger)
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
                modelo_llm=req.modelo_llm
            )
            
            if conteudo_bruto:
                conteudo_final = orquestrador_editorial.lapidar_conteudo_global(conteudo_bruto, logger=logger)
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
                        flag_simulador=flag_simulador
                    )

                    # Valida LaTeX antes de salvar
                    storage.update_classroom(req.id_sala, {"detalhe_progresso": f"Aula {numero}: Agente Validador LaTeX (Fase Final)..."})
                    conteudo_final = agente_validador_latex.validar_e_corrigir_aula_completa(conteudo_final, logger=logger, modelo_llm=req.modelo_llm)

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
    return {"status": "ok", "firebase": db is not None}

@app.post("/api/gerar_semestre")
def gerar_semestre(req: SemestreRequest, background_tasks: BackgroundTasks):
    if not db:
        raise HTTPException(status_code=500, detail="Banco de dados não conectado")
    
    background_tasks.add_task(processar_semestre_background, req)
    
    return {"message": "Semestre em processamento", "sala": req.id_sala}

@app.post("/api/upload_pdf")
async def upload_pdf(files: List[UploadFile] = File(...)):
    texto_completo = ""
    
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            continue # Ignorar não-PDFs

        try:
            content = await file.read()
            reader = pypdf.PdfReader(io.BytesIO(content))
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    texto_completo += t + "\n"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro processando {file.filename}: {str(e)}")

    if not texto_completo.strip():
        raise HTTPException(status_code=400, detail="Nenhum texto pôde ser extraído dos arquivos.")

    return {"status": "sucesso", "texto_extraido": texto_completo}

class EditarBlocoRequest(BaseModel):
    sala_id: str
    aula_id: str
    caminho_bloco: str # ex: "conteudo_json.paginas_conteudo.0.discussao_teorica_prosa"
    novo_conteudo: str
    prompt_ia: str = "" # Se vier preenchido, usa IA para editar


def rodar_agentes_paralelos(conteudo_final, titulo_aula, modelo_llm="2.5", diretrizes_override=None, logger=None, flag_exercicios=True, flag_simulador=True):
    import agente_exercicios
    import agente_simulador
    
    def task_exercicios():
        return agente_exercicios.gerar_caderno_exercicios(
            conteudo_final, 
            logger=logger, 
            modelo_llm=modelo_llm, 
            diretrizes_override=diretrizes_override
        )
        
    def task_simulador(idx_pag, nome_sim):
        html = agente_simulador.gerar_simulador_html(titulo_aula, nome_sim, logger=logger)
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
                model='gemini-flash-latest',
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
        
        # Consolida todo o material de apoio, anotações e diretrizes para o Agente 1
        materiais_professor = []
        if req.aula_manual.texto_base_pdf:
            materiais_professor.append(f"[MATERIAL DE APOIO / TEXTO BASE DO PROFESSOR]:\n{req.aula_manual.texto_base_pdf}")
        if req.aula_manual.texto_base_notacoes:
            materiais_professor.append(f"[ANOTAÇÕES DE NOTAÇÃO E LINGUAGEM DO PROFESSOR]:\n{req.aula_manual.texto_base_notacoes}")
        if req.aula_manual.descricao:
            materiais_professor.append(f"[DIRETRIZES PEDAGÓGICAS E OBJETIVOS DO PROFESSOR]:\n{req.aula_manual.descricao}")
            
        texto_consolidado_professor = "\n\n".join(materiais_professor)
        override_prompt_block = ""
        if texto_consolidado_professor.strip():
            import agente_extrator
            print(f"Aula Avulsa {req.numero_aula}: Extraindo notações, tom e diretrizes com Agente Extrator...")
            override_dict = agente_extrator.extrair_regras_override(texto_consolidado_professor, logger=logger)
            if override_dict:
                override_prompt_block = agente_extrator.formatar_override_para_prompt(override_dict)
                diretrizes = f"{override_prompt_block}\n\n{diretrizes}"
                
        conteudo_bruto = gerador_conteudo.gerar_conteudo_aula(
            nome_professor="Professor UFBA",
            codigo_disciplina=req.id_disciplina,
            tema_solicitado=tema_montado,
            ementa_texto=ementa_texto,
            diretrizes_texto=diretrizes, logger=logger, modelo_llm=req.modelo_llm)
        if conteudo_bruto:
            db.collection("classrooms").document(req.sala_id).update({"detalhe_progresso": f"Aula Avulsa: Agente Orquestrador (Fase 2/3)..."})
            conteudo_final = orquestrador_editorial.lapidar_conteudo_global(conteudo_bruto, logger=logger)
            if conteudo_final:
                db.collection("classrooms").document(req.sala_id).update({"detalhe_progresso": f"Aula Avulsa: Agentes Paralelos (Simulador/Exercícios) (Fase 3/3)..."})
                conteudo_final = rodar_agentes_paralelos(
                    conteudo_final, 
                    titulo, 
                    modelo_llm=req.modelo_llm, 
                    diretrizes_override=override_prompt_block, 
                    logger=logger
                )

                db.collection("classrooms").document(req.sala_id).update({"detalhe_progresso": "Aula Avulsa: Agente Validador LaTeX (Fase Final)..."})
                conteudo_final = agente_validador_latex.validar_e_corrigir_aula_completa(conteudo_final, logger=logger, modelo_llm=req.modelo_llm)

                db.collection("classrooms").document(req.sala_id).collection("aulas").document(str(req.numero_aula)).set({
                    "numero_aula": req.numero_aula,
                    "titulo": titulo,
                    "conteudo_json": conteudo_final,
                    "publicada": False
                })
                db.collection("classrooms").document(req.sala_id).update({
                    "aulas_geradas": firestore.Increment(1),
                    "total_aulas": firestore.Increment(1),
                    "status": "pronto",
                    "detalhe_progresso": "Aula conclu?da com sucesso!",
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
