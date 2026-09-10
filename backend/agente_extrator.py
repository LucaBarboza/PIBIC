import os
import json
from typing import Optional, Dict
from google import genai
from google.genai import types
from dotenv import load_dotenv
from schemas import RegraOverride
from client_factory import get_genai_client

load_dotenv()

PROMPT_EXTRATOR = """
Você é um Especialista em Extração de Diretrizes, Notações Acadêmicas e Perfil Pedagógico de Professores Universitários.
Sua missão é ler o conjunto de documentos (texto de apoio/PDF, anotações de notação e diretrizes) fornecido pelo professor e extrair com extrema riqueza, profundidade e precisão:

1. Tom, Voz e Linguagem do Professor (Perfil Pedagógico Descritivo Aprofundado):
   - Elabore um parágrafo descritivo rico, denso e minucioso caracterizando a "persona" pedagógica do professor.
   - Detalhe expressamente:
     a) O tom didático e a postura (ex: acolhedor e encorajador, rigoroso e analítico, instigante, pragmático).
     b) O vocabulário e estilo textual (ex: uso de perguntas reflexivas para o aluno, analogias visuais/intuitivas, ênfase em intuição geométrica ou tomada de decisão, termos preferidos).
     c) O modo como o professor transita da intuição teórica para a prática e como ele conduz as explicações.
   - Esse texto funcionará como uma diretriz editorial mestra para que o Agente Escritor assuma a exata "voz" do professor ao redigir a aula.

2. Notações Estatísticas e Matemáticas Específicas: Mapeie o conceito/variável para a notação exata exigida pelo professor em LaTeX (ex: "média populacional" -> "\\mu", "desvio padrão" -> "\\sigma", "independência" -> "\\perp").
3. Tópicos Obrigatórios: Quaisquer assuntos, conceitos ou subtópicos específicos que o professor declarou que devem ser cobertos nesta aula.
4. Estilo de Exercícios: Instruções sobre nivelamento, formato, estilo ou quantidade de questões e preferências de exemplos.
5. Outras Diretrizes: Observações pedagógicas, alertas ou avisos contextuais relevantes.

DOCUMENTO DO PROFESSOR:
{texto_documento}
"""

def extrair_regras_override(texto_documento: str, logger=None, modelo_llm: str = "hibrido", tracker=None) -> Optional[Dict]:
    """
    Lê o texto/documento de notações/diretrizes do professor e usa o Gemini 2.5 Flash
    com Structured Output (schema RegraOverride) para retornar as regras estruturadas.
    """
    if not texto_documento or not texto_documento.strip():
        return None
        
    from gemini_retry import executar_chamada_com_retry
    from telemetry import resolver_modelo
    modelo_alvo = resolver_modelo("extrator", modelo_llm)

    try:
        client = get_genai_client()
        
        prompt = PROMPT_EXTRATOR.format(texto_documento=texto_documento)
        
        if logger:
            logger.update_agent("extrator", "rodando", prompt=prompt)
            logger.log("Agente Extrator: Lendo notações, tom e diretrizes específicas...", "info")
            
        def chamar_extrator():
            return client.models.generate_content(
                model=modelo_alvo,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RegraOverride
                )
            )

        resposta = executar_chamada_com_retry(
            chamar_extrator,
            max_retries=5,
            logger=logger,
            nome_agente="Extrator",
            descricao="extração de notações e diretrizes",
            tracker=tracker,
            modelo=modelo_alvo
        )
        
        if resposta.text:
            override_dict = json.loads(resposta.text)
            if logger:
                logger.log("Agente Extrator: Notações e diretrizes extraídas com sucesso!", "info")
            return override_dict
            
    except Exception as e:
        print(f"[ERRO] Falha no Agente Extrator: {e}")
        if logger:
            logger.log(f"[ERRO] Agente Extrator falhou: {e}", "erro")
            
    return None

def carregar_part_pdf(caminho_pdf: str, client):
    """
    Lê o arquivo PDF bruto e empacota para o Gemini 2.5 Multimodal.
    Para arquivos <= 20MB, utiliza Part.from_bytes direta sem latência de upload de arquivo.
    Para arquivos > 20MB, utiliza a API de arquivos client.files.upload.
    """
    tamanho = os.path.getsize(caminho_pdf)
    if tamanho <= 20 * 1024 * 1024:
        with open(caminho_pdf, "rb") as f:
            dados = f.read()
        return types.Part.from_bytes(data=dados, mime_type="application/pdf")
    else:
        return client.files.upload(file=caminho_pdf)

