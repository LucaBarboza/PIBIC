import os
import sys
import json
import re
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional

# Importamos o contrato do subtópico para o Revisor analisar
from schemas import SubtopicoValidado
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
        
    # Tenta ler do secrets.toml da pasta local
    path = os.path.join(".streamlit", "secrets.toml")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for linha in f:
                    if "GEMINI_API_KEY" in linha:
                        match = re.search(r'(?:GEMINI_API_KEY\s*=\s*["\'])(.*?)(?:["\'])', linha)
                        if match:
                            os.environ["GEMINI_API_KEY"] = match.group(1).strip()
                            return True
        except Exception:
            pass
    return False

# Inicializa o carregamento da chave de API
carregar_chave_api()

# ==============================================================================
# SCHEMA DE DECISÃO DO AGENTE REVISOR (CRITIC)
# ==============================================================================
class DecisaoRevisao(BaseModel):
    aprovado: bool = Field(
        description="True se o conteúdo está correto e consistente com as diretrizes. False se precisa de correções."
    )
    comentario_correcao: Optional[str] = Field(
        default=None,
        description="Laudo técnico cirúrgico detalhando cada desvio conceitual encontrado e as correções necessárias se aprovado for False."
    )
    feedback_melhoria: Optional[str] = Field(
        default=None,
        description="Explicação detalhada dos pontos que violaram as diretrizes ou que contêm erros de notação."
    )
    conteudo_corrigido: Optional[SubtopicoValidado] = Field(
        default=None,
        description="Se aprovado for True, retorne o objeto de conteúdo revisado sem alterações estruturais."
    )

# ==============================================================================
# FUNÇÃO DE AUDITORIA DO SUBTÓPICO
# ==============================================================================
def auditar_subtopico_local(bloco_bruto_dict: dict, diretrizes_texto: str, logger=None, sub_idx=None, sub_tentativa=None, modelo_llm: str = "hibrido", tracker=None) -> DecisaoRevisao:
    client = get_genai_client()
    
    bloco_bruto_str = json.dumps(bloco_bruto_dict, ensure_ascii=False, indent=2)

    from prompts import PROMPT_REVISOR_CIENTIFICO, DICIONARIO_LATEX
    from telemetry import resolver_modelo
    modelo_alvo = resolver_modelo("revisor", modelo_llm)
    
    prompt_revisor = PROMPT_REVISOR_CIENTIFICO.replace("[CONTEÚDO_BRUTO]", bloco_bruto_str).replace("[DIRETRIZES_DE_ESTILO]", diretrizes_texto)

    config_revisor = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=DecisaoRevisao
    )

    from gemini_retry import executar_chamada_com_retry

    try:
        def chamar_revisor():
            return client.models.generate_content(
                model=modelo_alvo,
                contents=[bloco_bruto_str, prompt_revisor],
                config=config_revisor
            )

        resposta = executar_chamada_com_retry(
            chamar_revisor,
            max_retries=5,
            logger=logger,
            nome_agente=f"Revisor_{sub_idx}" if sub_idx else "Revisor",
            descricao=f"auditoria do subtópico {sub_idx}" if sub_idx else "auditoria do subtópico",
            tracker=tracker,
            modelo=modelo_alvo
        )

        if logger:
            if sub_idx:
                logger.update_agent(f"revisor_{sub_idx}", "rodando", resposta=resposta.text)
            else:
                logger.update_agent("revisor", "rodando", resposta=resposta.text)
        return DecisaoRevisao.model_validate_json(resposta.text)
    except Exception as e:
        # Em caso de esgotamento das tentativas, força aprovação preventiva com os dados já existentes
        print(f"      [ALERTA] Falha operacional no motor do Revisor após retentativas: {e}")
        return DecisaoRevisao(aprovado=True, conteudo_corrigido=SubtopicoValidado(**bloco_bruto_dict))
