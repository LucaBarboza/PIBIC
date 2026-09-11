import os
import json
import re
from typing import Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from client_factory import get_genai_client
from gemini_retry import executar_chamada_com_retry

TEMPLATE_SIMULADOR_UFBA = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>__TITULO__</title>
  <!-- 1. Tailwind CSS via CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- 2. Plotly.js via CDN -->
  <script src="https://cdn.plot.ly/plotly-2.29.1.min.js"></script>
  <!-- 3. KaTeX CSS + JS + Auto-Render via CDN -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"></script>
  <style>
    html, body {
      background-color: #f8fafc;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 0;
      padding: 0;
      overflow-x: hidden;
      overflow-y: hidden;
      height: auto !important;
      min-height: 0 !important;
    }
    /* Eliminação absoluta de qualquer barra de rolagem no KaTeX e nas fórmulas */
    .katex, .katex-display, .katex-html, .katex *, 
    #explicacao_dinamica, #explicacao_dinamica *,
    #simulador-root * {
      overflow-x: visible !important;
      overflow-y: visible !important;
      scrollbar-width: none !important;
      -ms-overflow-style: none !important;
    }
    .katex::-webkit-scrollbar, .katex *::-webkit-scrollbar,
    .katex-display::-webkit-scrollbar, .katex-html::-webkit-scrollbar,
    #explicacao_dinamica::-webkit-scrollbar, #explicacao_dinamica *::-webkit-scrollbar {
      display: none !important;
      width: 0 !important;
      height: 0 !important;
    }
    .katex-display {
      margin: 0.35em 0 !important;
      max-width: 100% !important;
      white-space: normal !important;
    }
    .katex-display > .katex {
      white-space: normal !important;
      text-align: center;
    }
    #explicacao_dinamica {
      word-break: break-word;
      overflow: visible !important;
    }
    .katex { font-size: 1.05em; }
  </style>
