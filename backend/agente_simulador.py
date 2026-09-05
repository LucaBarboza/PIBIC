import os
import json
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv
from client_factory import get_genai_client

def carregar_chave_api():
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")

PROMPT_ENGENHEIRO_SIMULACAO = """
Você é um Engenheiro de Frontend Sênior especializado em Data Visualization, Estatística Computacional e interfaces educacionais altamente responsivas.
Sua missão é criar uma simulação interativa baseada em tecnologias web nativas (HTML5, Tailwind CSS via CDN, Javascript ES6), bibliotecas de gráficos (Plotly.js via CDN) e fórmulas matemáticas nítidas (KaTeX via CDN).

[CONTEXTO DA AULA E DO SUBTÓPICO]
Tema Geral da Aula: {tema_aula}
Simulação Solicitada: {nome_simulador}

Conteúdo Teórico do Subtópico:
\"\"\"{contexto_subtopico}\"\"\"

[DIRETRIZ MESTRE 1: DESIGN SYSTEM 100% LIGHT THEME ACADÊMICO - PROIBIÇÃO DE DARK MODE]
1. TEMA CLARO OBRIGATÓRIO (LIGHT THEME):
   - O simulador roda integrado a uma plataforma acadêmica com fundo claro.
   - Body/Container: DEVE usar `bg-white` ou `bg-slate-50` com texto `text-slate-800`.
   - Cards e Paineis: `bg-white border border-slate-200 rounded-xl shadow-sm p-4 sm:p-5`.
   - Destaques e Títulos: `text-slate-900 font-bold`, subtítulos `text-slate-600`.
   - Inputs e Sliders: `accent-blue-600 bg-slate-100`.
   - Plotly Layout:
     * `paper_bgcolor: 'rgba(0,0,0,0)'`
     * `plot_bgcolor: 'rgba(0,0,0,0)'`
     * `font: {{ color: '#334155', family: 'system-ui, -apple-system, sans-serif' }}`
     * `xaxis: {{ gridcolor: '#f1f5f9', zerolinecolor: '#cbd5e1', linecolor: '#cbd5e1' }}`
     * `yaxis: {{ gridcolor: '#f1f5f9', zerolinecolor: '#cbd5e1', linecolor: '#cbd5e1' }}`
   - É ESTRITAMENTE PROIBIDO usar classes escuras como `bg-slate-900`, `bg-slate-800`, `bg-gray-900`, `text-white`, `text-slate-100` ou temas escuros (`plotly_dark`).

[DIRETRIZ MESTRE 2: KATEX NATIVO PARA TODAS AS FÓRMULAS E SÍMBOLOS MATEMÁTICOS]
1. INCLUSÃO NO HEAD:
   - Inclua sempre o CDN do KaTeX no `<head>`:
     ```html
     <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
     <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
     <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
     ```
2. FÓRMULAS RENDERIZADAS EM TEMPO REAL:
   - Todos os símbolos matemáticos nos cards de métricas (ex: $\\bar{{x}}$, $\\tilde{{x}}$, $\\sum(x_i - \\bar{{x}}) = 0$, $\\sigma$, $\\mu$, $\\beta_1$, $R^2$) DEVEM estar formatados com delimitadores KaTeX `$ ... $` ou `$$ ... $$`.
   - Crie a função helper de renderização:
     ```javascript
     function renderLatex() {{
       if (typeof renderMathInElement !== 'undefined') {{
         renderMathInElement(document.body, {{
           delimiters: [
             {{ left: "$$", right: "$$", display: true }},
             {{ left: "$", right: "$", display: false }}
           ],
           throwOnError: false
         }});
       }}
     }}
     ```
   - Chame `renderLatex()` no final de `initSimulation()` e no final de `updateChart()`.
   - NUNCA exiba variáveis indefinidas (`undefined`) no HTML ou nos cálculos.

[DIRETRIZ MESTRE 3: SENSO ESTATÍSTICO REAL - PROIBIÇÃO DE SLIDERS ABSTRATOS]
1. CENÁRIOS ESTATÍSTICOS CONCRETOS:
   - É TERMINANTEMENTE PROIBIDO criar controles genéricos como 'Fator de Crescimento', 'Deslocamento Base', 'Colunas Multiplicativas'.
   - O simulador DEVE modelar um cenário com significado real:
     * Para Barras / Colunas / Setores: Categorias temáticas reais (ex: 'Regiões', 'Cursos Universitários', 'Faixas de Renda'). Controles para frequência/contagem de cada categoria, alternar Frequência Absoluta vs Relativa (%), ordenar barras (Decrescente / Crescente / Original).
     * Para Ponto de Equilíbrio / Média: Mostrar dados com desvios individuais $d_i = (x_i - \\bar{{x}})$ e a soma nula $\\sum(x_i - \\bar{{x}}) = 0$.
     * Para Histogramas: Controles para 'Largura de Classes (bins)', 'Tamanho da Amostra (n)', 'Média' e 'Assimetria'.
     * Para Boxplots e Outliers: Sliders para 'Mediana', 'IQR', e adicionar/remover 'Outliers' com visualização da barreira $Q_3 + 1.5 \\times IQR$.
     * Para Dispersão e Regressão: Sliders para inclinação ($\\beta_1$), intercepto ($\\beta_0$), ruído ($\\sigma$) e resíduos visíveis.

[DIRETRIZ MESTRE 4: EIXOS FIXOS E ESTÁVEIS NO PLOTLY]
1. LIMITES FIXOS NO LAYOUT:
   - Configure SEMPRE limites fixos bem calibrados no Plotly (`autorange: false`, `range: [min, max]`).
   - Os dados e formas se movem em tempo real contra uma grade estável.
2. FEEDBACK PEDAGÓGICO EM TEMPO REAL:
   - Atualize `<p id="explicacao_dinamica">` com um parágrafo claro e dinâmico interpretando o impacto estatístico das alterações do usuário.

[DIRETRIZ MESTRE 6: CONCISÃO E CONCLUSÃO COMPLETA (MÁXIMO 250-300 LINHAS)]
1. CÓDIGO LIMPO E FOCADO:
   - Escreva um código Javascript e HTML enxuto, priorizando a reatividade dos sliders e os gráficos do Plotly.
   - Evite boilerplate repetitivo, centenas de linhas de SVGs decorativos ou presets gigantescos.
   - Garanta que TODAS as funções JS sejam completamente fechadas e que o arquivo termine perfeitamente com `</script></body></html>`.

[CÓDIGO DE PARTIDA ESPERADO]
Retorne APENAS um documento HTML completo e válido (começando com <!DOCTYPE html> e terminando com </html>). É PROIBIDO usar marcadores de markdown (como ```html).
"""

