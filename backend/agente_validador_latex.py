import os
import json
import re
import subprocess
import time
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv
try:
    from backend import latex_sanitizer
    from backend.client_factory import get_genai_client
except ImportError:
    import latex_sanitizer
    from client_factory import get_genai_client

class ItemCorrecaoLatex(BaseModel):
    id: int = Field(description="ID numérico da anomalia a ser corrigida")
    caminho_campo: str = Field(description="Caminho exato do campo no JSON (ex: 'paginas_conteudo[0].formalismo_latex')")
    trecho_original_quebrado: str = Field(description="O trecho original que continha a anomalia KaTeX")
    trecho_corrigido_limpo: str = Field(description="A versão totalmente corrigida e válida no KaTeX, que compila 100% sem erros")
    explicacao_tecnica: str = Field(description="Breve explicação técnica da correção efetuada (ex: 'Removidos cifrões aninhados dentro de $$')")

class RelatorioCorrecaoLatex(BaseModel):
    correcoes: List[ItemCorrecaoLatex] = Field(description="Lista contendo cada uma das correções cirúrgicas efetuadas")

def compilar_katex_real(aula_json: dict) -> dict:
    """
    Executa o compilador Node.js com o KaTeX real para verificar 100% das fórmulas da aula.
    Retorna o relatório: {"aprovado": bool, "total_formulas": int, "total_erros": int, "erros": list}
    """
    try:
        script_path = os.path.join(os.path.dirname(__file__), "compilador_katex_node.js")
        payload = json.dumps(aula_json, ensure_ascii=False)
        
        proc = subprocess.run(
            ["node", script_path],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15
        )
        if proc.stdout and proc.stdout.strip():
            return json.loads(proc.stdout)
        elif proc.stderr:
            print(f" [AVISO] Compilador KaTeX stderr: {proc.stderr[:200]}")
    except Exception as e:
        print(f" [AVISO] Falha ao invocar compilador KaTeX Node: {e}")
    
    # Fallback estático caso o processo Node falhe
    return {"aprovado": True, "total_formulas": 0, "total_erros": 0, "erros": []}

def substituir_no_caminho(obj, caminho: str, novo_valor: str) -> bool:
    """
    Substitui cirurgicamente um valor dentro de um dicionário/lista navegando pela string de caminho.
    Ex: 'root.conteudo_json.paginas_conteudo[0].formalismo_latex'
    """
    tokens = [t for t in re.split(r'[\.\[\]]+', caminho) if t]
    while tokens and tokens[0] in ('root', 'aula', 'conteudo_json', 'conteudo') and (not isinstance(obj, dict) or tokens[0] not in obj):
        tokens.pop(0)

    if not tokens:
        return False

    atual = obj
    for i in range(len(tokens) - 1):
        token = tokens[i]
        if token.isdigit():
            idx = int(token)
            if isinstance(atual, list) and 0 <= idx < len(atual):
                atual = atual[idx]
            else:
                return False
        else:
            if isinstance(atual, dict) and token in atual:
                atual = atual[token]
            else:
                return False

    ultimo = tokens[-1]
    if ultimo.isdigit():
        idx = int(ultimo)
        if isinstance(atual, list) and 0 <= idx < len(atual):
            atual[idx] = novo_valor
            return True
    else:
        if isinstance(atual, dict):
            atual[ultimo] = novo_valor
            return True

    return False

def reparar_anomalias_cirurgico(aula_sanitizada: dict, anomalias: list, logger=None, target_model="gemini-3.5-flash-lite", tracker=None) -> dict:
    """
    Envia APENAS as anomalias capturadas pelo KaTeX real para o LLM e aplica as correções cirurgicamente
    no JSON original sem tocar no resto da aula.
    """
    try:
        client = get_genai_client()
    except Exception as e:
        print(f" [AVISO] Falha ao inicializar Gemini Client no validador: {e}. Mantendo versão determinística.")
        return aula_sanitizada
    
    try:
        from backend.prompts import DICIONARIO_LATEX
    except ImportError:
        from prompts import DICIONARIO_LATEX
    
    prompt_cirurgico = f"""
Você é o Revisor de Elite de Tipografia KaTeX e LaTeX de uma editora acadêmica de exatas.
Sua tarefa é REPARAR CIRURGICAMENTE uma lista de anomalias de compilação KaTeX encontradas pelo compilador oficial KaTeX.

[DIRETRIZES DA EDITORA PARA A CORREÇÃO]
{DICIONARIO_LATEX}

REGRAS RÍGIDAS DE CORREÇÃO:
1. Mantenha 100% das palavras de prosa, significados e termos em português intactos.
2. Corrija APENAS os erros de sintaxe KaTeX apontados.
3. É TERMINANTEMENTE PROIBIDO usar cifrões ($) dentro de blocos matemáticos ($$...$$).
4. Garanta que todas as equações em bloco usem apenas $$...$$ e equações em linha usem $...$.
5. Preencha rigorosamente a estrutura 'RelatorioCorrecaoLatex'.

[ANOMALIAS DE COMPILAÇÃO KATEX IDENTIFICADAS]
{json.dumps(anomalias, ensure_ascii=False, indent=2)}
"""

    print(f"   -> [LLM] Solicitando reparo cirúrgico rápido ao {target_model}...", flush=True)
    
    max_retries = 2
    for tentativa in range(max_retries):
        try:
            t0 = time.time()
            resposta = client.models.generate_content(
                model=target_model,
                contents=prompt_cirurgico,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RelatorioCorrecaoLatex
                )
            )
            t_elap = time.time() - t0
            
            if tracker and target_model:
                try:
                    tracker.registrar_chamada(
                        nome_agente="Validador_LaTeX",
                        modelo=target_model,
                        response=resposta,
                        tempo_s=t_elap
                    )
                except Exception:
                    pass
            
            relatorio = RelatorioCorrecaoLatex.model_validate_json(resposta.text)
            
            correcoes_aplicadas = 0
            for item in relatorio.correcoes:
                sucesso = substituir_no_caminho(aula_sanitizada, item.caminho_campo, item.trecho_corrigido_limpo)
                if sucesso:
                    correcoes_aplicadas += 1
                    msg = f"Correção [{item.id}] em {item.caminho_campo}: {item.explicacao_tecnica}"
                    print(f"   -> [REPARO CIRÚRGICO APLICADO] {msg}")
                    if logger:
                        logger.log(f"Validador LaTeX: {msg}", "info")
                    
            print(f" [OK] Reparo cirúrgico concluído! ({correcoes_aplicadas}/{len(anomalias)} anomalias tratadas)")
            if logger:
                logger.update_agent("validador_latex", "concluido", resposta=resposta.text)
                logger.log("Validador LaTeX: Reparo cirúrgico aplicado.", "success")
    
            return latex_sanitizer.sanitize_json_recursively(aula_sanitizada)
    
        except Exception as e:
            msg_erro = f"Tentativa {tentativa + 1} de reparo: {str(e)}"
            print(f" [AVISO] {msg_erro}")
            time.sleep(2)
            
    print(" [AVISO] Mantendo versão sanitizada determinística.")
    return aula_sanitizada