</head>
<body class="bg-slate-50 text-slate-800 antialiased p-3 sm:p-5 pb-6">
  <div id="simulador-root" class="max-w-4xl mx-auto space-y-4 pb-2">
    <!-- Cabeçalho Acadêmico Pré-Pronto -->
    <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
      <span class="text-xs font-bold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-md border border-indigo-100">Lab Interativo</span>
      <h3 class="text-base sm:text-lg font-bold text-slate-800 mt-1">__TITULO__</h3>
    </div>

    <!-- Painel de Parâmetros e Controles Pré-Pronto -->
    <div class="bg-white p-4 sm:p-5 rounded-xl border border-slate-200 shadow-sm space-y-3">
      <div class="flex items-center justify-between border-b border-slate-100 pb-2">
        <h4 class="text-xs font-bold text-slate-500 uppercase tracking-wider">Painel de Parâmetros</h4>
        <span class="text-xs text-slate-400">Ajuste os controles para visualizar a alteração dinâmica</span>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
        __PAINEL_CONTROLES_HTML__
      </div>
    </div>

    <!-- Container do Gráfico Plotly -->
    <div class="bg-white p-3 sm:p-4 rounded-xl border border-slate-200 shadow-sm">
      <div id="grafico" class="w-full" style="min-height: 400px;"></div>
    </div>

    <!-- Card de Fórmula / Definição Formal (Embaixo do Gráfico) -->
    __BLOCO_FORMULA_CARD__

    <!-- Card de Explicação Pedagógica Dinâmica -->
    <div class="bg-indigo-50/60 border border-indigo-100 p-4 sm:p-5 rounded-xl text-slate-700 shadow-sm mb-4 pb-3">
      <div class="flex items-center gap-2 mb-2">
        <span class="text-indigo-600 font-bold text-sm">💡 Interpretação Pedagógica:</span>
      </div>
      <div id="explicacao_dinamica" class="text-sm leading-relaxed text-slate-700 space-y-1.5">
        __EXPLICACAO_INICIAL__
      </div>
    </div>
  </div>

  <!-- Sistema de Auto-Ajuste de Altura e Renderização KaTeX -->
  <script>
    function prepararLatexSolto(texto) {
      if (!texto || typeof texto !== 'string') return texto;
      if (texto.includes('katex-html') || texto.includes('katex-display')) return texto;

      let res = texto;
      
      // 1. Recupera escapes de caracteres de controle e tabs corrompidos
      res = res
        .replace(/[\x0c\u000c]rac/g, '\\frac')
        .replace(/[\x08\u0008]ar\\{/g, '\\bar{')
        .replace(/[\x08\u0008]eta/g, '\\beta')
        .replace(/[\x08\u0008]inom/g, '\\binom')
        .replace(/[\x08\u0008]mathbf/g, '\\mathbf')
        .replace(/\t(ext|au|heta|imes)/g, '\\$1')
        .replace(/(?<![\\f\x0c\u000c])rac\\{/g, '\\frac{');

      // 2. Corrige potências e subscritos compostos sem chaves (ex: phi^|h| -> phi^{|h|}, e^-x -> e^{-x})
      res = res
        .replace(/\\^\\|([^|]+)\\|/g, '^{|$1|}')
        .replace(/_\\|([^|]+)\\|/g, '_{|$1|}');

      // 3. Parênteses contendo expressões matemáticas como (mu), (sigma = 1.0)
      res = res.replace(/\\(([^)]*\\\\(?:mu|sigma|alpha|beta|theta|lambda|pi|gamma|delta|phi|omega|tau|rho|hat|bar|pm|approx|leq|geq|cdot)[^)]*)\\)/g, function(match, interior) {
        var limpo = interior.trim();
        if (limpo.startsWith('$') && limpo.endsWith('$')) return match;
        return '($' + limpo + '$)';
      });

      // 4. Comandos LaTeX soltos restantes (que não estão em $...$)
      var cmdRegex = /(?<![\\$a-zA-Z0-9])\\\\(mu|sigma|alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|vartheta|iota|kappa|lambda|nu|xi|pi|varpi|rho|varrho|varsigma|tau|upsilon|phi|varphi|chi|psi|omega|Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Upsilon|Phi|Psi|Omega|pm|mp|cdot|times|approx|neq|ne|leq|geq|le|ge|infty|forall|exists|partial|nabla)(?![a-zA-Z0-9])/g;

      var partes = res.split(/(\\$\\$[\\s\\S]*?\\$\\$|\\$[^\\$\\n]+?\\$)/);
      for (var i = 0; i < partes.length; i += 2) {
        if (partes[i]) {
          partes[i] = partes[i].replace(cmdRegex, function(_, m) { return '$\\\\' + m + '$'; });
        }
      }
      return partes.join('');
    }

    function processarNosDeTextoParaLatex(node) {
      if (!node) return;
      if (node.nodeType === Node.TEXT_NODE) {
        const val = node.nodeValue;
        if (val && (val.includes('\\') || val.includes('\t') || val.includes('\x0c') || val.includes('\x08') || val.includes('^|') || val.includes('_|'))) {
          const modificado = prepararLatexSolto(val);
          if (modificado !== val) {
            node.nodeValue = modificado;
          }
        }
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        const tag = node.tagName.toLowerCase();
        if (tag === 'script' || tag === 'style' || tag === 'input' || tag === 'select' || (node.classList && (node.classList.contains('katex') || node.classList.contains('katex-html')))) {
          return;
        }
        Array.from(node.childNodes).forEach(child => processarNosDeTextoParaLatex(child));
      }
    }

    let lastSentHeight = 0;
    function emitirAltura() {
      const root = document.getElementById('simulador-root');
      if (!root) return;

      // Medição estrita do container de conteúdo (NUNCA do document.body ou documentElement para impedir loop ratchet de expansão)
      const rect = root.getBoundingClientRect();
      const hContent = Math.ceil(rect.height || root.offsetHeight || 600);
      const alturaFinal = Math.min(Math.max(hContent + 30, 520), 1600);

      if (Math.abs(alturaFinal - lastSentHeight) >= 3) {
        lastSentHeight = alturaFinal;
        window.parent.postMessage({ type: 'simulador_resize', height: alturaFinal }, '*');
      }
    }

    let renderizando = false;
    function renderizarLatex() {
      if (renderizando) return;
      renderizando = true;
      try {
        const rootEl = document.getElementById('simulador-root') || document.body;
        processarNosDeTextoParaLatex(rootEl);
        if (window.renderMathInElement) {
          renderMathInElement(rootEl, {
            delimiters: [
              {left: '$$', right: '$$', display: true},
              {left: '$', right: '$', display: false},
              {left: '\\(', right: '\\)', display: false},
              {left: '\\[', right: '\\]', display: true}
            ],
            throwOnError: false
          });
        }
      } catch (err) {
        console.warn('Erro na renderização KaTeX:', err);
      } finally {
        renderizando = false;
        setTimeout(emitirAltura, 50);
        setTimeout(emitirAltura, 200);
        setTimeout(emitirAltura, 500);
      }
    }

    // Observador contínuo de resize estritamente no container de conteúdo (NUNCA no document.body)
    if (window.ResizeObserver) {
      const ro = new ResizeObserver(() => {
        emitirAltura();
      });
      const rootEl = document.getElementById('simulador-root');
      if (rootEl) ro.observe(rootEl);
      const expEl = document.getElementById('explicacao_dinamica');
      if (expEl) ro.observe(expEl);
    }

    // Observador de mutações no DOM para detectar updates em explicacao_dinamica e controles
    window.addEventListener('DOMContentLoaded', () => {
      const rootEl = document.getElementById('simulador-root');
      if (rootEl && window.MutationObserver) {
        let timerMutacao = null;
        const mo = new MutationObserver((mutations) => {
          const apenasKatex = mutations.every(m => {
            const t = m.target;
            return t && t.classList && (t.classList.contains('katex') || t.classList.contains('katex-html'));
          });
          if (apenasKatex) {
            setTimeout(emitirAltura, 50);
            return;
          }

          if (timerMutacao) clearTimeout(timerMutacao);
          timerMutacao = setTimeout(() => {
            renderizarLatex();
            emitirAltura();
          }, 30);
        });
        mo.observe(rootEl, { childList: true, characterData: true, subtree: true });
      }
      renderizarLatex();
      emitirAltura();
    });

    window.addEventListener('load', () => {
      renderizarLatex();
      setTimeout(emitirAltura, 100);
      setTimeout(emitirAltura, 400);
      setTimeout(emitirAltura, 800);
    });
  </script>

  <!-- Lógica Javascript Especializada Injetada -->
  <script>
    __CODIGO_JAVASCRIPT_LOGICA__

    // Inicialização segura com polling para aguardar Plotly carregar
    function inicializarSimulacaoBlindada() {
      if (typeof Plotly !== 'undefined' && typeof initSimulation === 'function') {
        initSimulation();
        renderizarLatex();
        setTimeout(emitirAltura, 150);
      } else {
        setTimeout(inicializarSimulacaoBlindada, 50);
      }
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', inicializarSimulacaoBlindada);
    } else {
      inicializarSimulacaoBlindada();
    }
  </script>
