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
Você é um Engenheiro de Frontend Sênior e Especialista em Data Visualization Educacional da UFBA.
Sua missão é criar uma simulação/laboratório interativo de altíssimo nível didático usando HTML5, Tailwind CSS e Plotly.js.

[CONTEXTO DA AULA]
Tema Geral da Aula: {tema_aula}
Simulação / Gráfico Solicitado: {nome_simulador}

[DIRETRIZ CENTRAL: SENSO ESTATÍSTICO REAL E PROIBIÇÃO DE SLIDERS ARTIFICIAIS]
1. AUTENTICIDADE ESTATÍSTICA (MANDATÓRIO):
   - É TERMINANTEMENTE PROIBIDO criar controles ou termos sintéticos/artificiais sem sentido didático (ex: NUNCA crie sliders como 'Fator de Crescimento', 'Deslocamento Base', 'Constante A', 'Multiplicador Genérico').
   - Os sliders e controles DEVEM controlar parâmetros estatísticos reais e intuitivos:
     * Gráfico de Barras / Colunas / Setores: Tamanho Amostral (N), Proporção da Categoria Líder (%), Escala de Exibição (Frequência Absoluta N vs Frequência Relativa %), ou Adição de Novas Categorias.
     * Histograma: Número de Classes / Intervalos (Bins k de 4 a 30), Tamanho Amostral (N de 50 a 2000), Assimetria da Amostra.
     * Boxplot (Diagrama de Caixa): Dispersão / Variância (sigma), Quantidade de Outliers (Valores Discrepantes), Assimetria (Simétrico vs Cauda Longa).
     * Diagrama de Dispersão / Regressão: Coeficiente de Correlação Linear (r de -1.0 a +1.0), Inclinação da Reta (beta1), Ruído / Dispersão dos Resíduos (sigma), Tamanho da Amostra (N).
     * Distribuições de Probabilidade: Média (mu), Desvio Padrão (sigma), Parâmetro Lambda (Poisson), Probabilidade de Sucesso (p na Binomial).

2. EIXOS COM LIMITES FIXOS E ESTÁVEIS (OS DADOS MUDAM, OS EIXOS FICAM FIXOS):
   - No `layout` do Plotly, os eixos X e Y DEVEM SEMPRE ter limites fixos e bem calibrados com `autorange: false` e `range: [min, max]`.
   - MOTIVO PEDAGÓGICO: Com eixos fixos, quando o aluno altera um parâmetro (ex: dispersão, proporção, correlação), ele VÊ os dados, barras e pontos mudarem de formato contra a grade fixa.
   - É PROIBIDO fazer os sliders alterarem os limites dos eixos (`layout.xaxis.range`). Os sliders DEVEM alterar os dados da distribuição.

3. DINÂMICA E EXPLICAÇÃO EM TEMPO REAL:
   - Na função `updateChart()`:
     a) Leia os valores numéricos dos `<input type="range">`.
     b) Atualize os `<span id="val_...">` com os valores formatados.
     c) Recalcule os dados estatísticos (arrays x, y) aplicando as fórmulas estatísticas adequadas.
     d) Atualize o gráfico com `Plotly.react('grafico', traces, layout, config)`.
     e) Atualize o elemento `<p id="explicacao_dinamica">` com uma explicação pedagógica dinâmica em português que interpreta o estado atual do gráfico para o estudante.

[DIRETRIZES DE ARQUITETURA E LAYOUT VERTICAL]
1. HIERARQUIA DE ELEMENTOS (DISPOSIÇÃO VERTICAL):
   - A página DEVE ser estruturada de cima para baixo na seguinte ordem:
     a) CABEÇALHO: Título e subtítulo em HTML no topo (`<h2 class="text-xl font-bold text-slate-800">{nome_simulador}</h2>`).
     b) PAINEL DE CONTROLES: Sliders (`<input type="range">`) agrupados em um card com Tailwind CSS no topo/centro, com labels claros e spans com os valores numéricos.
     c) CONTAINER DO GRÁFICO (LARGURA TOTAL 100%): O gráfico DEVE ter SEMPRE uma div explícita `<div id="grafico" class="w-full my-4" style="width: 100%; min-height: 420px; height: 460px;"></div>` ABAIXO dos controles.
     d) CARD EXPLICATIVO DINÂMICO NO RODAPÉ: `<div class="bg-blue-50/70 border border-blue-100 rounded-xl p-4 text-slate-700 text-sm mb-4"><h4 class="font-bold text-blue-900 mb-1 flex items-center gap-1">💡 Como interpretar este gráfico?</h4><p id="explicacao_dinamica" class="leading-relaxed"></p></div>`.

2. INICIALIZAÇÃO BLINDADA COM POLLING DO PLOTLY:
   - Como o Plotly é carregado via CDN assíncrono, você DEVE OBRIGATORIAMENTE usar a função de polling antes de chamar `Plotly.newPlot`:
     ```javascript
     function initSimulation() {{
       if (typeof Plotly === 'undefined') {{
         setTimeout(initSimulation, 50);
         return;
       }}
       
       const sliders = document.querySelectorAll('input[type="range"]');
       sliders.forEach(s => s.addEventListener('input', updateChart));
       
       updateChart();
     }}

     function updateChart() {{
       // 1. Lê valores dos sliders e atualiza spans
       // 2. Calcula arrays X e Y a partir da fórmula matemática
       // 3. Renderiza no Plotly com eixos fixos
       Plotly.react('grafico', traces, layout, config);
       
       // 4. Atualiza explicação dinâmica em português
       // 5. Notifica o iframe pai para ajuste de altura
       if (window.parent) {{
         window.parent.postMessage({{ type: 'resize', height: document.body.scrollHeight + 60 }}, '*');
       }}
     }}

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
    <div class="bg-slate-50 p-4 rounded-xl border border-slate-200 grid grid-cols-1 md:grid-cols-2 gap-4">
      <!-- Sliders aqui com seus respectivos labels e spans -->
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
      const sliders = document.querySelectorAll('input[type="range"]');
      sliders.forEach(s => s.addEventListener('input', updateChart));
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

def gerar_simulador_html(tema_aula: str, nome_simulador: str, logger=None, modelo_llm: str = "hibrido", tracker=None) -> str:
    """
    Gera um código HTML/JS completo para uma simulação interativa usando Gemini com Structured Outputs.
    """
    client = get_genai_client()
    
    from telemetry import resolver_modelo
    modelo_alvo = resolver_modelo("simulador", modelo_llm)
    
    prompt = PROMPT_ENGENHEIRO_SIMULACAO.format(
        tema_aula=tema_aula,
        nome_simulador=nome_simulador
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
                    response_schema=SimuladorHTMLOutput
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