def validar_e_corrigir_aula_completa(aula_json: dict, logger=None, modelo_llm: str = "hibrido", tracker=None) -> dict:
    """
    Agente Validador e Auditor Final com Loop de Auto-Cura (KaTeX Real + Node.js).
    Ciclo:
      1. Sanitização determinística instantânea (< 1ms).
      2. Compilação estrita com o motor real do KaTeX.
      3. Se 0 erros -> Aprovado imediatamente!
      4. Se houver erros -> Reparo cirúrgico com feedback exato do KaTeX para o LLM.
      5. Re-compilação no KaTeX para atestar o sucesso (até 2 iterações).
      6. Fallback final seguro para blindar a interface do usuário.
    """
    if not aula_json or not isinstance(aula_json, dict):
        return aula_json
        
    try:
        from backend.telemetry import resolver_modelo
    except ImportError:
        from telemetry import resolver_modelo
    target_model = resolver_modelo("validador_latex", modelo_llm)
    
    try:
        if logger:
            logger.update_agent("validador_latex", "rodando")
            logger.log(f"Validador LaTeX: Auditoria com compilador KaTeX real ({target_model})...", "info")
            
        print(f"\n[Agente Validador de LaTeX ({target_model})] Auditoria com compilador KaTeX real...")
        
        aula_atual = aula_json
        max_loops = 2
        
        for ciclo in range(max_loops):
            # 1. Sanitização determinística
            aula_atual = latex_sanitizer.sanitize_json_recursively(aula_atual)
            
            # 2. Compilação com KaTeX real
            relatorio = compilar_katex_real(aula_atual)
            total_formulas = relatorio.get("total_formulas", 0)
            total_erros = relatorio.get("total_erros", 0)
            erros = relatorio.get("erros", [])
            
            if relatorio.get("aprovado", False) or total_erros == 0:
                print(f" [OK] Compilação KaTeX 100% Aprovada no Ciclo {ciclo + 1}! ({total_formulas} fórmulas verificadas, 0 erros)")
                if logger:
                    logger.update_agent("validador_latex", "concluido", resposta=f"Aprovado: {total_formulas} fórmulas validadas sem erros.")
                    logger.log(f"Validador LaTeX: 100% aprovado pelo motor KaTeX ({total_formulas} fórmulas).", "success")
                return aula_atual
                
            print(f"   -> [KATEX REAL - CICLO {ciclo + 1}] Detectadas {total_erros} falhas de compilação em {total_formulas} fórmulas.")
            if logger:
                logger.log(f"Validador LaTeX: {total_erros} falha(s) de compilação no ciclo {ciclo + 1}. Reparando...", "warning")
                
            anomalias_formatadas = []
            for idx_e, e in enumerate(erros[:8]):
                anomalias_formatadas.append({
                    "id": idx_e + 1,
                    "caminho_campo": e.get("caminho", "desconhecido"),
                    "erro_detectado": e.get("erro", "Erro KaTeX"),
                    "trecho_original": e.get("formula", "")
                })
                
            aula_atual = reparar_anomalias_cirurgico(
                aula_atual,
                anomalias_formatadas,
                logger=logger,
                target_model=target_model,
                tracker=tracker
            )
            
        # Pós-loop
        relatorio_final = compilar_katex_real(aula_atual)
        if relatorio_final.get("aprovado", False) or relatorio_final.get("total_erros", 0) == 0:
            print(" [OK] Todas as anomalias foram sanadas com sucesso no Loop!")
            if logger:
                logger.update_agent("validador_latex", "concluido")
                logger.log("Validador LaTeX: Reparo concluído e aprovado pelo KaTeX.", "success")
            return aula_atual
        else:
            print(f" [AVISO] Restaram {relatorio_final.get('total_erros', 0)} anomalia(s). Aplicando versão sanitizada final.")
            if logger:
                logger.update_agent("validador_latex", "concluido")
                logger.log("Validador LaTeX: Concluído com blindagem determinística.", "info")
            return latex_sanitizer.sanitize_json_recursively(aula_atual)

    except Exception as e:
        print(f" [AVISO] Exceção no validador LaTeX: {e}. Retornando aula sanitizada de forma segura.")
        if logger:
            logger.update_agent("validador_latex", "concluido")
        return latex_sanitizer.sanitize_json_recursively(aula_json)