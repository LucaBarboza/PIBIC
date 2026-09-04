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
Você é um Engenheiro de Frontend Sênior especializado em Data Visualization e interfaces educacionais altamente responsivas.
Sua missão é criar uma simulação interativa baseada em tecnologias web nativas (HTML, Tailwind CSS via CDN, Javascript) e bibliotecas de gráficos (Plotly.js via CDN).

[CONTEXTO DA AULA]
Tema Geral da Aula: {tema_aula}
Simulação Solicitada: {nome_simulador}

[DIRETRIZ DE SIMPLICIDADE E INTUIÇÃO VISUAL]
O objetivo central do simulador é proporcionar uma experiência visual interativa, intuitiva e dinâmica com Plotly.js. Os sliders alteram os parâmetros e o gráfico do Plotly atualiza em tempo real. Não sobrecarregue a tela com deduções analíticas no texto — o foco é 100% no gráfico interativo e na resposta visual aos sliders.

[DIRETRIZES DE ARQUITETURA E LAYOUT VERTICAL - CRÍTICO]
1. HIERARQUIA DE ELEMENTOS (DISPOSIÇÃO VERTICAL):
   - A página DEVE ser estruturada de cima para baixo na seguinte ordem:
     a) CABEÇALHO: Título e subtítulo em HTML no topo (`<h2 class="text-xl font-bold text-slate-800">{nome_simulador}</h2>`).
     b) PAINEL DE CONTROLES: Sliders (`<input type="range">`) agrupados em um card com Tailwind CSS no topo/centro.
     c) CONTAINER DO GRÁFICO (LARGURA TOTAL 100%): O gráfico DEVE ter SEMPRE uma div explícita `<div id="grafico" class="w-full my-4" style="width: 100%; min-height: 420px; height: 450px;"></div>` ABAIXO dos controles. TODA simulação DEVE renderizar um gráfico Plotly na div `grafico`.
     d) RODAPÉ / CARD EXPLICATIVO (OPCIONAL): Breve explicação das conclusões da simulação.

2. ALTURA, EIXOS E LEGENDA DO GRÁFICO (MANDATÓRIO):
   - A div do gráfico DEVE ter estilo inline com largura e altura explícitas:
     `<div id="grafico" class="w-full my-4" style="width: 100%; min-height: 420px; height: 460px;"></div>`
   - NO JS DO PLOTLY (LAYOUT COMPLETO COM TÍTULO, EIXOS E LEGENDA TOTALMENTE DESCOLADOS):
     * O container alvo do Plotly DEVE ser exatamente o id `grafico` (`Plotly.newPlot('grafico', ...)`).
     * Defina o título formal do gráfico dentro do Plotly:
       `title: {{ text: '{nome_simulador}', font: {{ size: 16, color: '#1e293b' }} }}`
     * Configure títulos descritivos para os eixos:
       `xaxis: {{ title: {{ text: 'Nome da Variável X', standoff: 15 }} }}, yaxis: {{ title: {{ text: 'Nome da Variável Y', standoff: 15 }} }}`
     * LEGENDA E MARGENS (CRÍTICO - EVITE SOBREPOSIÇÃO):
       Coloque margem inferior suficiente (`b: 80`) e posicione a legenda no topo superior direito ou abaixo do gráfico sem encavalar no título do eixo X:
       `margin: {{ t: 60, b: 80, l: 65, r: 35 }}, autosize: true, legend: {{ orientation: 'h', x: 0.5, xanchor: 'center', y: 1.15 }}` (legenda no topo acima do gráfico) ou `{{ orientation: 'h', x: 0.5, xanchor: 'center', y: -0.3 }}` (legenda bem abaixo do título do eixo X).
     * Ative responsividade: `Plotly.newPlot('grafico', data, layout, {{ responsive: true, displayModeBar: false }});`

3. INICIALIZAÇÃO BLINDADA COM POLLING DO PLOTLY (CRÍTICO - EVITA TELA BRANCA):
   - Como o Plotly é carregado via CDN assíncrono, você DEVE OBRIGATORIAMENTE usar a função de polling antes de chamar `Plotly.newPlot`:
     ```javascript
     function initSimulation() {{
       if (typeof Plotly === 'undefined') {{
         setTimeout(initSimulation, 50);
         return;
       }}
       
       // Configura listeners nos sliders
       const sliders = document.querySelectorAll('input[type="range"]');
       sliders.forEach(s => s.addEventListener('input', updateChart));
       
       // Executa a primeira renderização do gráfico
       updateChart();
     }}

     function updateChart() {{
       // 1. Lê valores dos sliders
       // 2. Calcula dados / arrays
       // 3. Renderiza no Plotly
       Plotly.react('grafico', traces, layout, config);
       
       // Notifica o iframe pai para ajuste de altura
       if (window.parent) {{
         window.parent.postMessage({{ type: 'resize', height: document.body.scrollHeight + 60 }}, '*');
       }}
     }}

     // Dispara a inicialização em qualquer estado do DOM
     window.addEventListener('load', initSimulation);
     document.addEventListener('DOMContentLoaded', initSimulation);
     initSimulation();
     ```

