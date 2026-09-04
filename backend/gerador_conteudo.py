import os
import sys
import json
import re
import time
import concurrent.futures
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List

# Importando os schemas estruturados que criamos no arquivo anterior
from schemas import SubtopicoValidado, FonteRDetalhada, SubtopicoRoteiro, RoteiroCompletoAula
from client_factory import get_genai_client
# Importamos a função do revisor local para auditoria
from revisor_notacao import auditar_subtopico_local
import latex_sanitizer

# ==============================================================================
# FUNÇÃO PRINCIPAL DE ORQUESTRAÇÃO DE CONTEÚDO
# ==============================================================================
def gerar_conteudo_aula(nome_professor: str, codigo_disciplina: str, tema_solicitado: str, ementa_texto: str = None, diretrizes_texto: str = None, logger=None, modelo_llm: str = "hibrido", tracker=None):
    t_inicio_roteirista = 0.0
    t_fim_roteirista = 0.0
    t_inicio_escrita = 0.0
    t_fim_escrita = 0.0
    log_subtopicos = []
    if logger:
        logger.update_agent("gerador_bruto", "rodando")
        logger.log("Gerador de Conteúdo: Iniciando elaboração do macro roteiro...", "info")
    
    try:
        client = get_genai_client()
        from telemetry import resolver_modelo
        modelo_roteirista = resolver_modelo("roteirista", modelo_llm)
        modelo_escritor = resolver_modelo("escritor", modelo_llm)

    except Exception as e:
        if logger:
            logger.update_agent("gerador_bruto", "erro")
            logger.log(f"Gerador de Conteúdo: Erro crítico - {str(e)}", "error")
        raise e

    # 1. Recupera as Stores do professor e de livros globais para busca híbrida simultânea
    NOME_STORE = f"store-{nome_professor.lower().strip()}-{codigo_disciplina.lower().strip()}"
    NOME_STORE_FALLBACK = "plataforma-estatistica-db"
    store_names = []
    
    try:
        stores_disponiveis = list(client.file_search_stores.list())
        for store in stores_disponiveis:
            if store.display_name == NOME_STORE:
                store_names.append(store.name)
                print(f"[RAG] RAG especifico do professor ativado! Usando a Store: {store.display_name}")
                
        for store in stores_disponiveis:
            if store.display_name == NOME_STORE_FALLBACK:
                store_names.append(store.name)
                print(f"[RAG] RAG global de livros ativado! Usando a Store: {store.display_name}")
    except Exception as e:
        print(f"[ALERTA] Alerta ao buscar stores no Google Cloud: {e}")
            
    if not store_names:
        print(f"[AVISO] Nenhuma base de dados RAG ('{NOME_STORE}' ou '{NOME_STORE_FALLBACK}') foi encontrada. Continuando em modo sem RAG...")

    # 2. Carrega a ementa (texto puro via API FastAPI)
    if not ementa_texto:
        raise ValueError("O texto da ementa é obrigatório.")
    
    print(f"[EMENTA] Utilizando ementa de {len(ementa_texto)} caracteres para alinhamento de escopo...")

    # 3. Valida as diretrizes de notação e design enviadas pelo Streamlit
    if not diretrizes_texto or not diretrizes_texto.strip():
        raise ValueError("As diretrizes de notação e estilo são obrigatórias e devem ser fornecidas pelo Streamlit.")

    # ==============================================================================
    # FASE 1: AGENTE 1 - O ROTEIRISTA DA EMENTA (Gemini 2.5 Pro)
    # ==============================================================================
    t_inicio_roteirista = time.time()
    print(f"\n[Agente 1 - Roteirista ({modelo_roteirista})] Analisando a ementa e estruturando a trilha pedagógica da aula...")
    
    prompt_roteirista = f"""
Você é um Designer Instrucional Especialista em Ensino Superior de Matemática e Estatística, com foco em modelagem de currículos acadêmicos rigorosos.

### CONTEXTO E MISSÃO
Você receberá a [EMENTA] de uma disciplina universitária (anexada em PDF) e um [TÓPICO_SOLICITADO] (um recorte extraído dessa ementa). 
Sua missão é atuar como um arquiteto de conteúdo: você deve quebrar o [TÓPICO_SOLICITADO] em uma sequência lógica e linear de subtópicos teóricos, preenchendo rigorosamente a estrutura 'RoteiroCompletoAula'.

---

### DIRETRIZES DE ESCOPO E COBERTURA (MANDATÓRIO)
1. Delimitação Estrita da Ementa: Analise a [EMENTA] global para entender o nível de maturidade da disciplina. 
Cubra o [TÓPICO_SOLICITADO] com profundidade matemática adequada, mas NUNCA antecipe ou invada tópicos que estão listados em outras partes da ementa.
2. Granularidade Didática: Não economize subtópicos. Se o tema for complexo, 
fracione-o de forma robusta (geralmente entre 5 a 8 subtópicos, ou mais se necessário). 
Cada item da lista deve focar intensamente em um único conceito específico, garantindo uma progressão pedagógica fluida.
3. Formalismo Teórico Exclusivo: O foco deve ser a intuição conceitual, o formalismo matemático e as deduções analíticas. 
É TERMINANTEMENTE PROIBIDO incluir, sugerir ou criar componentes de programação, sintaxe de código ou laboratórios computacionais 
(como R, Python, SAS ou Julia).

---

### INSTRUÇÕES PARA PREENCHIMENTO DO SCHEMA DE RETORNO

1. 'topico_principal' (string): 
   - Nomeie o tema da aula de forma fluida, clara e contextualizada. 
   - Exemplo: "Fundamentos Teóricos e Aplicações da Regressão Linear Simples".

2. 'esquema_paginas' (lista de SubtopicoRoteiro):
   Cada item representa um subtópico que se tornará uma página teórica e deve conter:
   
   - 'titulo' (string): Título científico elegante, imersivo e de alta sonoridade acadêmica. Evite nomes curtos, genéricos ou informais.
     * Exemplo Ruim: "Introdução ao Teste t"
     * Exemplo Ideal: "A Engenharia Inferencial: Testes de Hipóteses e Distribuição t de Student"
     
   - 'conceitos_chave_rag' (lista de strings): Forneça de 3 a 5 palavras-chave cirúrgicas e termos técnicos exatos associados ao conceito (em português ou inglês). 
     * IMPORTANTE: Esses termos serão usados por um Agente Escritor para busca vetorial (RAG) em livros-texto. Use jargões estatísticos precisos, notações ou nomes de teoremas/estimadores (ex: ["estimadores de MQO", "resíduos ordinários", "mínimos quadrados ordinários", "Gauss-Markov theorem"]).

---

### ENTRADAS DO USUÁRIO
- [EMENTA]: {ementa_texto}
- [TÓPICO_SOLICITADO]: {tema_solicitado}
- [DIRETRIZES_E_MATERIAL_DO_PROFESSOR]: {diretrizes_texto}
"""
    
    contents_roteirista = []
    if ementa_texto:
        contents_roteirista.append(f"Esta é a ementa oficial:\n{ementa_texto}")
    if diretrizes_texto:
        contents_roteirista.append(f"Diretrizes e material do professor:\n{diretrizes_texto}")
    contents_roteirista.append(prompt_roteirista)

    from gemini_retry import executar_chamada_com_retry

    try:
        def chamar_roteirista():
            return client.models.generate_content(
                model=modelo_roteirista,
                contents=contents_roteirista,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RoteiroCompletoAula
                )
            )
        
        resposta_roteiro = executar_chamada_com_retry(
            chamar_roteirista,
            max_retries=5,
            logger=logger,
            nome_agente="Roteirista",
            descricao="elaboração do macro roteiro da aula",
            tracker=tracker,
            modelo=modelo_roteirista
        )
        
        # O Pydantic realiza o parsing nativo garantindo o objeto tipado
        roteiro_pedagogico = RoteiroCompletoAula.model_validate_json(resposta_roteiro.text)
        if logger:
            logger.init_subtopics(len(roteiro_pedagogico.esquema_paginas))
            logger.update_agent("gerador_bruto", "concluido", resposta=resposta_roteiro.text)
            logger.log(f"Roteirista: Roteiro macro concluído com {len(roteiro_pedagogico.esquema_paginas)} subtópicos.", "success")
        t_fim_roteirista = time.time()
        print(f"[OK] Roteiro gerado com sucesso! {len(roteiro_pedagogico.esquema_paginas)} subtópicos mapeados.")
    except Exception as e:
        if logger:
            logger.update_agent("gerador_bruto", "erro")
            logger.log(f"Gerador de Conteúdo: Erro crítico - {str(e)}", "error")
        raise e

    # ==============================================================================
    # FASE 2: AGENTE 2 + 2.5 - O ESCRITOR COM LOOP DE REVISÃO ATIVA
    # ==============================================================================
    t_inicio_escrita = time.time()
    print("\n[Agente 2 + 2.5] Iniciando laço de escrita com loop de revisão ativa EM PARALELO...")
    
    from gemini_retry import executar_chamada_com_retry

    # Função isolada para processar um único subtópico
    def processar_subtopico(idx, sub):
        t_inicio_sub = time.time()
        print(f"\n   -> Iniciando Processamento Subtópico [{idx+1}/{len(roteiro_pedagogico.esquema_paginas)}]: {sub.titulo}")
        
        termos_busca = " ".join(sub.conceitos_chave_rag)
        query_rag = f"{tema_solicitado} - {sub.titulo} - {termos_busca}"
        
        tentativa = 0
        bloco_aprovado = False
        subtopico_atual_dados = None
        dados_escritor_dict = None
        laudo_revisao = None
        
        feedbacks = []
        MAX_TENTATIVAS_REVISAO = 4

        while tentativa < MAX_TENTATIVAS_REVISAO and not bloco_aprovado:
            tentativa += 1
            print(f"      [Topico {idx+1} | Tentativa {tentativa}/{MAX_TENTATIVAS_REVISAO}] Enviando para o Escritor...")

            if store_names:
                diretriz_veracidade = "Baseie-se estritamente e exclusivamente nas informações contidas nos documentos do RAG e nos materiais do professor fornecidos pelo File Search. É terminantemente proibido inventar teoremas, deduzir propriedades sem fundamentação teórica nas fontes recuperadas, ou citar livros que não constem de fato nas referências obtidas."
                contexto_rag_descricao = "os documentos recuperados da base RAG (File Search)"
                tools_config = [
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=store_names,
                            metadata_filter=f'discipline="{codigo_disciplina.upper().strip()}"',
                            top_k=45
                        )
                    )
                ]
            else:
                diretriz_veracidade = "Como não há base RAG de apoio disponível, baseie-se no conhecimento estatístico consolidado da literatura acadêmica padrão (ex: Bussab & Morettin, Morettin & Singer, etc.). É terminantemente proibido inventar teoremas ou deduzir propriedades errôneas. Cite obras e páginas reais e verossímeis nas referências bibliográficas do retorno."
                contexto_rag_descricao = "o conhecimento estatístico consolidado da literatura acadêmica padrão"
                tools_config = None

            from prompts import REGRAS_MESTRE_ESCRITOR

            if tentativa == 1 or not dados_escritor_dict or not laudo_revisao:
                prompt_escritor = f"""
Você é um Professor Titular de Estatística e co-autor de livros didáticos clássicos e rigorosos de nível universitário.

### CONTEXTO E MISSÃO
Você receberá as Diretrizes de Notação e Design do professor, {contexto_rag_descricao} e um [SUBTÓPICO_ALVO] que integra o [TÓPICO_DA_AULA].
Sua missão é atuar como o produtor científico principal do conteúdo teórico: você deve redigir a teoria acadêmica e formalismo matemático de forma extremamente completa para o [SUBTÓPICO_ALVO], preenchendo rigorosamente a estrutura 'SubtopicoValidado'.

---

### DIRETRIZES DE ESCOPO E EXAUSTIVIDADE (MANDATÓRIO)
1. Escrita Didática de Livro: Você tem um limite de saída alto. USE ESTE ESPAÇO PARA SER O MÁXIMO POSSÍVEL DIDÁTICO E CLARO. É OBRIGATÓRIO escrever o texto, explicações e detalhes analíticos para que o aluno compreenda plenamente o assunto. Proibido simplificar demais a ponto de perder o rigor matemático.
2. Regra de Ouro de Veracidade: {diretriz_veracidade}
3. Rigor Científico e LaTeX: Toda notação matemática formal, hipóteses, variabilidades, distribuições e deduções devem ser apresentadas com rigor absoluto em LaTeX estruturado ($$ para destaque centralizado ou $ para linha).

{REGRAS_MESTRE_ESCRITOR}

---

### INSTRUÇÕES PARA PREENCHIMENTO DO SCHEMA DE RETORNO

1. 'titulo_subtopico' (string):
   - Deve conter o título exato do subtópico: '{sub.titulo}'.

2. 'conteudo' (objeto ConteudoSubtopico):
   - 'tipo_bloco' (string): Deve ser preenchido estritamente como 'teorico'.
   - 'conceito_intuitivo' (string): Texto longo e aprofundado, de no mínimo 3 a 4 parágrafos densos (separe-os obrigatoriamente com DUAS quebras de linha \\n\\n). Explique a motivação histórica, o problema prático que impulsionou o conceito e analogias do mundo real. Adote o tom, linguagem e termos do professor fornecidos no override. ATENÇÃO: Proibido inserir qualquer notação LaTeX matemática ($ ou $$) neste campo. Mantenha o foco puramente na prosa qualitativa.
   - 'conceito_formal' (string ou null): Apresente o enunciado matemático formal em LaTeX ($$ ou $). Se o subtópico for histórico/qualitativo/conceitual (sem fórmulas próprias), RETORNE ESTRITAMENTE null.
   - 'propriedades_do_conceito' (lista de strings ou null): Mapeie leis, teoremas e propriedades deduzidas diretamente desse conceito (ou null se for subtópico qualitativo).
   - 'pre_requisitos_e_auxiliares' (lista de strings ou null): Ferramentas matemáticas necessárias (ou null se não houver).
   - 'condicoes_de_contorno' (lista de strings ou null): Premissas e suposições fundamentais para a validade do modelo (ou null se não aplicável).
   - 'simuladores_interativos_recomendados' (lista de strings ou null): Lista contendo uma ou mais propostas de simulações/visualizações interativas com Plotly e controles dinâmicos/sliders (ex: ['Reta OLS com sliders de tamanho amostral n e ruído sigma', 'Gráfico de dispersão de resíduos']). PRIORIZE SEMPRE A INTERATIVIDADE. Se não for necessário gráfico neste subtópico, retorne null.
   - 'deducao_formal_passo_a_passo' (lista de strings ou null): Demonstração matemática completa em LaTeX ($$), cada string representando um passo contíguo. Se for subtópico conceitual/histórico/qualitativo sem demonstração algébrica, RETORNE ESTRITAMENTE null.
   - 'interpretacao_geometrica_grafica' (string ou null): Explique como visualizar o conceito espacialmente ou graficamente (ou null se não aplicável).
   - 'exemplo_canonico' (objeto EstruturaExemplo ou null):
     * 'enunciado' (string): Problema contextualizado (podendo ser clássico como moedas/dados para intuição ou aplicado à indústria).
     * 'passo_a_passo_solucao' (lista de strings): Cálculos detalhados em LaTeX ($$).
     * 'resultado_final' (string): Resultado aritmético seguido de interpretação prática.

3. 'fontes_rag' (lista de FonteRDetalhada):
   Cada item representa uma fonte bibliográfica e deve conter:
   - 'livro_autor' (string): Sobrenome dos autores e título clássico do livro.
   - 'capitulo' (string): Capítulo e seção consultada.
   - 'paginas_utilizadas' (string): O número exato da página ou intervalo de páginas consultadas (ex: "p. 142" ou "pp. 210-214"). Se não houver RAG, preencher com referências padrão consolidadas.

---

### ENTRADAS DO USUÁRIO
- [TÓPICO_DA_AULA]: {tema_solicitado}
- [SUBTÓPICO_ALVO]: {sub.titulo}
- [DIRETRIZES_DE_ESTILO]:
{diretrizes_texto}
"""
                contents_envio = [query_rag, prompt_escritor]
            else:
                # PROMPT DE REPARO CIRÚRGICO BASEADO NO LAUDO DO REVISOR
                rascunho_anterior_str = json.dumps(dados_escritor_dict, ensure_ascii=False, indent=2)
                prompt_escritor = f"""
Você é um Professor Titular de Estatística revisando um capítulo após auditoria rigorosa do Revisor Científico.

### CONTEXTO E MISSÃO DE REPARO CIRÚRGICO
O Revisor Científico auditou o seu rascunho anterior e apontou correções específicas (cálculos numéricos, matrizes, determinantes ou notações no 'exemplo_canonico').

Sua missão é APROVEITAR 100% da riqueza teórica do rascunho anterior e APLICAR CIRURGICAMENTE as correções apontadas pelo Revisor, substituindo os valores errados pelos valores e fórmulas exatas do laudo.

---

### LAUDO DO REVISOR CIENTÍFICO COM AS CORREÇÕES OBRIGATÓRIAS (SIGA CADA PONTO):
{laudo_revisao.comentario_correcao}

---

### RASCUNHO ANTERIOR GERADO:
{rascunho_anterior_str}

---

### DIRETRIZES DE REPARO CIRÚRGICO (MANDATÓRIO):
1. Mantenha intactos todos os parágrafos de introdução, motivação, intuição teórica e formalismo que já foram elogiados ou aprovados pelo revisor.
2. Corrija cirurgicamente as passagens e cálculos indicados no laudo (ex: produtos de matrizes, determinantes, coeficientes, valores ajustados, resíduos e conclusões no 'exemplo_canonico').
3. Preencha rigorosamente a estrutura 'SubtopicoValidado' completa.
"""
                contents_envio = [prompt_escritor]

            config_escritor = types.GenerateContentConfig(
                tools=tools_config,
                response_mime_type="application/json",
                response_schema=SubtopicoValidado
            )

            try:
                if logger:
                    logger.update_agent(f"gerador_bruto_{idx+1}", "rodando", prompt=prompt_escritor)
                    logger.log(f"Gerador de Conteúdo: Redigindo tópico {idx+1} (Tentativa {tentativa})...", "info")
                
                def chamar_escritor():
                    return client.models.generate_content(
                        model=modelo_escritor,
                        contents=contents_envio,
                        config=config_escritor
                    )

                resposta_escritor = executar_chamada_com_retry(
                    chamar_escritor,
                    max_retries=5,
                    logger=logger,
                    nome_agente=f"Escritor_{idx+1}",
                    descricao=f"redação do subtópico {idx+1} (tentativa {tentativa})",
                    tracker=tracker,
                    modelo=modelo_escritor
                )
                
                if logger:
                    logger.update_agent(f"gerador_bruto_{idx+1}", "rodando", resposta=resposta_escritor.text)
                    logger.log(f"gerador_{idx+1}_{tentativa} terminou", "info")
                
                dados_escritor_dict = json.loads(resposta_escritor.text)
                dados_escritor_dict = latex_sanitizer.sanitize_json_recursively(dados_escritor_dict)
                
                print(f"      [REVISOR] Analisando tópico {idx+1}...")
                laudo_revisao = auditar_subtopico_local(dados_escritor_dict, diretrizes_texto, logger=logger, sub_idx=idx+1, sub_tentativa=tentativa, modelo_llm=modelo_llm, tracker=tracker)
                
                if laudo_revisao.aprovado:
                    print(f"      [OK] Bloco {idx+1} APROVADO pelo revisor!")
                    if logger:
                        logger.log(f"Revisor (Crítico): Tópico {idx+1} aprovado!", "success")
                    bloco_aprovado = True
                    
                    if laudo_revisao.conteudo_corrigido:
                        subtopico_atual_dados = laudo_revisao.conteudo_corrigido
                    else:
                        subtopico_atual_dados = SubtopicoValidado(**dados_escritor_dict)
                    
                    fontes_capturadas = []
                    if hasattr(resposta_escritor, "grounding_metadata") and resposta_escritor.grounding_metadata:
                        chunks = resposta_escritor.grounding_metadata.grounding_chunks
                        if chunks:
                            for chunk in chunks:
                                if hasattr(chunk, "retrieved_context") and chunk.retrieved_context:
                                    ctx = chunk.retrieved_context
                                    title = getattr(ctx, "title", "Livro Ingerido")
                                    page = str(getattr(ctx, "page_number", "S/N"))
                                    fontes_capturadas.append(
                                        FonteRDetalhada(
                                            livro_autor=title,
                                             capitulo="N/A (Grounding)",
                                            paginas_utilizadas=f"p. {page}" if page != "S/N" else "p. não especificada"
                                        )
                                    )
                    if fontes_capturadas:
                        vistas = set()
                        fontes_unicas = []
                        for f in fontes_capturadas:
                            chave = (f.livro_autor, f.paginas_utilizadas)
                            if chave not in vistas:
                                vistas.add(chave)
                                fontes_unicas.append(f)
                        subtopico_atual_dados.fontes_rag = fontes_unicas
                else:
                    print(f"      [REPROVADO] Bloco {idx+1} REPROVADO! Motivo: {laudo_revisao.comentario_correcao}")
                    if logger:
                        logger.log(f"Revisor (Crítico): Tópico {idx+1} reprovado. Devolvendo ao gerador com rascunho e laudo...", "warning")
                    feedbacks.append(laudo_revisao.comentario_correcao)
                    
            except Exception as e:
                print(f"      [ERRO] Falha no subtópico {idx+1}: {e}")
                time.sleep(3)
                
        if not subtopico_atual_dados and dados_escritor_dict:
            subtopico_atual_dados = SubtopicoValidado(**dados_escritor_dict)
            subtopico_atual_dados.fontes_rag = [
                FonteRDetalhada(
                    livro_autor="Fonte nao mapeada",
                    capitulo="Falhas na revisao",
                    paginas_utilizadas="p. S/N"
                )
            ]
            
        t_fim_sub = time.time()
        log_data = {
            "titulo": sub.titulo,
            "tentativas": tentativa,
            "reprovacoes": len(feedbacks),
            "feedbacks": feedbacks,
            "tempo_segundos": round(t_fim_sub - t_inicio_sub, 2),
            "aprovado": bloco_aprovado
        }
        
        if logger:
            logger.update_agent(f"gerador_bruto_{idx+1}", "concluido")
            logger.update_agent(f"revisor_{idx+1}", "concluido")
        return (idx, subtopico_atual_dados, log_data)


    # Controle de Pool de Execução
    aulas_conteudo_final = [None] * len(roteiro_pedagogico.esquema_paginas)
    log_subtopicos = [None] * len(roteiro_pedagogico.esquema_paginas)
    
    tarefas_pendentes = list(enumerate(roteiro_pedagogico.esquema_paginas))
    max_workers_atuais = 3
    cooldowns_executados = 0
    MAX_COOLDOWNS = 3
    
    while tarefas_pendentes:
        print(f"\n[POOL] Iniciando pool com {max_workers_atuais} workers para {len(tarefas_pendentes)} tópicos pendentes.")
        ocorreu_429 = False
        tarefas_falhadas_429 = []
        
        # O ThreadPoolExecutor será cancelado nativamente no Python 3.9+ usando cancel_futures=True se houver erro
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers_atuais)
        
        # Submete as tarefas
        futuros = {}
        for item in tarefas_pendentes:
            fut = executor.submit(processar_subtopico, item[0], item[1])
            futuros[fut] = item
            
        tarefas_pendentes = [] # Limpa a lista para o caso de precisarmos reabastecer com as falhas
        
        try:
            for futuro in concurrent.futures.as_completed(futuros):
                item = futuros[futuro]
                idx_orig, sub_orig = item
                try:
                    res_idx, res_dados, res_log = futuro.result()
                    aulas_conteudo_final[res_idx] = res_dados
                    log_subtopicos[res_idx] = res_log
                    print(f"   -> [CONCLUÍDO] Tópico {res_idx+1} gerado com sucesso!")
                except Exception as e:
                    if "429_TOO_MANY_REQUESTS" in str(e):
                        if not ocorreu_429:
                            print("\n[ERRO CRÍTICO 429] Detectado limite de requisições! Iniciando protocolo de cancelamento e cooldown...")
                            ocorreu_429 = True
                        tarefas_falhadas_429.append(item)
                    else:
                        print(f"\n[ERRO FATAL] O tópico {idx_orig+1} falhou e não pode ser recuperado: {e}")
                        aulas_conteudo_final[idx_orig] = "FALHA"
                        
        finally:
            # Encerra o pool atual. Em Python 3.9+, cancel_futures=True cancela as tarefas que ainda estão na fila de espera
            # Para manter compatibilidade com versões antigas, cancelamos manualmente as pendentes que não completaram.
            executor.shutdown(wait=False, cancel_futures=True) if hasattr(executor, 'shutdown') and 'cancel_futures' in executor.shutdown.__code__.co_varnames else executor.shutdown(wait=False)
            
            # As tarefas canceladas não retornarão result(), então elas não foram colocadas em aulas_conteudo_final
            # Precisamos re-adicionar todas as tarefas que ainda não estão prontas na lista pendente
            tarefas_pendentes = []
            for i, sub in enumerate(roteiro_pedagogico.esquema_paginas):
                if aulas_conteudo_final[i] is None:
                    tarefas_pendentes.append((i, sub))
        
        if ocorreu_429 and tarefas_pendentes:
            cooldowns_executados += 1
            if cooldowns_executados > MAX_COOLDOWNS:
                raise Exception(f"Abortando após {MAX_COOLDOWNS} tentativas falhas de cooldown para erros 429. Verifique sua cota da API.")
            print(f"[COOLDOWN {cooldowns_executados}/{MAX_COOLDOWNS}] Aguardando 60 segundos antes de tentar novamente...")
            time.sleep(60)
            max_workers_atuais = 3
            print("[COOLDOWN] Reduzindo paralelismo para 3 workers para evitar novos erros 429.")
            
    # Remove eventuais Nones caso algum tópico tenha falhado irreversivelmente
    aulas_conteudo_final = [x for x in aulas_conteudo_final if x is not None and x != "FALHA"]
    
    t_fim_escrita = time.time()
    if logger:
        for i in range(1, len(roteiro_pedagogico.esquema_paginas) + 1):
            logger.update_agent(f"gerador_bruto_{i}", "concluido")
            logger.update_agent(f"revisor_{i}", "concluido")
        logger.update_agent("revisor", "concluido")
        logger.log("Conteúdo bruto e revisão finalizados.", "success")

    return {
        "tema": tema_solicitado,
        "conteudo_paginas": [p.model_dump() for p in aulas_conteudo_final],
        "log_gerador": {
            "tempo_roteirista_segundos": round(t_fim_roteirista - t_inicio_roteirista, 2),
            "tempo_escrita_revisao_segundos": round(t_fim_escrita - t_inicio_escrita, 2),
            "subtopicos": log_subtopicos
        }
    }

if __name__ == "__main__":
    print("[AVISO] A geração de conteúdo deve ser executada a partir da interface do Streamlit.")
    print("Por favor, execute o comando: streamlit run app.py")