from pydantic import BaseModel, Field

class SimuladorHTMLOutput(BaseModel):
    codigo_html_completo: str = Field(
        description="Código HTML5 completo contendo <!DOCTYPE html>, Tailwind CSS, KaTeX CDN, Plotly.js e Javascript interativo em uma única string sem blocos de markdown."
    )

def _garantir_inclusoes_html(codigo_html: str) -> str:
    """
    Pós-processador para injetar com garantia KaTeX CDN, ResizeObserver e normalizar cores de fundo para Light Theme.
    """
    html = codigo_html
    
    # 1. Normaliza classes dark mode acidentais no body
    html = re.sub(r'(<body[^>]*class=["\'][^"\']*)\bbg-slate-900\b', r'\1bg-white', html)
    html = re.sub(r'(<body[^>]*class=["\'][^"\']*)\bbg-gray-900\b', r'\1bg-white', html)
    html = re.sub(r'(<body[^>]*class=["\'][^"\']*)\bbg-black\b', r'\1bg-white', html)
    html = re.sub(r'(<body[^>]*class=["\'][^"\']*)\btext-slate-100\b', r'\1text-slate-800', html)
    html = re.sub(r'(<body[^>]*class=["\'][^"\']*)\btext-white\b', r'\1text-slate-800', html)

    # 2. Injeta KaTeX no <head> se não estiver presente
    if "katex.min.css" not in html:
        katex_head_tags = """
    <!-- KaTeX CDN Injetado com Segurança -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
        """
        if "</head>" in html:
            html = html.replace("</head>", f"{katex_head_tags}\n</head>")
        elif "<body" in html:
            html = re.sub(r"(<body)", f"{katex_head_tags}\n\\1", html, count=1)

    # 3. Injeta script de renderização matemática e ResizeObserver se não estiver presente
    if "simulador_resize" not in html or "renderMathInElement" not in html:
        helper_script = """
<script>
function __renderLatexSeguro() {
  if (typeof renderMathInElement !== 'undefined') {
    renderMathInElement(document.body, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false }
      ],
      throwOnError: false
    });
  }
}

function __notificarAltura() {
  try {
    const h = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, 700);
    window.parent.postMessage({ type: 'simulador_resize', height: h }, '*');
  } catch(e) {}
}

window.addEventListener('DOMContentLoaded', () => {
  __renderLatexSeguro();
  __notificarAltura();
  if (window.ResizeObserver) {
    new ResizeObserver(() => {
      __notificarAltura();
    }).observe(document.body);
  }
});

window.addEventListener('load', () => {
  __renderLatexSeguro();
  __notificarAltura();
  setTimeout(() => {
    __renderLatexSeguro();
    __notificarAltura();
  }, 400);
});
</script>
"""
        if "</body>" in html:
            html = html.replace("</body>", f"{helper_script}\n</body>")
        else:
            html += f"\n{helper_script}"

    return html

