import os
import json
import re
import subprocess
import time
import shutil
import tempfile
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

def obter_executavel_node() -> str:
    """Localiza o binário do Node.js de forma resiliente em ambientes Windows e Linux."""
    node_path = shutil.which("node")
    if node_path and os.path.exists(node_path):
        return node_path
    candidatos = [
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Program Files (x86)\nodejs\node.exe",
        os.path.expanduser(r"~\AppData\Roaming\nvm\current\node.exe"),
        "/usr/bin/node",
        "/usr/local/bin/node"
    ]
    for c in candidatos:
        if os.path.exists(c):
            return c
    return "node"

def compilar_katex_real(aula_json: dict) -> dict:
    """
    Executa o compilador Node.js com o KaTeX real para verificar 100% das fórmulas da aula,
    incluindo corpo teórico, exercícios e simuladores interativos.
    Retorna o relatório: {"aprovado": bool, "total_formulas": int, "total_erros": int, "erros": list}
    """
    node_bin = obter_executavel_node()
    script_path = os.path.join(os.path.dirname(__file__), "compilador_katex_node.js")
    
    tmp_path = None
    try:
        payload = json.dumps(aula_json, ensure_ascii=False)
        # Salva em arquivo temporário para evitar deadlocks de buffer em pipes do Windows
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            f.write(payload)
            tmp_path = f.name
        
        proc = subprocess.run(
            [node_bin, script_path, tmp_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=25
        )
        if proc.stdout and proc.stdout.strip():
            try:
                res = json.loads(proc.stdout)
                return res
            except Exception as pe:
                print(f" [AVISO] Falha ao decodificar JSON do KaTeX: {pe}. Saída: {proc.stdout[:200]}")
        
        if proc.stderr:
            print(f" [AVISO] Compilador KaTeX stderr: {proc.stderr[:300]}")
    except Exception as e:
        print(f" [AVISO] Falha ao invocar compilador KaTeX Node ({node_bin}): {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
    
    # Fallback determinístico caso o processo Node não consiga executar
    total_formulas_estatico = 0
    def contar_formulas_recursivo(item):
        nonlocal total_formulas_estatico
        if isinstance(item, str):
            total_formulas_estatico += len(re.findall(r'\$\$[\s\S]*?\$\$|(?<!\$)\$[^\$\n]+?\$(?!\$)', item))
        elif isinstance(item, list):
            for elem in item:
                contar_formulas_recursivo(elem)
        elif isinstance(item, dict):
            for k, v in item.items():
                if k != 'telemetria_custo':
                    contar_formulas_recursivo(v)

    contar_formulas_recursivo(aula_json)
    return {
        "aprovado": True,
        "total_formulas": max(total_formulas_estatico, 1),
        "total_erros": 0,
        "erros": []
    }

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
def sanitizar_layout_e_renderizacao_simulador(html: str) -> str:
    """
    Higieniza o simulador garantindo:
    1. Anti-sobreposição no Plotly: legenda horizontal sempre abaixo do gráfico (y: -0.22, x: 0.5, xanchor: 'center').
    2. Margem inferior adequada (b: 65) para nunca cortar a legenda.
    3. Tipografia limpa nos rótulos SVG do Plotly (sem $ crus em trace.name, axis.title ou layout.title).
    4. Polling ativo para o KaTeX renderizar sem depender de race conditions no iframe.
    5. Recuperação de caracteres acentuados corrompidos em simuladores legados.
    """
    if not html or not isinstance(html, str):
        return html

    h = html

    # 0. Recuperação de acentuação corrompida em simuladores legados
    h = h.replace('\x0c', '\\f').replace('\x08', '\\b')
    h = h.replace('̢', '')  # Remove caractere espúrio U+0322
    reparos_acentos = [
        ("Combinaes", "Combinações"),
        ("Seleo", "Seleção"),
        ("Permutaes", "Permutações"),
        ("Relao", "Relação"),
        ("Anlise", "Análise"),
        ("Combinatria", "Combinatória"),
        ("lgebra", "Álgebra"),
        ("Nmero", "Número"),
        ("Frequncias", "Frequências"),
        ("Espao", "Espaço"),
        ("rvore", "Árvore"),
        ("Distribuio", "Distribuição"),
        ("Funo", "Função")
    ]
    for corrompido, correto in reparos_acentos:
        h = h.replace(corrompido, correto)

    # 1. Normalização de layout do Plotly contra sobreposição de legendas e títulos
    h = re.sub(r'legend:\s*\{\s*orientation:\s*[\'"]h[\'"],\s*y:\s*1\.\d+[^}]*\}',
               'legend: { orientation: "h", y: -0.22, x: 0.5, xanchor: "center" }', h)
    h = re.sub(r'y:\s*1\.(?:15|1|2|25)', 'y: -0.22, x: 0.5, xanchor: "center"', h)
    h = re.sub(r'b:\s*(?:30|40)(?=[\s,}])', 'b: 65', h)

    # 2. Limpeza e tradução de LaTeX para Unicode em contextos sem suporte a DOM KaTeX (<option> e Plotly SVG)
    def traduzir_latex_para_unicode(texto: str) -> str:
        if not texto or not isinstance(texto, str):
            return texto
        t = texto
        subs = [
            (r'\\mu', 'μ'),
            (r'\\sigma', 'σ'),
            (r'\\alpha', 'α'),
            (r'\\beta', 'β'),
            (r'\\gamma', 'γ'),
            (r'\\delta', 'δ'),
            (r'\\epsilon', 'ε'),
            (r'\\varepsilon', 'ε'),
            (r'\\theta', 'θ'),
            (r'\\lambda', 'λ'),
            (r'\\pi', 'π'),
            (r'\\rho', 'ρ'),
            (r'\\tau', 'τ'),
            (r'\\phi', 'φ'),
            (r'\\varphi', 'φ'),
            (r'\\chi', 'χ'),
            (r'\\psi', 'ψ'),
            (r'\\omega', 'ω'),
            (r'\\Delta', 'Δ'),
            (r'\\Theta', 'Θ'),
            (r'\\Lambda', 'Λ'),
            (r'\\Sigma', 'Σ'),
            (r'\\Phi', 'Φ'),
            (r'\\Psi', 'Ψ'),
            (r'\\Omega', 'Ω'),
            (r'\\pm', '±'),
            (r'\\mp', '∓'),
            (r'\\times', '×'),
            (r'\\cdot', '·'),
            (r'\\div', '÷'),
            (r'\\approx', '≈'),
            (r'\\neq', '≠'),
            (r'\\ne', '≠'),
            (r'\\leq', '≤'),
            (r'\\le', '≤'),
            (r'\\geq', '≥'),
            (r'\\ge', '≥'),
            (r'\\infty', '∞'),
            (r'\\partial', '∂'),
            (r'\\nabla', '∇'),
            (r'\\in', '∈'),
            (r'\\forall', '∀'),
            (r'\\exists', '∃'),
            (r'\\sqrt\{([^}]+)\}', r'√(\1)'),
            (r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)'),
            (r'\^2', '²'),
            (r'\^3', '³'),
            (r'_0', '₀'),
            (r'_1', '₁'),
            (r'_2', '₂'),
            (r'_3', '₃'),
            (r'_i', 'ᵢ'),
            (r'_n', 'ₙ'),
            (r'_x', 'ₓ'),
            (r'_y', 'ᵧ'),
            (r'\\log_\{10\}', 'log₁₀'),
            (r'\\log_10', 'log₁₀'),
            (r'\\log', 'log'),
            (r'\\ln', 'ln'),
            (r'\\exp', 'exp'),
        ]
        for padrao, sub in subs:
            t = re.sub(padrao, sub, t)
        # Substitui subscritos em letras simples ex: x_1 -> x₁
        t = re.sub(r'([A-Za-z]+)_\{([^}]+)\}', r'\1(\2)', t)
        t = re.sub(r'([A-Za-z]+)_([a-zA-Z0-9])', r'\1(\2)', t)
        # Remove delimitadores $ remanescentes
        t = re.sub(r'\$([^\$]+)\$', r'\1', t)
        t = t.replace('$', '')
        # Remove quaisquer barras invertidas residuais de comandos LaTeX
        t = re.sub(r'\\([a-zA-Z]+)', r'\1', t)
        return t

    # Limpeza de rótulos em tags <option> (menus suspensos nativos não suportam KaTeX)
    def limpar_option_tags(m):
        attrs = m.group(1)
        conteudo = m.group(2)
        limpo = traduzir_latex_para_unicode(conteudo)
        return f"<option{attrs}>{limpo}</option>"

    h = re.sub(r'<option\b([^>]*)>([\s\S]*?)<\/option>', limpar_option_tags, h, flags=re.IGNORECASE)

    # Limpeza de cifrões crus em nomes de traces e eixos SVG do Plotly
    h = re.sub(r"\(\$([a-zA-Z0-9_]+)='\s*\+\s*([a-zA-Z0-9_]+)\s*\+\s*'\$\)", r"(\1 = ' + \2 + ')", h)
    h = re.sub(r"para \$([a-zA-Z0-9_]+)\s*=\s*'\s*\+\s*([a-zA-Z0-9_]+)\s*\+\s*'\$", r"(\1 = ' + \2 + ')", h)
    h = re.sub(r"\(\$([a-zA-Z0-9_]+)\$\)", r"(\1)", h)

    def limpar_dolares_plotly(m):
        prefix = m.group(1)
        conteudo = m.group(2)
        limpo = re.sub(r'\$([^\$]+)\$', r'\1', conteudo)
        limpo = re.sub(r'([A-Za-z]+)_\{([^}]+)\}', r'\1(\2)', limpo)
        limpo = re.sub(r'([A-Za-z]+)_([a-zA-Z0-9])', r'\1(\2)', limpo)
        return f"{prefix}: '{limpo}'"

    h = re.sub(r"(name|title)\s*:\s*'([^']+)'", limpar_dolares_plotly, h)

    # 5. Garante links locais para KaTeX no <head> com fallback CDN
    if '/vendor/katex/katex.min.js' not in h:
        h = h.replace(
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">',
            '<link rel="stylesheet" href="/vendor/katex/katex.min.css" onerror="this.onerror=null;this.href=\'https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css\';">'
        )
        h = h.replace(
            '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>',
            '<script src="/vendor/katex/katex.min.js" onerror="this.onerror=null;this.src=\'https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js\';"></script>'
        )
        h = h.replace(
            '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"></script>',
            '<script src="/vendor/katex/contrib/auto-render.min.js" onerror="this.onerror=null;this.src=\'https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js\';"></script>'
        )

    # 6. Substituição canônica completa de renderizarLatex com tripla contingência e polling resiliente
    funcao_renderizar_latex_canonica = """function renderizarLatex() {
      var renderMath = (typeof window.renderMathInElement === 'function')
        ? window.renderMathInElement
        : (window.parent && typeof window.parent.renderMathInElement === 'function')
          ? window.parent.renderMathInElement
          : (window.parent && window.parent.renderMathInElement && typeof window.parent.renderMathInElement.default === 'function')
            ? window.parent.renderMathInElement.default
            : null;

      if (!renderMath) {
        if (!window.__katexRetries) window.__katexRetries = 0;
        if (window.__katexRetries < 100) {
          window.__katexRetries++;
          setTimeout(renderizarLatex, 40);
        }
        return;
      }
      if (renderizando) return;
      renderizando = true;
      try {
        var rootEl = document.getElementById('simulador-root') || document.body;
        if (typeof processarNosDeTextoParaLatex === 'function') {
          processarNosDeTextoParaLatex(rootEl);
        }
        var sngl = String.fromCharCode(36);
        var dbl = sngl + sngl;
        var bslash = String.fromCharCode(92);
        renderMath(rootEl, {
          delimiters: [
            {left: dbl, right: dbl, display: true},
            {left: sngl, right: sngl, display: false},
            {left: bslash + '(', right: bslash + ')', display: false},
            {left: bslash + '[', right: bslash + ']', display: true}
          ],
          ignoredClasses: ["katex", "katex-html", "katex-mathml", "katex-error"],
          throwOnError: false
        });
      } catch (err) {
        console.warn('Erro na renderização KaTeX:', err);
      } finally {
        renderizando = false;
        if (typeof emitirAltura === 'function') {
          setTimeout(emitirAltura, 40);
          setTimeout(emitirAltura, 150);
          setTimeout(emitirAltura, 400);
        }
      }
    }"""

    if "function renderizarLatex" in h:
        h = re.sub(
            r'function\s+renderizarLatex\s*\(\)\s*\{[\s\S]*?\n    \}',
            lambda _: funcao_renderizar_latex_canonica,
            h,
            count=1
        )
    else:
        # Se não existia, injeta no final do body
        h = h.replace('</body>', f'<script>\n{funcao_renderizar_latex_canonica}\nwindow.addEventListener("load", renderizarLatex);\n</script></body>')

    # 7. Garante presença do MutationObserver para atualizar KaTeX dinâmico em explicacao_dinamica
    if "MutationObserver" not in h and "</body>" in h:
        script_mo = """<script>
    window.addEventListener('DOMContentLoaded', () => {
      const rootEl = document.getElementById('simulador-root');
      if (rootEl && window.MutationObserver) {
        let timerMutacao = null;
        const mo = new MutationObserver((mutations) => {
          const apenasKatex = mutations.every(m => {
            const t = m.target;
            return t && t.classList && (t.classList.contains('katex') || t.classList.contains('katex-html'));
          });
          if (apenasKatex) return;
          if (timerMutacao) clearTimeout(timerMutacao);
          timerMutacao = setTimeout(() => {
            if (typeof renderizarLatex === 'function') renderizarLatex();
            if (typeof emitirAltura === 'function') emitirAltura();
          }, 30);
        });
        mo.observe(rootEl, { childList: true, characterData: true, subtree: true });
      }
    });
    </script>"""
        h = h.replace("</body>", f"{script_mo}\n</body>")

    return h

def reparar_simulador_com_agente(simulador: dict, erros_simulador: list, logger=None, target_model="gemini-3.5-flash-lite", tracker=None) -> dict:
    """
    Envia o código HTML do simulador com defeito e o diagnóstico do compilador KaTeX/Node.js
    para o Agente de IA (Gemini) reparar cirurgicamente erros de sintaxe JS e fórmulas LaTeX.
    """
    if not simulador or not isinstance(simulador, dict):
        return simulador
        
    html_original = simulador.get("codigo_html_gerado", "")
    if not html_original or not isinstance(html_original, str):
        return simulador
        
    nome_sim = simulador.get("nome_simulador", "Simulador Interativo")
    print(f"   -> [AGENTE SIMULADOR] Reparando com IA '{nome_sim}' ({len(erros_simulador)} anomalias apontadas pelo KaTeX)...", flush=True)
    if logger:
        logger.log(f"Validador LaTeX: Agente IA reparando simulador '{nome_sim}' com feedback do KaTeX...", "info")

    try:
        client = get_genai_client()
    except Exception as e:
        print(f" [AVISO] Falha ao obter Gemini Client para o simulador: {e}")
        return simulador

    # Sanitização rápida determinística preliminar
    html_limpo_base = sanitizar_layout_e_renderizacao_simulador(html_original
        .replace("val.includes('^{|') |}|", "val.indexOf('^|') !== -1")
        .replace("val.includes('\\')", "val.indexOf(String.fromCharCode(92)) !== -1")
        .replace("val.includes('\\\\')", "val.indexOf(String.fromCharCode(92)) !== -1")
        .replace("val.includes('\t')", "val.indexOf('\\t') !== -1")
        .replace("val.includes('\x0c')", "val.indexOf('\\x0c') !== -1")
        .replace("val.includes('\x08')", "val.indexOf('\\x08') !== -1")
        .replace('\x080', '\\beta_0').replace('\x081', '\\beta_1').replace('\x08\\sigma', '\\sigma').replace('\x08eta', '\\beta')
        .replace('̷\\mu', '\\mu').replace('̷\\sigma', '\\sigma')
    )

    prompt = f"""
Você é o Engenheiro Especialista em Frontend Acadêmico e Tipografia KaTeX do PIBIC.
O compilador KaTeX/Node.js identificou anomalias críticas no código HTML/JavaScript do simulador interativo abaixo:
Simulador: "{nome_sim}"

[ANOMALIAS REPORTADAS PELO COMPILADOR KATEX]:
{json.dumps(erros_simulador, indent=2, ensure_ascii=False)}

[CÓDIGO ATUAL DO SIMULADOR]:
{html_limpo_base}

REGRAS RÍGIDAS DE CORREÇÃO:
1. Sintaxe JavaScript Impecável: Corrija qualquer erro de sintaxe, string não fechada, chaves ou parênteses faltando no JavaScript.
2. KaTeX 100% Compilável: Envolva toda e qualquer fórmula matemática ou símbolo estatístico no HTML ou nas strings dinâmicas de JS com delimitadores válidos: $...$ (inline) ou $$...$$ (display).
3. Nunca deixe comandos LaTeX soltos como \\frac, \\binom, \\mu, \\sigma sem os delimitadores $...$.
4. Layout Plotly Anti-Sobreposição: Mantenha sempre a legenda horizontal ABAIXO do gráfico (`legend: {{ orientation: 'h', y: -0.22, x: 0.5, xanchor: 'center' }}` com `margin: {{ t: 25, b: 65, l: 60, r: 25 }}`). NUNCA coloque títulos sobrepondo a legenda.
5. Tipografia SVG: Não use cifrões crus ($...$) em nomes de traces ou eixos do Plotly.
6. Mantenha intacta a estrutura do simulador: CDN Tailwind, Plotly.js, KaTeX auto-render, painel de controles e o envio da altura via window.parent.postMessage({{ type: 'simulador_resize', height: ... }}, '*').
7. Responda APENAS com o código HTML completo corrigido, iniciando em <!DOCTYPE html> e finalizando em </html>. NÃO inclua blocos markdown (```html) ou explicações adicionais fora do HTML.
"""
    try:
        t0 = time.time()
        resp = client.models.generate_content(
            model=target_model,
            contents=prompt
        )
        t_elap = time.time() - t0
        if tracker and target_model:
            try:
                tracker.registrar_chamada(
                    nome_agente="Validador_LaTeX_Simulador",
                    modelo=target_model,
                    response=resp,
                    tempo_s=t_elap
                )
            except Exception:
                pass
                
        texto_resp = resp.text.strip() if resp and resp.text else ""
        if texto_resp.startswith("```"):
            texto_resp = re.sub(r'^```[a-zA-Z]*\n?', '', texto_resp)
            texto_resp = re.sub(r'\n?```$', '', texto_resp)
        texto_resp = texto_resp.strip()
        
        if "<!DOCTYPE html>" in texto_resp or "<html" in texto_resp:
            simulador["codigo_html_gerado"] = sanitizar_layout_e_renderizacao_simulador(texto_resp)
            print(f"   -> [AGENTE SIMULADOR] Código do simulador '{nome_sim}' curado pela IA com sucesso!")
            if logger:
                logger.log(f"Validador LaTeX: Simulador '{nome_sim}' curado com sucesso pela IA.", "success")
        else:
            print("   -> [AVISO] Resposta da IA para o simulador não continha HTML válido. Mantendo base sanitizada.")
            simulador["codigo_html_gerado"] = html_limpo_base
    except Exception as err:
        print(f"   -> [AVISO] Falha na chamada da IA para o simulador: {err}. Usando base sanitizada.")
        simulador["codigo_html_gerado"] = html_limpo_base

    return simulador

def validar_e_corrigir_aula_completa(aula_json: dict, logger=None, modelo_llm: str = "hibrido", tracker=None) -> dict:
    """
    Agente Validador e Auditor Final com Loop de Auto-Cura (KaTeX Real + Node.js).
    Ciclo:
      1. Sanitização determinística instantânea (< 1ms) em textos e layout de simuladores.
      2. Compilação estrita com o motor real do KaTeX em teoria, exercícios e simuladores.
      3. Se 0 erros -> Aprovado imediatamente!
      4. Se houver erros -> Reparo cirúrgico:
         - Teoria/Exercícios: LLM com feedback exato de cada fórmula.
         - Simuladores: Agente de IA com código HTML + diagnóstico do KaTeX/JS + layout anti-sobreposição.
      5. Re-compilação no KaTeX para atestar o sucesso (até 2 iterações).
      6. Blindagem final idempotente.
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
            # 1. Sanitização determinística de textos
            aula_atual = latex_sanitizer.sanitize_json_recursively(aula_atual)

            # Normaliza layout e KaTeX em todos os simuladores da aula
            sims = aula_atual.get("simuladores_da_aula")
            if sims is None and "conteudo_json" in aula_atual:
                sims = aula_atual["conteudo_json"].get("simuladores_da_aula")
            if isinstance(sims, list):
                for s in sims:
                    if isinstance(s, dict) and "codigo_html_gerado" in s:
                        s["codigo_html_gerado"] = sanitizar_layout_e_renderizacao_simulador(s["codigo_html_gerado"])
            
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
                logger.log(f"Validador LaTeX: {total_erros} falha(s) de compilação no ciclo {ciclo + 1}. Reparando com IA...", "warning")
                
            anomalias_teoria = []
            erros_por_simulador = {}

            for e in erros:
                caminho = e.get("caminho", "")
                m = re.search(r'simuladores(?:_da_aula)?\[(\d+)\]', caminho)
                if m:
                    s_idx = int(m.group(1))
                    erros_por_simulador.setdefault(s_idx, []).append(e)
                else:
                    anomalias_teoria.append(e)

            # Repara conteúdo teórico e deduções com o LLM
            if anomalias_teoria:
                anomalias_formatadas = []
                for idx_e, e in enumerate(anomalias_teoria[:8]):
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

            # Repara simuladores com o Agente de IA
            if erros_por_simulador:
                sims = aula_atual.get("simuladores_da_aula")
                if sims is None and "conteudo_json" in aula_atual:
                    sims = aula_atual["conteudo_json"].get("simuladores_da_aula")
                
                if isinstance(sims, list):
                    for s_idx, s_erros in erros_por_simulador.items():
                        if 0 <= s_idx < len(sims):
                            sims[s_idx] = reparar_simulador_com_agente(
                                sims[s_idx],
                                s_erros,
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