def extrair_texto_base_pdf(caminho_pdf: str, tema_aula: str = "", logger=None, modelo_llm: str = "hibrido", tracker=None) -> str:
    """
    Usa o Gemini Multimodal para ler e estruturar o PDF do professor com máxima fidelidade.
    Transcreve fórmulas para LaTeX, conceitos teóricos, deduções, exemplos e didática.
    Substitui 100% o pypdf, funcionando até para materiais escaneados ou complexos.
    """
    if not os.path.exists(caminho_pdf):
        return ""
        
    client = get_genai_client()
    from gemini_retry import executar_chamada_com_retry
    from telemetry import resolver_modelo
    modelo_alvo = resolver_modelo("extrator", modelo_llm)
    
    nome_arq = os.path.basename(caminho_pdf)
    if logger:
        logger.update_agent("extrator", "rodando")
        logger.log(f"Agente Extrator (IA): Analisando PDF '{nome_arq}' com IA multimodal ({modelo_alvo})...", "info")
    print(f"\n[Agente Extrator ({modelo_alvo})] Analisando PDF multimodal '{nome_arq}'...")

    prompt = f"""
Você é um Especialista Sênior em Transcrição e Estruturação Didática de Documentos Acadêmicos Universitários.
Analise detalhadamente o documento PDF anexado, que é o material base fornecido pelo professor para a aula '{tema_aula}'.

Sua missão é extrair, transcrever e estruturar todo o conteúdo conceitual deste documento com máxima fidelidade pedagógica e matemática:
1. Sequência Temática: Liste e organize os assuntos na ordem exata apresentada pelo professor.
2. Fórmulas e Definições: Transcreva TODAS as fórmulas, definições matemáticas e deduções analíticas rigorosamente em formato LaTeX válido ($ ... $ para inline e $$ ... $$ para display).
3. Exemplos Numéricos e Práticos: Transcreva enunciados, dados de problemas e passos aritméticos presentes nas notas.
4. Notações e Convenções: Destaque as convenções de notação e termos técnicos utilizados pelo professor.
5. Postura e Tom: Mantenha as analogias, ênfases pedagógicas e intuições do professor.

Produza um texto denso, rico, completo e detalhado em português que servirá de diretriz mestra para os micro-agentes que redigirão a aula.
"""

    try:
        pdf_part = carregar_part_pdf(caminho_pdf, client)
        
        def chamar_extrator_material():
            return client.models.generate_content(
                model=modelo_alvo,
                contents=[pdf_part, prompt]
            )
            
        resposta = executar_chamada_com_retry(
            chamar_extrator_material,
            max_retries=4,
            logger=logger,
            nome_agente="Extrator PDF Material",
            descricao=f"leitura multimodal do PDF {nome_arq}",
            tracker=tracker,
            modelo=modelo_alvo
        )
        
        if resposta and resposta.text:
            if logger:
                logger.log(f"Agente Extrator (IA): PDF '{nome_arq}' lido e estruturado com sucesso!", "success")
            print(f" [OK] Agente Extrator processou '{nome_arq}' com sucesso ({len(resposta.text)} caracteres extraídos).")
            return resposta.text.strip()
            
    except Exception as e:
        print(f"[ERRO] Falha no Agente Extrator ao ler PDF com IA: {e}")
        if logger:
            logger.log(f"[ERRO] Agente Extrator falhou na leitura do PDF: {e}", "erro")
            
    return ""