</body>
</html>
"""

PROMPT_ENGENHEIRO_SIMULACAO = """
Você é um Engenheiro de Visualização de Dados e Estatística Computacional para o Ensino Superior (Padrão Acadêmico UFBA).
Sua missão é projetar os componentes de uma simulação estatística interativa concreta, rigorosa e pedagógica.

[CONTEXTO DA AULA E DO SUBTÓPICO]
Tema Geral da Aula: {tema_aula}
Simulação Solicitada: {nome_simulador}

Conteúdo Teórico do Subtópico:
\"\"\"{contexto_subtopico}\"\"\"

[DIRETRIZES DE SENSO ESTATÍSTICO REAL - PROIBIÇÃO DE SLIDERS ABSTRATOS]
1. PROIBIÇÃO DE SLIDERS ABSTRATOS:
   - É TERMINANTEMENTE PROIBIDO criar sliders ou controles genéricos/artificiais (como 'Fator Multiplicativo', 'Deslocamento Base', 'Colunas', 'Barras').
   - Todos os controles devem modelar parâmetros estatísticos REAIS com rótulos em português:
     * Para Gráficos de Frequência / Barras / Setores: Categorias reais (ex: 'Regiões', 'Cursos', 'Faixas de Renda'), controle de contagem/frequência de cada categoria, alternância entre 'Frequência Absoluta' e 'Frequência Relativa (%)', ordenação (Decrescente / Crescente / Original).
     * Para Histogramas: 'Número de Intervalos (bins)', 'Tamanho da Amostra ($n$)', 'Média ($\\mu$)', 'Desvio Padrão ($\\sigma$)'.
     * Para Boxplots / Medidas de Posição: 'Mediana', 'Dispersão ($IQR$)', 'Assimetria', inclusão de 'Outliers'.
     * Para Dispersão e Regressão: 'Inclinação ($\\beta_1$)', 'Intercepto ($\\beta_0$)', 'Dispersão dos Erros ($\\sigma$)', 'Tamanho da Amostra ($n$)'.
     * Para Distribuições de Probabilidade: Parâmetros reais da distribuição (ex: $p$, $n$, $\\mu$, $\\sigma$, $\\lambda$, $gl$).

