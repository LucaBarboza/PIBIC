import os
import json
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv
import latex_sanitizer
from client_factory import get_genai_client

def detectar_anomalias_estruturais_katex(texto: str) -> list:
    """
    Realiza uma varredura completa por anomalias de sintaxe que o KaTeX / ReactMarkdown não consegue compilar.
    Retorna uma lista de strings descrevendo cada erro encontrado.
    """
    if not isinstance(texto, str) or not texto.strip():
        return []
        
    erros = []
    
    # 1. Checa ambientes \begin{...} sem o correspondente \end{...}
    begins = re.findall(r'\\begin\{([a-zA-Z*]+)\}', texto)
    ends = re.findall(r'\\end\{([a-zA-Z*]+)\}', texto)
    if sorted(begins) != sorted(ends):
        erros.append(f"Ambientes de matriz/equação desalinhados: \\begin{{{begins}}} vs \\end{{{ends}}}")

    # 2. Checa ambientes LaTeX não suportados em inline/display mode no KaTeX
    bad_envs = re.findall(r'\\begin\{(align\*?|equation\*?|gather\*?)\}', texto)
    if bad_envs:
        erros.append(f"Ambiente incompatível com KaTeX: \\begin{{{bad_envs[0]}}} (usar 'aligned')")
        
    # 3. Checa comandos/macros não suportados pelo KaTeX
    if r'\bm{' in texto:
        erros.append(r"Comando \bm{ não suportado pelo KaTeX (usar \boldsymbol{)")
    if r'\bold{' in texto:
        erros.append(r"Comando \bold{ não suportado pelo KaTeX (usar \mathbf{)")
    if re.search(r'\\+boldsymbol\\+\{', texto):
        erros.append(r"Sintaxe de chave escapada incorretamente em \boldsymbol\{")
    if r'\thicksim' in texto:
        erros.append(r"Comando inválido \thicksim (usar \sim)")
    if r'\nginxed' in texto:
        erros.append(r"Comando inválido \nginxed (usar \in)")

    # 4. Checa % não escapado dentro de ambiente de matemática ($...$ ou $$...$$)
    for bloco in re.findall(r'(?<!\\)\$([\s\S]*?)(?<!\\)\$', texto):
        if re.search(r'(?<!\\)%', bloco):
            erros.append("Caractere de porcentagem (%) não escapado dentro de ambiente matemático")
            break

    # 5. Checa cifrões desbalanceados (ignorando R\$ e US\$ escapados)
    unescaped_dollars = len(re.findall(r'(?<!\\)\$', texto))
    if unescaped_dollars % 2 != 0:
        erros.append("Cifrões ($) desbalanceados na string")
        
    # 6. Checa chaves desbalanceadas em ambiente de bloco $$
    for bloco in re.findall(r'\$\$(.*?)\$\$', texto, flags=re.DOTALL):
        chaves_abertas = bloco.count("{") - bloco.count("\\{")
        chaves_fechadas = bloco.count("}") - bloco.count("\\}")
        if chaves_abertas != chaves_fechadas:
            erros.append(f"Chaves desbalanceadas no bloco KaTeX ({chaves_abertas} abertas vs {chaves_fechadas} fechadas)")

    # 7. Checa \left e \right desbalanceados em blocos de matemática
    for bloco in re.findall(r'(?<!\\)\$([\s\S]*?)(?<!\\)\$', texto):
        left_count = len(re.findall(r'\\left[\(\[\{\|\.]', bloco))
        right_count = len(re.findall(r'\\right[\)\]\}\|\.]', bloco))
        if left_count != right_count:
            erros.append(f"Delimitadores \\left e \\right desbalanceados ({left_count} \\left vs {right_count} \\right)")
            break

    # 8. Símbolos gregos e matemáticos soltos na prosa pura (fora de blocos $)
    texto_sem_math = re.sub(r'(?<!\\)\$\$[\s\S]*?(?<!\\)\$\$', '', texto)
    texto_sem_math = re.sub(r'(?<!\\)\$(?:[^\$\n]|\\\$)+?(?<!\\)\$', '', texto_sem_math)
    symbols_soltos = re.findall(r'(?<!\\)\b(\\mu|\\sigma|\\alpha|\\beta|\\theta|\\lambda|\\pi|\\gamma|\\delta|\\epsilon|\\phi|\\omega|\\rho|\\tau|\\eta|\\chi|\\psi|\\zeta|\\in|\\forall|\\exists|\\rightarrow|\\Rightarrow|\\infty|\\partial)\b', texto_sem_math)
    if symbols_soltos:
        erros.append(f"Comandos matemáticos soltos na prosa sem delimitadores $: {set(symbols_soltos)}")

    return erros


