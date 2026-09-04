import time
import os
from client_factory import get_genai_client

def executar_chamada_com_retry(
    chamada_fn,
    max_retries: int = 5,
    logger = None,
    nome_agente: str = "Agente",
    descricao: str = "requisição",
    tracker = None,
    modelo: str = ""
):
    """
    Executa uma função de chamada ao Gemini com política de retentativas e Failover Multi-Chave:
    1. Inicia na Chave Gratuita Primária (Custo R$ 0,00).
    2. Se erro 503 ocorrer 3 vezes consecutivas na chave gratuita: failover imediato para a Chave Paga.
    3. Se erro 429 (cota esgotada) ocorrer na chave gratuita: failover imediato para a Chave Paga.
    4. Registra na telemetria se a chamada foi gratuita ou paga.
    """
    client_mgr = get_genai_client()

    for tentativa in range(max_retries):
        try:
            tier_antes = client_mgr.get_active_tier()
            t0 = time.time()
            res = chamada_fn()
            t_elapsed = time.time() - t0
            
            # Reset de contador de 503 ao ter sucesso
            client_mgr.consecutive_503_count = 0
            
            if tracker and modelo:
                try:
                    tracker.registrar_chamada(
                        nome_agente=nome_agente,
                        modelo=modelo,
                        response=res,
                        tempo_s=t_elapsed,
                        tier=tier_antes
                    )
                except Exception as e_track:
                    print(f" [AVISO TRACKER] Falha ao registrar telemetria: {e_track}")
                    
            return res
        except Exception as e:
            erro_str = str(e)
            is_429 = "429" in erro_str or "RESOURCE_EXHAUSTED" in erro_str or "quota" in erro_str.lower()
            is_503 = "503" in erro_str or "UNAVAILABLE" in erro_str
            current_tier = client_mgr.get_active_tier()

            # --- FAILOVER INTELIGENTE PARA 503 (Instabilidade de Servidor) ---
            if is_503:
                client_mgr.consecutive_503_count += 1
                if client_mgr.consecutive_503_count >= 3 and current_tier == "free" and client_mgr.is_paid_available():
                    msg_failover = f"[{nome_agente}] Erro 503 do servidor ocorreu 3 vezes na chave gratuita. Alternando automaticamente para a Chave Paga (Fallback)..."
                    print(f" [FAILOVER 503] {msg_failover}")
                    if logger:
                        logger.log(msg_failover, "warning")
                    client_mgr.switch_to_paid(reason="3x 503 de instabilidade do servidor na chave gratuita")
                    time.sleep(1)
                    continue

            # --- FAILOVER INTELIGENTE PARA 429 (Cota / Rate Limit) ---
            if is_429 and current_tier == "free" and client_mgr.is_paid_available():
                # Se for 3.6 Flash (cota de 20 RPD) ou repetição de 429, faz failover imediato para a chave paga
                if "3.6-flash" in modelo or "per day" in erro_str.lower() or "daily" in erro_str.lower() or tentativa >= 1:
                    msg_failover = f"[{nome_agente}] Cota da chave gratuita esgotada no modelo {modelo}. Alternando imediatamente para a Chave Paga (Fallback)..."
                    print(f" [FAILOVER 429] {msg_failover}")
                    if logger:
                        logger.log(msg_failover, "warning")
                    client_mgr.switch_to_paid(reason=f"429 Quota Exceeded ({modelo}) na chave gratuita")
                    time.sleep(1)
                    continue

            if tentativa == max_retries - 1:
                msg_final = f"[{nome_agente}] Falha definitiva em '{descricao}' após {max_retries} tentativas: {erro_str}"
                print(f" [ERRO CRÍTICO] {msg_final}")
                if logger:
                    logger.log(msg_final, "error")
                raise e
                
            if is_429:
                tempo_espera = (tentativa + 1) * 4  # 4s, 8s, 12s, 16s
                msg = f"[{nome_agente}] Limite de cota (429) em '{descricao}' (Tier {current_tier.upper()}). Aguardando {tempo_espera}s antes da tentativa {tentativa + 2}/{max_retries}..."
                print(f" [AVISO 429] {msg}")
                if logger:
                    logger.log(msg, "warning")
                time.sleep(tempo_espera)
            elif is_503:
                tempo_espera = 4
                msg = f"[{nome_agente}] Serviço indisponível (503) em '{descricao}' (Tentativa {client_mgr.consecutive_503_count}/3 no tier {current_tier.upper()}). Aguardando {tempo_espera}s..."
                print(f" [AVISO 503] {msg}")
                if logger:
                    logger.log(msg, "warning")
                time.sleep(tempo_espera)
            else:
                tempo_espera = (tentativa + 1) * 3
                msg = f"[{nome_agente}] Falha em '{descricao}': {erro_str}. Retentando em {tempo_espera}s (tentativa {tentativa + 2}/{max_retries})..."
                print(f" [AVISO] {msg}")
                if logger:
                    logger.log(msg, "warning")
                time.sleep(tempo_espera)