2. EIXOS FIXOS E ESTÁVEIS NO PLOTLY:
   - No `layout` do Plotly, use SEMPRE `autorange: false` e limites `range: [min, max]` fixos bem calibrados nos eixos.
   - Quando o aluno mover um slider, a curva ou as barras devem mudar contra uma grade fixa e estável.
   - Use o layout claro acadêmico:
     `paper_bgcolor: '#ffffff'`, `plot_bgcolor: '#f8fafc'`, cor de fonte `#334155`, linhas de grade `#e2e8f0`.

3. ESTRUTURA DO HTML DOS CONTROLES (`painel_controles_html`):
   - Gere apenas os blocos de `<div class="space-y-1">` contendo:
     `<label class="flex justify-between text-xs font-semibold text-slate-700"><span>Nome do Parâmetro ($...$):</span><span id="valor_param" class="text-indigo-600 font-bold">50</span></label>`
     `<input type="range" id="param" min="..." max="..." step="..." value="..." class="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600">`
   - Se aplicável, use `<select id="..." class="w-full text-xs font-medium bg-slate-50 border border-slate-300 rounded-lg p-2 text-slate-700 focus:ring-indigo-500 focus:border-indigo-500">`.

4. ESTRUTURA DO JAVASCRIPT (`codigo_javascript_logica`):
   - Deve conter a função `function initSimulation()` que conecta os listeners de input (`addEventListener('input', updateChart)` ou `'change'`) e chama `updateChart()`.
   - Deve conter a função `function updateChart()` que:
     a) Lê os valores dos inputs.
     b) Atualiza os `<span>` com os valores formatados.
     c) Gera os dados estatísticos e atualiza o gráfico via `Plotly.react('grafico', traces, layout, {{ responsive: true, displayModeBar: false }})`.
     d) Atualiza o elemento `document.getElementById('explicacao_dinamica').innerHTML` com uma explicação pedagógica dinâmica em português estruturada (usando listas `•` ou parágrafos) que interpreta o resultado atual para o estudante.
     e) Chama `renderizarLatex()` no final para formatar símbolos KaTeX.

5. FORMATAÇÃO DE SÍMBOLOS MATEMÁTICOS E LATEX:
   - Envolva sempre letras gregas e fórmulas matemáticas entre cifrões `$ ... $` (ex: `($\\mu = 0.0$)`, `($\\sigma = 1.0$)`, `($\\mu \\pm 1\\sigma$)`, `$f(x)$`).
   - Use SEMPRE chaves completas {{}} em expoentes e subscritos compostos (ex: `\\phi^{{|h|}}` e JAMAIS `\\phi^|h|`; `e^{{-x}}` e JAMAIS `e^-x`; `X_{{t+1}}`).
   - Não use quebras literais de texto sem tags HTML (`<br>` ou `<p>`).

