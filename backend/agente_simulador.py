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
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"></script>
  <style>
    body {
      background-color: #f8fafc;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 0;
      padding: 0;
      overflow: hidden;
    }
    .katex { font-size: 1.05em; }
  </style>
</head>
<body class="bg-slate-50 text-slate-800 antialiased p-3 sm:p-5">
  <div id="simulador-root" class="max-w-4xl mx-auto space-y-4">
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
    <div class="bg-indigo-50/60 border border-indigo-100 p-4 rounded-xl text-slate-700 shadow-sm">
      <div class="flex items-center gap-2 mb-1.5">
        <span class="text-indigo-600 font-bold text-sm">💡 Interpretação Pedagógica:</span>
      </div>
      <p id="explicacao_dinamica" class="text-sm leading-relaxed text-slate-700">
        __EXPLICACAO_INICIAL__
      </p>
    </div>
  </div>

  <!-- Sistema de Auto-Ajuste de Altura e Renderização KaTeX -->
  <script>
    function limparCaracteresDeEscapeJS(rootEl) {
      if (!rootEl) return;
      const elements = rootEl.querySelectorAll('*');
      elements.forEach(el => {
        if (el.children.length === 0 && el.innerHTML) {
          let txt = el.innerHTML;
          if (txt.includes('\\x0c') || txt.includes('\\x08') || txt.includes('rac{') || txt.includes('quad') || txt.includes('omega_') || txt.includes('hat') || txt.includes('ell(')) {
            txt = txt
              .replace(/[\\x0c\\u000c]rac/g, '\\\\frac')
              .replace(/[\\x08\\u0008]ar\\{/g, '\\\\bar{')
              .replace(/[\\x08\\u0008]eta/g, '\\\\beta')
              .replace(/[\\x08\\u0008]inom/g, '\\\\binom')
              .replace(/[\\x08\\u0008]mathbf/g, '\\\\mathbf')
              .replace(/(?<![\\\\f\\x0c\\u000c])rac\\{/g, '\\\\frac{')
              .replace(/(?<![\\\\a-zA-Z])hat(?=\s*[\(\{\\\\a-zA-Z])/g, '\\\\hat ')
              .replace(/(?<![\\\\a-zA-Z])ell(?=[\s\(\{\^_])/g, '\\\\ell ')
              .replace(/(?<!\\\\)omega([_\\s\\^\\{])/g, '\\\\omega$1')
              .replace(/(?<!\\\\)sigma([_\\s\\^\\{])/g, '\\\\sigma$1')
              .replace(/(?<!\\\\)mu([_\\s\\^\\{])/g, '\\\\mu$1')
              .replace(/(?<!\\\\)alpha([_\\s\\^\\{])/g, '\\\\alpha$1')
              .replace(/(?<!\\\\)beta([_\\s\\^\\{])/g, '\\\\beta$1')
              .replace(/(?<!\\\\)theta([_\\s\\^\\{])/g, '\\\\theta$1')
              .replace(/(?<!\\\\)lambda([_\\s\\^\\{])/g, '\\\\lambda$1')
              .replace(/(?<!\\\\)pi([_\\s\\^\\{])/g, '\\\\pi$1')
              .replace(/(?<!\\\\)sum([_\\s\\^\\{])/g, '\\\\sum$1')
              .replace(/(?<!\\\\)quad(?=[\\s\\$\\(\\)])/g, '\\\\quad');
            el.innerHTML = txt;
          }
        }
      });
    }

    let lastSentHeight = 0;
    function emitirAltura() {
      const root = document.getElementById('simulador-root');
      if (!root) return;
      // Mede ESTRITAMENTE o elemento de conteúdo, sem consultar body/doc scrollHeight (evita loop infinito)
      const h = Math.ceil(root.offsetHeight || root.getBoundingClientRect().height);
      if (h > 50 && Math.abs(h - lastSentHeight) > 6) {
        lastSentHeight = h;
        const alturaFinal = Math.min(h + 24, 1800);
        window.parent.postMessage({ type: 'simulador_resize', height: alturaFinal }, '*');
      }
    }

    function renderizarLatex() {
      const rootEl = document.getElementById('simulador-root') || document.body;
      limparCaracteresDeEscapeJS(rootEl);
      if (window.renderMathInElement) {
        renderMathInElement(document.body, {
          delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '$', right: '$', display: false}
          ],
          throwOnError: false
        });
      }
      setTimeout(emitirAltura, 50);
    }

    // Observador contínuo focado exclusivamente no container de conteúdo
    if (window.ResizeObserver) {
      const ro = new ResizeObserver(() => {
        emitirAltura();
      });
      const rootEl = document.getElementById('simulador-root');
      if (rootEl) ro.observe(rootEl);
    }

    // Carregamento inicial garantido
    window.addEventListener('load', () => {
      renderizarLatex();
      emitirAltura();
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
     * Para Histogramas: 'Número de Intervalos (bins)', 'Tamanho da Amostra (n)', 'Média (mu)', 'Desvio Padrão (sigma)'.
     * Para Boxplots / Medidas de Posição: 'Mediana', 'Dispersão (IQR)', 'Assimetria', inclusão de 'Outliers'.
     * Para Dispersão e Regressão: 'Inclinação (beta1)', 'Intercepto (beta0)', 'Dispersão dos Erros (sigma)', 'Tamanho da Amostra (n)'.
     * Para Distribuições de Probabilidade: Parâmetros reais da distribuição (ex: p, n, mu, sigma, lambda, gl).

2. EIXOS FIXOS E ESTÁVEIS NO PLOTLY:
   - No `layout` do Plotly, use SEMPRE `autorange: false` e limites `range: [min, max]` fixos bem calibrados nos eixos.
   - Quando o aluno mover um slider, a curva ou as barras devem mudar contra uma grade fixa e estável.
   - Use o layout claro acadêmico:
     `paper_bgcolor: '#ffffff'`, `plot_bgcolor: '#f8fafc'`, cor de fonte `#334155`, linhas de grade `#e2e8f0`.

3. ESTRUTURA DO HTML DOS CONTROLES (`painel_controles_html`):
   - Gere apenas os blocos de `<div class="space-y-1">` contendo:
     `<label class="flex justify-between text-xs font-semibold text-slate-700"><span>Nome do Parâmetro:</span><span id="valor_param" class="text-indigo-600 font-bold">50</span></label>`
     `<input type="range" id="param" min="..." max="..." step="..." value="..." class="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600">`
   - Se aplicável, use `<select id="..." class="w-full text-xs font-medium bg-slate-50 border border-slate-300 rounded-lg p-2 text-slate-700 focus:ring-indigo-500 focus:border-indigo-500">`.

4. ESTRUTURA DO JAVASCRIPT (`codigo_javascript_logica`):
   - Deve conter a função `function initSimulation()` que conecta os listeners de input (`addEventListener('input', updateChart)` ou `'change'`) e chama `updateChart()`.
   - Deve conter a função `function updateChart()` que:
     a) Lê os valores dos inputs.
     b) Atualiza os `<span>` com os valores formatados.
     c) Gera os dados estatísticos e atualiza o gráfico via `Plotly.react('grafico', traces, layout, {{ responsive: true, displayModeBar: false }})`.
     d) Atualiza o elemento `document.getElementById('explicacao_dinamica').innerHTML` com uma explicação pedagógica dinâmica em português que interpreta o resultado atual para o estudante.
     e) Chama `renderizarLatex()` caso haja fórmulas matemáticas no texto dinâmico.

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
            return client.models.generate_content(
                model=modelo_alvo,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ComponenteSimulador
                )
            )

        resposta = executar_chamada_com_retry(
            chamar_simulador,
            max_retries=5,
            logger=logger,
            nome_agente="Simulador",
            descricao=f"geração do simulador '{nome_simulador}'",
            tracker=tracker,
            modelo=modelo_alvo
        )
        
        comp = ComponenteSimulador.model_validate_json(resposta.text)
        
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
            # Garante que qualquer comando LaTeX em strings JS tenha barras duplas '\\'
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

