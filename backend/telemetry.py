import time
from typing import Dict, List, Any, Optional

# Tabela Oficial Google AI Studio (Preço por 1 Milhão de Tokens em USD)
PRECOS_MODELOS = {
    "gemini-3.5-flash-lite": {
        "prompt": 0.30 / 1_000_000,
        "completion": 2.50 / 1_000_000,
        "nome_display": "Gemini 3.5 Flash-Lite"
    },
    "gemini-3.6-flash": {
        "prompt": 1.50 / 1_000_000,
        "completion": 7.50 / 1_000_000,
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

CAMBIO_BRL = 5.50  # Taxa de conversão USD -> BRL

def resolver_modelo(agente: str = "", modo_llm: str = "3.5") -> str:
    """
    Retorna o modelo de IA oficial padrão: Gemini 3.5 Flash-Lite para 100% dos agentes,
    garantindo velocidade máxima e custo mínimo.
    """
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

    def registrar_chamada(
        self,
        nome_agente: str,
        modelo: str,
        response: Optional[Any] = None,
        tempo_s: float = 0.0,
        prompt_tokens: int = 0,
        candidates_tokens: int = 0
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
        tabela = PRECOS_MODELOS.get(modelo_key, PRECOS_MODELOS["gemini-2.5-flash"])
        
        custo_p_usd = p_tok * tabela["prompt"]
        custo_c_usd = c_tok * tabela["completion"]
        custo_call_usd = custo_p_usd + custo_c_usd
        custo_call_brl = custo_call_usd * CAMBIO_BRL

        self.total_tokens_prompt += p_tok
        self.total_tokens_resposta += c_tok
        self.total_tokens += t_tok
        self.custo_total_usd += custo_call_usd
        self.custo_total_brl += custo_call_brl

        self.chamadas.append({
            "agente": nome_agente,
            "modelo": modelo_key,
            "nome_modelo": tabela["nome_display"],
            "tokens_prompt": p_tok,
            "tokens_resposta": c_tok,
            "tokens_total": t_tok,
            "tempo_segundos": round(tempo_s, 2),
            "custo_usd": round(custo_call_usd, 6),
            "custo_brl": round(custo_call_brl, 4)
        })

    def obter_resumo(self) -> Dict[str, Any]:
        tempo_total = round(time.time() - self.t_inicio, 1)
        modo_label = "Gemini 3.6 Flash (Escrita) + 3.5 Flash-Lite (Apoio)"
        
        return {
            "modo_utilizado": str(self.modo_llm),
            "modo_label": modo_label,
            "tempo_total_segundos": tempo_total,
            "tokens_prompt": self.total_tokens_prompt,
            "tokens_resposta": self.total_tokens_resposta,
            "tokens_total": self.total_tokens,
            "custo_total_usd": round(self.custo_total_usd, 5),
            "custo_total_brl": round(self.custo_total_brl, 4),
            "custo_formatado_brl": f"R$ {self.custo_total_brl:.3f}" if self.custo_total_brl < 1.0 else f"R$ {self.custo_total_brl:.2f}",
            "custo_formatado_usd": f"${self.custo_total_usd:.4f}",
            "cambio_usd_brl": CAMBIO_BRL,
            "total_chamadas_agentes": len(self.chamadas),
            "detalhe_agentes": self.chamadas
        }
