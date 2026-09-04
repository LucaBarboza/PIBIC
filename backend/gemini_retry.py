import time
import os

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
    Executa uma função de chamada ao Gemini/Vertex com política robusta de retentativas e progressive backoff.
    Para erros 429 / RESOURCE_EXHAUSTED: espera (tentativa + 1) * 5 segundos (5s, 10s, 15s, 20s, 25s).
    Para erros 503 / UNAVAILABLE: espera 5 segundos.
    """
    for tentativa in range(max_retries):
        try:
            t0 = time.time()
            res = chamada_fn()
            t_elapsed = time.time() - t0
            
            if tracker and modelo:
                try:
                    tracker.registrar_chamada(
                        nome_agente=nome_agente,
                        modelo=modelo,
                        response=res,
                        tempo_s=t_elapsed
                    )
                except Exception as e_track:
                    print(f" [AVISO TRACKER] Falha ao registrar telemetria: {e_track}")
                    
            return res
        except Exception as e:
            erro_str = str(e)
            is_429 = "429" in erro_str or "RESOURCE_EXHAUSTED" in erro_str or "quota" in erro_str.lower()
            is_503 = "503" in erro_str or "UNAVAILABLE" in erro_str
            
            if tentativa == max_retries - 1:
                msg_final = f"[{nome_agente}] Falha definitiva em '{descricao}' após {max_retries} tentativas: {erro_str}"
                print(f" [ERRO CRÍTICO] {msg_final}")
                if logger:
                    logger.log(msg_final, "error")
                raise e
                
            if is_429:
                tempo_espera = (tentativa + 1) * 5  # 5s, 10s, 15s, 20s, 25s
                msg = f"[{nome_agente}] Limite de cota (429) em '{descricao}'. Aguardando {tempo_espera}s antes da tentativa {tentativa + 2}/{max_retries}..."
                print(f" [AVISO 429] {msg}")
                if logger:
                    logger.log(msg, "warning")
                time.sleep(tempo_espera)
            elif is_503:
                tempo_espera = 5
                msg = f"[{nome_agente}] Serviço indisponível (503) em '{descricao}'. Aguardando {tempo_espera}s antes da tentativa {tentativa + 2}/{max_retries}..."
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