def extrair_regras_override_pdf(caminho_pdf: str, logger=None, modelo_llm: str = "hibrido", tracker=None) -> Optional[Dict]:
    """
    Lê um PDF de notações/diretrizes diretamente com o Gemini Multimodal e extrai o RegraOverride estruturado.
    """
    if not os.path.exists(caminho_pdf):
        return None
        
    client = get_genai_client()
    from gemini_retry import executar_chamada_com_retry
    from telemetry import resolver_modelo
    modelo_alvo = resolver_modelo("extrator", modelo_llm)
    
    nome_arq = os.path.basename(caminho_pdf)
    if logger:
        logger.update_agent("extrator", "rodando")
        logger.log(f"Agente Extrator (IA): Mapeando notações e diretrizes do PDF '{nome_arq}' com {modelo_alvo}...", "info")
    print(f"\n[Agente Extrator ({modelo_alvo})] Mapeando notações do PDF '{nome_arq}'...")

    prompt = """
Você é um Especialista em Extração de Diretrizes, Notações Acadêmicas e Perfil Pedagógico de Professores Universitários.
Sua missão é ler o documento PDF anexado (anotações de notação e diretrizes do professor) e extrair com extrema riqueza e precisão o JSON estruturado conforme o schema RegraOverride:
1. Tom, Voz e Linguagem do Professor: Elabore um parágrafo descritivo rico e detalhado caracterizando a postura e didática.
2. Notações Estatísticas e Matemáticas Específicas: Mapeie o conceito/variável para a notação exata exigida pelo professor em LaTeX (ex: conceito -> "\\mu").
3. Tópicos Obrigatórios: Quaisquer assuntos ou conceitos que devem obrigatoriamente constar.
4. Estilo de Exercícios: Instruções sobre o estilo, nivelamento ou quantidade de exercícios.
5. Outras Diretrizes: Observações e alertas contextuais.
"""

    try:
        pdf_part = carregar_part_pdf(caminho_pdf, client)
        
        def chamar_extrator_notacoes():
            return client.models.generate_content(
                model=modelo_alvo,
                contents=[pdf_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RegraOverride
                )
            )
            
        resposta = executar_chamada_com_retry(
            chamar_extrator_notacoes,
            max_retries=4,
            logger=logger,
            nome_agente="Extrator PDF Notações",
            descricao=f"extração de notações do PDF {nome_arq}",
            tracker=tracker,
            modelo=modelo_alvo
        )
        
        if resposta and resposta.text:
            override_dict = json.loads(resposta.text)
            if logger:
                logger.log(f"Agente Extrator (IA): Notações do PDF '{nome_arq}' mapeadas com sucesso!", "success")
            return override_dict
            
    except Exception as e:
        print(f"[ERRO] Falha no Agente Extrator ao ler notações do PDF: {e}")
        if logger:
            logger.log(f"[ERRO] Agente Extrator falhou na leitura de notações do PDF: {e}", "erro")
            
    return None

def formatar_override_para_prompt(override_dict: dict) -> str:
    """
    Converte o dicionário RegraOverride em um bloco de texto formatado
    pronto para injeção nos prompts dos micro-agentes com prioridade absoluta.
    """
    if not override_dict:
        return ""
        
    linhas = ["[OVERRIDE DE DIRETRIZES E LINGUAGEM DO PROFESSOR - PRIORIDADE ABSOLUTA]"]
    
    # 1. Tom e Linguagem do Professor
    tom = override_dict.get("tom_e_linguagem_professor")
    if tom and isinstance(tom, str) and tom.strip():
        linhas.append(f"\nESTILO, TOM E LINGUAGEM DO PROFESSOR (ADOTE FIELMENTE NA REDAÇÃO):\n  - {tom.strip()}")

    # 2. Notações específicas (Dicionário de Conceito -> Notação)
    notacoes = override_dict.get("notacoes_estatisticas_especificas")
    if notacoes and isinstance(notacoes, dict) and len(notacoes) > 0:
        linhas.append("\nREGRAS DE NOTAÇÃO MATEMÁTICA ESTATÍSTICA (SOBRESCREVE O PADRÃO):")
        for conceito, notacao in notacoes.items():
            linhas.append(f"  - Conceito: '{conceito}' -> Notação Exata Obrigatória: {notacao}")
            
    # 3. Tópicos Obrigatórios
    topicos = override_dict.get("topicos_obrigatorios")
    if topicos and isinstance(topicos, list) and len(topicos) > 0:
        linhas.append("\nTÓPICOS E SUBTÓPICOS OBRIGATÓRIOS NESTA AULA:")
        for t in topicos:
            linhas.append(f"  - {t}")
            
    # 4. Estilo de Exercícios
    estilo = override_dict.get("estilo_exercicios")
    if estilo and isinstance(estilo, str) and estilo.strip():
        linhas.append(f"\nESTILO E FORMATO DOS EXERCÍCIOS:\n  - {estilo.strip()}")
        
    # 5. Outras Diretrizes
    outras = override_dict.get("outras_diretrizes")
    if outras and isinstance(outras, str) and outras.strip():
        linhas.append(f"\nOUTRAS DIRETRIZES E INSTRUÇÕES ESPECÍFICAS:\n  - {outras.strip()}")
        
    linhas.append("\n[FIM DO OVERRIDE DE DIRETRIZES DO PROFESSOR]\n")
    return "\n".join(linhas)