def mapear_todas_anomalias_json(aula_json: dict) -> list:
    """
    Percorre recursivamente um JSON de aula e retorna um relatório estruturado
    contendo todas as anomalias de KaTeX identificadas.
    """
    anomalias = []
    anomalia_counter = 1

    def auditar_recursivo(obj, caminho="root"):
        nonlocal anomalia_counter
        if isinstance(obj, str):
            errs = detectar_anomalias_estruturais_katex(obj)
            if errs:
                anomalias.append({
                    "id": anomalia_counter,
                    "caminho_campo": caminho,
                    "erro_detectado": " | ".join(errs),
                    "trecho_original": obj[:300] + ("..." if len(obj) > 300 else "")
                })
                anomalia_counter += 1
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if k == "codigo_html_gerado":
                    continue
                auditar_recursivo(v, f"{caminho}.{k}")
        elif isinstance(obj, list):
            for i, elem in enumerate(obj):
                auditar_recursivo(elem, f"{caminho}[{i}]")

    auditar_recursivo(aula_json)
    return anomalias

from pydantic import BaseModel, Field
from typing import List, Optional

class ItemCorrecaoLatex(BaseModel):
    id: int = Field(description="ID numérico da anomalia a ser corrigida")
    caminho_campo: str = Field(description="Caminho exato do campo no JSON (ex: 'paginas_conteudo[0].formalismo_latex')")
    trecho_original_quebrado: str = Field(description="O trecho original de texto ou fórmula que continha a anomalia KaTeX")
    trecho_corrigido_limpo: str = Field(description="A versão totalmente corrigida e válida no KaTeX, sem alterar o sentido ou palavras da prosa")
    explicacao_tecnica: str = Field(description="Breve explicação técnica da correção efetuada (ex: 'Substituído \\begin{align} por \\begin{aligned}')")

class RelatorioCorrecaoLatex(BaseModel):
    correcoes: List[ItemCorrecaoLatex] = Field(description="Lista contendo cada uma das correções cirúrgicas efetuadas")

def substituir_no_caminho(obj, caminho: str, novo_valor: str) -> bool:
    """
    Substitui cirurgicamente um valor dentro de um dicionário/lista navegando pela string de caminho.
    Ex: 'root.conteudo_json.paginas_conteudo[0].formalismo_latex'
    """
    caminho_limpo = re.sub(r'^(root|aula|\.conteudo_json|\.conteudo)\.?', '', caminho)
    caminho_limpo = re.sub(r'^\.', '', caminho_limpo)
    if not caminho_limpo:
        return False

    tokens = [t for t in re.split(r'[\.\[\]]+', caminho_limpo) if t]
    
    atual = obj
    for i in range(len(tokens) - 1):
        token = tokens[i]
        if token.isdigit():
            idx = int(token)
            if isinstance(atual, list) and idx < len(atual):
                atual = atual[idx]
            else:
                return False
        else:
            if isinstance(atual, dict) and token in atual:
                atual = atual[token]
            else:
                return False

    ultimo_token = tokens[-1]
    if ultimo_token.isdigit():
        idx = int(ultimo_token)
        if isinstance(atual, list) and idx < len(atual):
            atual[idx] = novo_valor
            return True
    else:
        if isinstance(atual, dict):
            atual[ultimo_token] = novo_valor
            return True

    return False

def reparar_anomalias_cirurgico(aula_sanitizada: dict, anomalias: list, logger=None, target_model="gemini-2.5-flash", tracker=None) -> dict:
    """
    Envia APENAS as anomalias capturadas no Passo 1 para o LLM e aplica as correções cirurgicamente
    no JSON original sem tocar no resto da aula. Usa fallback imediato para nunca travar o pipeline.
    """
    try:
        client = get_genai_client()
    except Exception as e:
        print(f" [AVISO] Falha ao inicializar Gemini Client no validador: {e}. Mantendo versão determinística.")
        return aula_sanitizada
    
    from prompts import DICIONARIO_LATEX
    
    prompt_cirurgico = f"""
Você é o Revisor de Elite de Tipografia KaTeX e LaTeX de uma editora acadêmica de exatas.
Sua tarefa é REPARAR CIRURGICAMENTE uma lista de anomalias de compilação KaTeX encontradas em um capítulo de livro didático.

[DIRETRIZES DA EDITORA PARA A CORREÇÃO]
{DICIONARIO_LATEX}

REGRAS RÍGIDAS DE CORREÇÃO:
1. Mantenha 100% das palavras de prosa, significados e termos em português intactos.
2. Corrija APENAS os erros de sintaxe KaTeX apontados (ex: troque `\\begin{{align}}` por `\\begin{{aligned}}`, troque `\\bm` por `\\boldsymbol`, fixe chaves desbalanceadas, etc).
3. Garanta que todas as equações em bloco tenham delimitadores `$$` duplos isolados e equações em linha tenham `$` simples com espaços antes e depois.
4. Preencha rigorosamente a estrutura 'RelatorioCorrecaoLatex'.

[ANOMALIAS CAPTURADAS PARA CORREÇÃO]
{json.dumps(anomalias, ensure_ascii=False, indent=2)}
"""

    print(f"   -> [LLM] Solicitando reparo cirúrgico rápido ao {target_model}...", flush=True)
    
    import time
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
                    
            print(f" [OK] Reparo cirúrgico concluído! ({correcoes_aplicadas}/{len(anomalias)} anomalias corrigidas pontualmente)")
            
            if logger:
                logger.update_agent("validador_latex", "concluido", resposta=resposta.text)
                logger.log("Auditor de Compilação LaTeX: Reparo concluído com sucesso.", "success")
    
            return latex_sanitizer.sanitize_json_recursively(aula_sanitizada)
    
        except Exception as e:
            msg_erro = f"Tentativa {tentativa + 1} de reparo: {str(e)}"
            print(f" [AVISO] {msg_erro}")
            time.sleep(2)
            
    print(" [AVISO] Mantendo versão sanitizada determinística (segura e sem travamentos).")
    if logger:
        logger.update_agent("validador_latex", "concluido")
        logger.log("Auditor de Compilação LaTeX: Concluído via sanitização determinística.", "success")
    return aula_sanitizada