def gerar_simulador_html(tema_aula: str, nome_simulador: str, contexto_subtopico: str = "", logger=None, modelo_llm: str = "hibrido", tracker=None) -> str:
    """
    Gera um código HTML/JS completo para uma simulação interativa usando Gemini com Structured Outputs.
    """
    client = get_genai_client()
    
    from telemetry import resolver_modelo
    modelo_alvo = resolver_modelo("simulador", modelo_llm)
    
    prompt = PROMPT_ENGENHEIRO_SIMULACAO.format(
        tema_aula=tema_aula,
        nome_simulador=nome_simulador,
        contexto_subtopico=contexto_subtopico or "Conceitos teóricos e visuais da aula."
    )
    
    print(f"\n[Agente Simulador ({modelo_alvo})] Gerando simulação interativa estruturada para '{nome_simulador}'...")
    
    from gemini_retry import executar_chamada_com_retry

    try:
        if logger:
            logger.update_agent("simulador", "rodando", prompt=prompt)
            logger.log("Agente Simulador: Programando a interface...", "info")
        
        def chamar_simulador():
            return client.models.generate_content(
                model=modelo_alvo,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SimuladorHTMLOutput,
                    max_output_tokens=16384,
                    temperature=0.2
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
        
        codigo_html = ""
        try:
            simulador_obj = SimuladorHTMLOutput.model_validate_json(resposta.text)
            codigo_html = simulador_obj.codigo_html_completo.strip()
        except Exception as json_err:
            raw_text = resposta.text
            match_json = re.search(r'"codigo_html_completo":\s*"([\s\S]*?)(?:"\s*\}|\Z)', raw_text)
            if match_json:
                raw_html = match_json.group(1)
                raw_html = raw_html.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
                codigo_html = raw_html.strip()
            else:
                match_html = re.search(r"(<!DOCTYPE[\s\S]*?</html>|<html[\s\S]*?</html>|<!DOCTYPE[\s\S]*)", raw_text, re.IGNORECASE)
                if match_html:
                    codigo_html = match_html.group(1).strip()
                else:
                    raise json_err
        
        # Garante que nada fora de <!DOCTYPE...</html> ou <html...</html> permaneça
        match_html = re.search(r"(<!DOCTYPE[\s\S]*?</html>|<html[\s\S]*?</html>)", codigo_html, re.IGNORECASE)
        if match_html:
            codigo_html = match_html.group(1).strip()
        elif "<!DOCTYPE" in codigo_html or "<html" in codigo_html:
            if "</body>" not in codigo_html:
                codigo_html += "\n</body>"
            if "</html>" not in codigo_html:
                codigo_html += "\n</html>"
            
        codigo_html = codigo_html.strip()
        
        # Injeta garantias estruturais (KaTeX, ResizeObserver, Light Theme normalizado)
        codigo_html = _garantir_inclusoes_html(codigo_html)
        
        if logger:
            logger.update_agent("simulador", "concluido", resposta=codigo_html)
            logger.log("Agente Simulador: Concluído com sucesso!", "success")
        print(" [OK] Simulador gerado, enriquecido com KaTeX e validado via Structured Outputs!")
        return codigo_html
        
    except Exception as e:
        msg_erro = f"Falha definitiva de gerar simulador '{nome_simulador}': {str(e)}"
        print(f" [ERRO] {msg_erro}")
        if logger:
            logger.update_agent("simulador", "erro")
            logger.log(f"Agente Simulador: Falha - {msg_erro}", "error")
        return f"<div class='p-4 text-red-500'>Erro ao gerar a simulação após várias tentativas.</div>"


if __name__ == "__main__":
    # Teste rápido
    html = gerar_simulador_html("Estatística Descritiva", "Ponto de Equilíbrio e Desvios da Média")
    print("\nCódigo Gerado (primeiros 500 chars):")
    print(html[:500])