Retorne estritamente o JSON estruturado conforme o schema.
"""

class ComponenteSimulador(BaseModel):
    titulo: str = Field(
        description="Título acadêmico e claro da simulação interativa (ex: 'Impacto da Variância na Dispersão dos Dados')."
    )
    formula_latex: Optional[str] = Field(
        default="",
        description="Fórmula matemática central em notação LaTeX (ex: '$IQR = Q_3 - Q_1$' ou '$\\sigma = \\sqrt{\\frac{\\sum (x_i - \\mu)^2}{N}}$') para o cabeçalho, ou string vazia."
    )
    painel_controles_html: str = Field(
        description="HTML dos controles contendo apenas elementos de input/select estilizados com Tailwind e labels claros."
    )
    codigo_javascript_logica: str = Field(
        description="Código JavaScript ES6 completo contendo as funções initSimulation() e updateChart(), listeners de eventos, cálculo estatístico, renderização Plotly.react e atualização de explicacao_dinamica."
    )
    explicacao_inicial: str = Field(
        description="Texto pedagógico inicial interpretando o gráfico para o estudante em português claro e estimulante."
    )

def gerar_simulador_html(tema_aula: str, nome_simulador: str, contexto_subtopico: str = "", logger=None, modelo_llm: str = "hibrido", tracker=None) -> str:
    """
    Gera um simulador interativo completo e validado usando Structured Outputs (ComponenteSimulador)
    e injetando os dados diretamente no template pré-pronto fixo UFBA Light Theme.
    """
    client = get_genai_client()
    
    from telemetry import resolver_modelo
    modelo_alvo = resolver_modelo("simulador", modelo_llm)
    
    prompt = PROMPT_ENGENHEIRO_SIMULACAO.format(
        tema_aula=tema_aula,
        nome_simulador=nome_simulador,
        contexto_subtopico=contexto_subtopico or "Conceitos teóricos e visuais da aula."
    )
    
    print(f"\n[Agente Simulador ({modelo_alvo})] Projetando componentes estruturados para '{nome_simulador}'...")
    
    try:
        if logger:
            logger.update_agent("simulador", "rodando", prompt=prompt)
            logger.log("Agente Simulador: Programando a interface no design system UFBA...", "info")
        
        def chamar_simulador():
            resp = client.models.generate_content(
                model=modelo_alvo,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ComponenteSimulador
                )
            )
            from latex_sanitizer import safe_json_loads
            parsed = safe_json_loads(resp.text)
            if not isinstance(parsed, dict):
                raise ValueError("Resposta do modelo não pôde ser convertida em dicionário JSON.")
            comp_obj = ComponenteSimulador.model_validate(parsed)
            return comp_obj, resp.text

        comp, resposta_raw = executar_chamada_com_retry(
            chamar_simulador,
            max_retries=5,
            logger=logger,
            nome_agente="Simulador",
            descricao=f"geração do simulador '{nome_simulador}'",
            tracker=tracker,
            modelo=modelo_alvo
        )
        
        # Monta card de fórmula (embaixo do gráfico em card dedicado)
        bloco_formula_card = ""
        if comp.formula_latex and comp.formula_latex.strip():
            formula_limpa = comp.formula_latex.strip()
            if not formula_limpa.startswith("$$") and not formula_limpa.startswith("$"):
                formula_limpa = f"$${formula_limpa}$$"
            bloco_formula_card = f"""
    <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm text-center">
      <span class="text-xs font-bold uppercase tracking-wider text-slate-500 block mb-1">Modelo Matemático do Laboratório</span>
      <div class="text-sm sm:text-base font-semibold text-slate-800">
        {formula_limpa}
      </div>
    </div>"""
        
        def sanitizar_js_latex(codigo_js: str) -> str:
            if not codigo_js:
                return codigo_js
            comandos = (
                r'frac|dfrac|tfrac|binom|dbinom|tbinom|sqrt|'
                r'hat|widehat|bar|overline|tilde|widetilde|vec|dot|ddot|'
                r'text|textbf|textit|mathbf|boldsymbol|bm|mathit|mathrm|mathcal|mathbb|'
                r'alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|vartheta|'
                r'iota|kappa|lambda|mu|nu|xi|pi|varpi|rho|varrho|sigma|varsigma|tau|'
                r'upsilon|phi|varphi|chi|psi|omega|Gamma|Delta|Theta|Lambda|Xi|Pi|'
                r'Sigma|Upsilon|Phi|Psi|Omega|'
                r'sum|prod|coprod|int|iint|iiint|oint|lim|sup|inf|max|min|log|ln|exp|sin|cos|tan|'
                r'cdot|times|div|pm|mp|circ|bullet|star|'
                r'approx|sim|simeq|cong|equiv|propto|le|ge|leq|geq|neq|ne|'
                r'in|notin|subset|subseteq|supset|supseteq|cup|cap|setminus|'
                r'to|rightarrow|Rightarrow|leftarrow|Leftarrow|leftrightarrow|Leftrightarrow|'
                r'partial|nabla|infty|forall|exists|nexists|empty|emptyset|'
                r'ell|hbar|aleph|Re|Im|wp|'
                r'quad|qquad|left|right|big|Big|bigg|Bigg|middle'
            )
            # 1. Recupera caracteres de controle gerados por escape no JSON
            codigo_js = codigo_js.replace('\x0c', r'\f').replace('\x08', r'\b')
            codigo_js = re.sub(r'\t(ext|au|heta|imes)', r'\\t\1', codigo_js)
            # 2. Corrige potências e subscritos sem chaves (ex: \phi^|h| -> \phi^{|h|}, _|h| -> _{|h|})
            codigo_js = re.sub(r'\^\|([^|]+)\|', r'^{|\1|}', codigo_js)
            codigo_js = re.sub(r'_\|([^|]+)\|', r'_{|\1|}', codigo_js)
            # 3. Garante que qualquer comando LaTeX em strings JS tenha barras duplas '\\'
            return re.sub(rf'(?<!\\)\\({comandos})(?![a-zA-Z])', r'\\\\\1', codigo_js)

        codigo_js_sanitizado = sanitizar_js_latex(comp.codigo_javascript_logica.strip())
        explicacao_sanitizada = comp.explicacao_inicial.strip().replace(r'\n\n', '\n\n').replace(r'\n', '\n')

        # Injeta componentes no template pré-pronto fixo de forma segura (sem format/KeyError)
        html_final = (
            TEMPLATE_SIMULADOR_UFBA
            .replace("__TITULO__", comp.titulo or nome_simulador)
            .replace("__BLOCO_FORMULA_CARD__", bloco_formula_card)
            .replace("__PAINEL_CONTROLES_HTML__", comp.painel_controles_html.strip())
            .replace("__EXPLICACAO_INICIAL__", explicacao_sanitizada)
            .replace("__CODIGO_JAVASCRIPT_LOGICA__", codigo_js_sanitizado)
        )
        
        if logger:
            logger.update_agent("simulador", "concluido", resposta=html_final)
            logger.log("Agente Simulador: Concluído com sucesso no design system fixo!", "success")
        print(" [OK] Simulador gerado e injetado com sucesso no template pré-pronto!")
        return html_final
        
    except Exception as e:
        msg_erro = f"Falha definitiva de gerar simulador '{nome_simulador}': {str(e)}"
        print(f" [ERRO] {msg_erro}")
        if logger:
            logger.update_agent("simulador", "erro")
            logger.log(f"Agente Simulador: Falha - {msg_erro}", "error")
        return f"<div class='p-4 text-red-500 bg-red-50 rounded-xl border border-red-200'>Erro ao gerar a simulação: {str(e)}</div>"


if __name__ == "__main__":
    # Teste rápido
    html = gerar_simulador_html("Distribuição Normal", "Impacto da Variância na Curva de Gauss")
    print("\nCódigo Gerado (primeiros 600 chars):")
    print(html[:600])