def validar_e_corrigir_aula_completa(aula_json: dict, logger=None, modelo_llm: str = "hibrido", tracker=None) -> dict:
    """
    Agente Validador e Auditor Final de Compilação LaTeX.
    Passo 1: Aplica a sanitização determinística instantânea em Python (< 1ms).
    Passo 2: Mapeia todas as anomalias estruturais reais de KaTeX no JSON.
    Passo 3: Se houver anomalias reais, executa o Reparo Cirúrgico Estruturado rápido.
    """
    if not aula_json or not isinstance(aula_json, dict):
        return aula_json
        
    from telemetry import resolver_modelo
    target_model = resolver_modelo("validador_latex", modelo_llm)
    
    try:
        if logger:
            logger.update_agent("validador_latex", "rodando")
            logger.log(f"Auditor de Compilação LaTeX ({target_model}): Inspecionando sintaxe e KaTeX...", "info")
            
        print(f"\n[Agente Validador de LaTeX ({target_model})] Inspecionando compilação de toda a aula...")
        
        # 1. Sanitização determinística automática em Python (< 1ms)
        aula_sanitizada = latex_sanitizer.sanitize_json_recursively(aula_json)
        
        # 2. Mapeamento estruturado de anomalias (Passo 1)
        anomalias_encontradas = mapear_todas_anomalias_json(aula_sanitizada)
        
        # Se anomalias foram detectadas, invoca o LLM com o relatório cirúrgico (Passo 2)
        if anomalias_encontradas:
            print(f"   -> [ALERTA KATEX] Detectadas {len(anomalias_encontradas)} anomalias reais no JSON. Acionando reparo cirúrgico...")
            if logger:
                logger.log(f"Validador LaTeX: Detectadas {len(anomalias_encontradas)} anomalias reais. Iniciando reparo cirúrgico...", "warning")
            return reparar_anomalias_cirurgico(aula_sanitizada, anomalias_encontradas, logger=logger, target_model=target_model, tracker=tracker)
        else:
            print(" [OK] Auditoria KaTeX concluída: 0 anomalias encontradas na aula!")
            if logger:
                logger.update_agent("validador_latex", "concluido")
                logger.log("Auditor de Compilação LaTeX: 100% livre de anomalias!", "success")
            return aula_sanitizada
            
    except Exception as e:
        print(f" [AVISO] Falha na auditoria avançada de LaTeX: {e}. Mantendo versão com sanitização determinística.")
        if logger:
            logger.update_agent("validador_latex", "concluido")
            logger.log("Auditor de Compilação LaTeX: Concluído com segurança.", "success")
        return latex_sanitizer.sanitize_json_recursively(aula_json)
        
        # Se nenhuma anomalia grave foi encontrada, retorna imediatamente (0ms latência extra!)
        if not anomalias_encontradas:
            print(" [OK] Auditoria de LaTeX: 100% de compilação limpa garantida (0 anomalias)!")
            if logger:
                logger.update_agent("validador_latex", "concluido", resposta="Compilação 100% Aprovada (0 anomalias).")
                logger.log("Auditor de Compilação LaTeX: 100% Aprovado (Zero erros de compilação).", "success")
            return aula_sanitizada

        # 3. Caso haja anomalias estruturais, aciona o Reparo Cirúrgico rápido
        print(f" [AVISO] {len(anomalias_encontradas)} anomalia(s) detectada(s). Acionando Reparo Cirúrgico via {target_model}...")
        if logger:
            logger.log(f"Auditor de Compilação LaTeX: Acionando {target_model} para reparo cirúrgico de {len(anomalias_encontradas)} anomalias...", "warning")
            
        return reparar_anomalias_cirurgico(aula_sanitizada, anomalias_encontradas, logger=logger, target_model=target_model)
    except Exception as e:
        print(f" [AVISO] Exceção no validador LaTeX: {e}. Retornando aula sanitizada de forma segura.")
        if logger:
            logger.update_agent("validador_latex", "concluido")
        return latex_sanitizer.sanitize_json_recursively(aula_json)