[CÓDIGO DE PARTIDA ESPERADO]
Retorne APENAS um documento HTML completo e válido (começando com <!DOCTYPE html> e terminando com </html>). É PROIBIDO usar marcadores de markdown (como ```html).

<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
</head>
<body class="bg-slate-50 p-4 md:p-6 font-sans">
  <div class="max-w-4xl mx-auto bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-6">
    <div class="text-center">
      <h2 class="text-xl font-bold text-slate-800 mb-1">{nome_simulador}</h2>
      <p class="text-xs text-slate-500">Laboratório Interativo Virtual | {tema_aula}</p>
    </div>
    
    <!-- Painel de Controles no topo -->
    <div class="bg-slate-50 p-4 rounded-xl border border-slate-200">
      <!-- Sliders aqui -->
    </div>

    <!-- Div do Gráfico ocupando 100% da largura -->
    <div id="grafico" class="w-full" style="width: 100%; min-height: 420px; height: 460px;"></div>

    <!-- Card Explicativo / Interpretação Didática com espaçamento inferior generoso -->
    <div class="bg-blue-50/70 border border-blue-100 rounded-xl p-4 text-slate-700 text-sm mb-4">
      <h4 class="font-bold text-blue-900 mb-1 flex items-center gap-1">💡 Como interpretar este gráfico?</h4>
      <p id="explicacao_dinamica" class="leading-relaxed">
        Interaja com os controles acima para visualizar a dinâmica do modelo em tempo real.
      </p>
    </div>
  </div>

  <script>
    // Todo o código JavaScript DEVE ficar OBRIGATORIAMENTE dentro desta tag <script>
    function initSimulation() {{
      if (typeof Plotly === 'undefined') {{
        setTimeout(initSimulation, 50);
        return;
      }}
      // Configuração de eventos e primeiro render
      updateChart();
    }}
    window.addEventListener('load', initSimulation);
    document.addEventListener('DOMContentLoaded', initSimulation);
    initSimulation();
  </script>
</body>
</html>
"""

from pydantic import BaseModel, Field

class SimuladorHTMLOutput(BaseModel):
    codigo_html_completo: str = Field(
        description="Código HTML5 completo contendo <!DOCTYPE html>, Tailwind CSS, Plotly.js e Javascript interativo em uma única string sem blocos de markdown."
    )

def gerar_simulador_html(tema_aula: str, nome_simulador: str, logger=None) -> str:
    """
    Gera um código HTML/JS completo para uma simulação interativa usando Gemini Pro com Structured Outputs.
    """
    client = get_genai_client()
    
    prompt = PROMPT_ENGENHEIRO_SIMULACAO.format(
        tema_aula=tema_aula,
        nome_simulador=nome_simulador
    )
    
    print(f"\n[Agente Simulador] Gerando simulação interativa estruturada para '{nome_simulador}' com Gemini Pro...")
    
    from gemini_retry import executar_chamada_com_retry

    try:
        if logger:
            logger.update_agent("simulador", "rodando", prompt=prompt)
            logger.log("Agente Simulador: Programando a interface...", "info")
        
        def chamar_simulador():
            return client.models.generate_content(
                model="gemini-pro-latest",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SimuladorHTMLOutput
                )
            )

        resposta = executar_chamada_com_retry(
            chamar_simulador,
            max_retries=5,
            logger=logger,
            nome_agente="Simulador",
            descricao=f"geração do simulador '{nome_simulador}'"
        )
        
        simulador_obj = SimuladorHTMLOutput.model_validate_json(resposta.text)
        codigo_html = simulador_obj.codigo_html_completo.strip()
        
        # Garante que nada fora de <!DOCTYPE...</html> ou <html...</html> permaneça
        match_html = re.search(r"(<!DOCTYPE[\s\S]*?</html>|<html[\s\S]*?</html>)", codigo_html, re.IGNORECASE)
        if match_html:
            codigo_html = match_html.group(1).strip()
            
        codigo_html = codigo_html.strip()
        if logger:
            logger.update_agent("simulador", "concluido", resposta=codigo_html)
            logger.log("Agente Simulador: Concluído com sucesso!", "success")
        print(" [OK] Simulador gerado e validado via Structured Outputs!")
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
    html = gerar_simulador_html("Distribuição Normal", "Impacto da Variância na Curva de Gauss")
    print("\nCódigo Gerado (primeiros 500 chars):")
    print(html[:500])
