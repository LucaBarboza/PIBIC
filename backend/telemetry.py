import time
from typing import Dict, List, Any, Optional

# Tabela Oficial Google AI Studio (Preço por 1 Milhão de Tokens em USD)
PRECOS_MODELOS = {
    "gemini-3.5-flash-lite": {
        "prompt": 0.10 / 1_000_000,      # $0.10 por 1M tokens de entrada
        "completion": 0.40 / 1_000_000,  # $0.40 por 1M tokens de saída
        "nome_display": "Gemini 3.5 Flash-Lite"
    },
    "gemini-3.6-flash": {
        "prompt": 0.30 / 1_000_000,      # $0.30 por 1M tokens de entrada
        "completion": 2.50 / 1_000_000,  # $2.50 por 1M tokens de saída
        "nome_display": "Gemini 3.6 Flash"
    },
    "gemini-2.5-flash": {
        "prompt": 0.30 / 1_000_000,
        "completion": 2.50 / 1_000_000,
        "nome_display": "Gemini 2.5 Flash"
    },
    "gemini-2.5-pro": {
        "prompt": 1.25 / 1_000_000,
        "completion": 10.00 / 1_000_000,
        "nome_display": "Gemini 2.5 Pro"
    }
}

CAMBIO_BRL = 5.70  # Taxa de conversão USD -> BRL (Dólar Comercial)

def resolver_modelo(agente: str = "", modo_llm: str = "3.5") -> str:
    """
    Retorna o modelo de IA oficial para cada agente:
    - Macro-Roteirista, Orquestrador Editorial e Simulador Interativo: Gemini 3.6 Flash ("Pro" para raciocínio visual e inteligência estrutural)
    - Escritores, Revisor, Exercícios, Validador KaTeX: Gemini 3.5 Flash-Lite (velocidade e 500 RPD)
    """
    agente_norm = (agente or "").lower().replace("-", "_").replace(" ", "_")
    if any(k in agente_norm for k in ["macro_roteirista", "macroroteirista", "orquestrador", "simulador", "engenheiro_simulacao"]):
        return "gemini-3.6-flash"
    return "gemini-3.5-flash-lite"

class TokenTracker:
    def __init__(self, modo_llm: str = "hibrido"):
        self.modo_llm = modo_llm
        self.t_inicio = time.time()
        self.chamadas: List[Dict[str, Any]] = []
        self.total_tokens_prompt = 0
        self.total_tokens_resposta = 0
        self.total_tokens = 0
        self.custo_total_usd = 0.0
        self.custo_total_brl = 0.0
        self.total_economia_brl = 0.0

    def registrar_chamada(
        self,
        nome_agente: str,
        modelo: str,
        response: Optional[Any] = None,
        tempo_s: float = 0.0,
        prompt_tokens: int = 0,
        candidates_tokens: int = 0,
        tier: str = "free"
    ):
        p_tok = prompt_tokens
        c_tok = candidates_tokens

        if response and hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            p_tok = getattr(um, "prompt_token_count", 0) or 0
            c_tok = getattr(um, "candidates_token_count", 0) or 0

        t_tok = p_tok + c_tok
        
        # Obter taxa do modelo
        modelo_key = modelo.replace("models/", "").strip()
        tabela = PRECOS_MODELOS.get(modelo_key, PRECOS_MODELOS["gemini-3.5-flash-lite"])
        
        custo_teorico_usd = (p_tok * tabela["prompt"]) + (c_tok * tabela["completion"])
        custo_teorico_brl = custo_teorico_usd * CAMBIO_BRL

        if tier == "free":
            custo_call_usd = 0.0
            custo_call_brl = 0.0
            economia_call_brl = custo_teorico_brl
            self.total_economia_brl += economia_call_brl
        else:
            custo_call_usd = custo_teorico_usd
            custo_call_brl = custo_teorico_brl
            economia_call_brl = 0.0

        self.total_tokens_prompt += p_tok
        self.total_tokens_resposta += c_tok
        self.total_tokens += t_tok
        self.custo_total_usd += custo_call_usd
        self.custo_total_brl += custo_call_brl

        self.chamadas.append({
            "agente": nome_agente,
            "modelo": modelo_key,
            "nome_modelo": tabela["nome_display"],
            "tier": tier,
            "is_gratuito": (tier == "free"),
            "tokens_prompt": p_tok,
            "tokens_resposta": c_tok,
            "tokens_total": t_tok,
            "tempo_segundos": round(tempo_s, 2),
            "custo_usd": round(custo_call_usd, 6),
            "custo_brl": round(custo_call_brl, 4),
            "economia_brl": round(economia_call_brl, 4)
        })

    def obter_resumo(self) -> Dict[str, Any]:
        tempo_total = round(time.time() - self.t_inicio, 1)
        
        if self.custo_total_brl == 0.0:
            custo_formatado = "R$ 0,00"
            modo_label = "Gemini 3.5 Flash-Lite & 3.6 Flash (100% Gratuito)"
        else:
            custo_formatado = f"R$ {self.custo_total_brl:.2f}"
            modo_label = f"Gemini 3.5 & 3.6 Flash (Fallback Pago: R$ {self.custo_total_brl:.2f})"
        
        return {
            "modo_utilizado": str(self.modo_llm),
            "modo_label": modo_label,
            "tempo_total_segundos": tempo_total,
            "tokens_prompt": self.total_tokens_prompt,
            "tokens_resposta": self.total_tokens_resposta,
            "tokens_total": self.total_tokens,
            "custo_total_usd": round(self.custo_total_usd, 5),
            "custo_total_brl": round(self.custo_total_brl, 4),
            "total_economia_brl": round(self.total_economia_brl, 4),
            "custo_formatado_brl": custo_formatado,
            "custo_formatado_usd": f"${self.custo_total_usd:.4f}",
            "cambio_usd_brl": CAMBIO_BRL,
            "total_chamadas_agentes": len(self.chamadas),
            "detalhe_agentes": self.chamadas
        }
