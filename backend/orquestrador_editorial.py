import os
import json
import re
from google import genai
from google.genai import types
from schemas import AulaUnificadaELapidada
from client_factory import get_genai_client

# ==============================================================================
# FALLBACK DE SEGURANÇA PARA A CHAVE DE API (GEMINI_API_KEY)
# ==============================================================================
def carregar_chave_api():
    """Garante a leitura da API key a partir do ambiente, do st.secrets (Streamlit Cloud) ou do secrets.toml local."""
    if "GEMINI_API_KEY" in os.environ and os.environ["GEMINI_API_KEY"].strip():
        return True
        
    # Tenta obter do st.secrets do Streamlit
    try:
        import streamlit as st
        if "GEMINI_API_KEY" in st.secrets:
            val = st.secrets["GEMINI_API_KEY"]
            if val and val.strip():
                os.environ["GEMINI_API_KEY"] = val.strip()
                return True
    except Exception:
        pass
        
    path = os.path.join(".streamlit", "secrets.toml")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for linha in f:
                    if "GEMINI_API_KEY" in linha:
                        match = re.search(r'(?:GEMINI_API_KEY\s*=\s*["\'])(.*?)(?:["\'])', linha)
                        if match:
                            os.environ["GEMINI_API_KEY"] = match.group(1).strip()
                            print(f"[KEY] Chave de API carregada com sucesso a partir de '{path}'.")
                            return True
        except Exception as e:
            print(f"[ALERTA] Erro ao tentar ler {path}: {e}")
    return False

def lapidar_conteudo_global(payload_bruto: dict, logger=None):
    client = get_genai_client()

    dados_entrada_str = json.dumps(payload_bruto, ensure_ascii=False)

    print("\n[Agente 3.5] Assumindo o controle editorial. Unificando e eliminando repetições da aula...")

    from prompts import PROMPT_ORQUESTRADOR
    prompt_editorial = PROMPT_ORQUESTRADOR.replace("[CAPÍTULO_BRUTO_AULA]", dados_entrada_str)

    config_editorial = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=AulaUnificadaELapidada
    )

    from gemini_retry import executar_chamada_com_retry

    try:
        if logger:
            logger.update_agent("orquestrador", "rodando", prompt=prompt_editorial)
            logger.log("Orquestrador Editorial: Revisando coerência de ponta a ponta...", "info")
            
        def chamar_orquestrador():
            return client.models.generate_content(
                model="gemini-pro-latest",
                contents=[dados_entrada_str, prompt_editorial],
                config=config_editorial
            )

        resposta = executar_chamada_com_retry(
            chamar_orquestrador,
            max_retries=5,
            logger=logger,
            nome_agente="Orquestrador",
            descricao="lapidação global da aula"
        )
        
        if logger:
            logger.update_agent("orquestrador", "concluido", resposta=resposta.text)
            logger.log("Orquestrador Editorial: Lapidação concluída.", "success")

        print(" [OK] Aula unificada, referências compiladas no rodapé e livre de repetições!")
        
        return json.loads(resposta.text)

    except Exception as e:
        print(f" [ERRO] Erro crítico no processo editorial: {e}")
        if logger:
            logger.update_agent("orquestrador", "erro")
            logger.log(f"Orquestrador Editorial: Falha ao gerar aula unificada - {str(e)}", "error")
            
        # Tenta salvar o progresso mapeando a chave antiga para a nova para não quebrar os agentes paralelos
        if "conteudo_paginas" in payload_bruto:
            payload_bruto["paginas_conteudo"] = payload_bruto.pop("conteudo_paginas")
            
        return payload_bruto

def formatar_latex_final(aula_json: dict, client) -> dict:
    from prompts import PROMPT_FORMATADOR_LATEX
    print("\n[Formatador LaTeX] Inspecionando e corrigindo delimitadores matemáticos...")
    
    config_formatador = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=AulaUnificadaELapidada
    )
    
    try:
        dados_str = json.dumps(aula_json, ensure_ascii=False)
        resposta_formatada = client.models.generate_content(
            model="gemini-pro-latest",
            contents=[dados_str, PROMPT_FORMATADOR_LATEX],
            config=config_formatador
        )
        print(" [OK] LaTeX validado e formatado com sucesso!")
        return json.loads(resposta_formatada.text)
    except Exception as e:
        print(f" [ERRO] Falha ao formatar LaTeX. Retornando a versão sem correção extra. Erro: {e}")
        return aula_json

def expandir_subtopico_para_prosa_livro(dados_subtopico: dict) -> str:
    client = get_genai_client()
    
    from prompts import PROMPT_PROFESSOR_EXPANSOR, DICIONARIO_LATEX
    prompt = PROMPT_PROFESSOR_EXPANSOR.replace("{dicionario_latex}", DICIONARIO_LATEX)
    
    resposta = client.models.generate_content(
        model="gemini-pro-latest",
        contents=[json.dumps(dados_subtopico, ensure_ascii=False), prompt],
        config=types.GenerateContentConfig(
            response_mime_type="text/plain"
        )
    )
    return resposta.text.strip()

if __name__ == "__main__":
    print("[AVISO] O processo editorial deve ser executado a partir da interface do Streamlit.")
    print("Por favor, execute o comando: streamlit run app.py")
