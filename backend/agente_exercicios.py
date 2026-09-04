import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv
from schemas import CadernoExerciciosValidado
from client_factory import get_genai_client

def carregar_chave_api():
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")

PROMPT_CRIADOR_EXERCICIOS = """
Você é um Professor Titular e elaborador chefe de exames (Banca Examinadora) em uma universidade de ponta.
Sua missão é ler o conteúdo de uma aula recém-criada e elaborar um caderno de exercícios rigoroso, desafiador e perfeitamente alinhado ao material didático.

[CONTEXTO DA AULA]
{conteudo_aula}

[DIRETRIZES PARA OS EXERCÍCIOS]
1. As questões de múltipla escolha devem apresentar cenários práticos (aplicação da teoria) em vez de apenas memorização de fórmulas.
2. Cada questão fechada deve ter uma "dica" estratégica e um "gabarito_comentado" extenso e detalhado.
3. As questões discursivas (abertas) devem ser complexas, exigindo cálculos em múltiplas etapas ou deduções baseadas na teoria ensinada.
4. O gabarito das questões discursivas DEVE ser passo a passo e utilizar formatação matemática rigorosa (LaTeX) quando houver cálculo.
5. Assegure que não há ambiguidades nas alternativas e que a alternativa correta seja matematicamente inquestionável.
"""

def gerar_caderno_exercicios(conteudo_aula_json: dict, logger=None, modelo_llm="2.5", diretrizes_override=None) -> dict:
    """
    Recebe a aula unificada e lapidada e gera o Caderno de Exercícios correspondente,
    garantindo a saída como um dicionário JSON compatível com o schema CadernoExerciciosValidado.
    """
    client = get_genai_client()
    target_model = "gemini-pro-latest" if str(modelo_llm) == "pro" else "gemini-3.5-flash-lite"
    
    # Reduzindo o conteúdo apenas para os textos essenciais para economizar tokens
    resumo_aula = f"Tema: {conteudo_aula_json.get('tema_global', 'Aula')}\n"
    for idx, pag in enumerate(conteudo_aula_json.get("paginas_conteudo", [])):
        resumo_aula += f"\n--- Tópico {idx+1}: {pag.get('titulo_subtopico')} ---\n"
        resumo_aula += f"{pag.get('discussao_teorica_prosa', '')[:1000]}...\n" # pega um pedaço do conceito para balizar o modelo
        resumo_aula += f"Fórmula principal: {pag.get('formalismo_latex', 'N/A')}\n"

    prompt = PROMPT_CRIADOR_EXERCICIOS.format(conteudo_aula=resumo_aula)
    if diretrizes_override:
        prompt = f"{diretrizes_override}\n\n{prompt}"
    
    print(f"\n[Agente de Exercícios ({target_model})] Elaborando caderno de exercícios para '{conteudo_aula_json.get('tema_global', 'Aula')}'...")
    
    from gemini_retry import executar_chamada_com_retry

    try:
        if logger:
            logger.update_agent("exercicios", "rodando", prompt=prompt)
            logger.log(f"Agente de Exercícios ({target_model}): Elaborando caderno rigoroso...", "info")
        
        def chamar_exercicios():
            return client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CadernoExerciciosValidado
                )
            )

        resposta = executar_chamada_com_retry(
            chamar_exercicios,
            max_retries=5,
            logger=logger,
            nome_agente="Exercícios",
            descricao="elaboração do caderno de exercícios"
        )
        
        import latex_sanitizer
        caderno_dict = json.loads(resposta.text)
        caderno_dict = latex_sanitizer.sanitize_json_recursively(caderno_dict)
        
        if logger:
            logger.update_agent("exercicios", "concluido", resposta=resposta.text)
            logger.log("Agente de Exercícios: Caderno gerado com sucesso.", "success")
            
        print(" [OK] Caderno de Exercícios gerado com sucesso!")
        return caderno_dict
        
    except Exception as e:
        msg_erro = f"Falha definitiva ao gerar exercícios: {str(e)}"
        print(f" [ERRO] {msg_erro}")
        if logger:
            logger.update_agent("exercicios", "erro")
            logger.log(f"Agente de Exercícios: Falha - {msg_erro}", "error")
        return None


if __name__ == "__main__":
    # Teste rápido
    dummy_aula = {
        "tema_global": "Introdução à Probabilidade",
        "paginas_conteudo": [
            {
                "titulo_subtopico": "Conceitos Básicos",
                "discussao_teorica_prosa": "A probabilidade mede a chance de um evento...",
                "formalismo_latex": "P(A) = \\frac{n(A)}{n(\\Omega)}"
            }
        ]
    }
    resultado = gerar_caderno_exercicios(dummy_aula)
    if resultado:
        print("Múltipla Escolha geradas:", len(resultado.get("questoes_multipla_escolha", [])))
        print("Abertas geradas:", len(resultado.get("questoes_discursivas", [])))
