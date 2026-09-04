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

def extrair_regras_override(texto_documento: str, logger=None) -> Optional[Dict]:
    """
    Lê o texto/documento de notações/diretrizes do professor e usa o Gemini 2.5 Flash
    com Structured Output (schema RegraOverride) para retornar as regras estruturadas.
    """
    if not texto_documento or not texto_documento.strip():
        return None
        
    from gemini_retry import executar_chamada_com_retry

    try:
        client = get_genai_client()
        
        prompt = PROMPT_EXTRATOR.format(texto_documento=texto_documento)
        
        if logger:
            logger.update_agent("extrator", "rodando", prompt=prompt)
            logger.log("Agente Extrator: Lendo notações, tom e diretrizes específicas...", "info")
            
        def chamar_extrator():
            return client.models.generate_content(
                model="gemini-2.5-flash",
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
            descricao="extração de notações e diretrizes"
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
