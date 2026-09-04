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
Sua missão é criar uma simulação interativa baseada em tecnologias web nativas (HTML5, Tailwind CSS via CDN, Javascript ES6) e bibliotecas de gráficos (Plotly.js via CDN).

[CONTEXTO DA AULA E DO SUBTÓPICO]
Tema Geral da Aula: {tema_aula}
Simulação Solicitada: {nome_simulador}

Conteúdo Teórico do Subtópico:
\"\"\"{contexto_subtopico}\"\"\"

[DIRETRIZ MESTRE 1: SENSO ESTATÍSTICO REAL - PROIBIÇÃO DE SLIDERS ABSTRATOS]
1. PROIBIÇÃO DE SLIDERS ABSTRATOS OU OPERAÇÕES PURAMENTE MULTIPLICATIVAS:
   - É TERMINANTEMENTE PROIBIDO criar controles ou sliders genéricos sem sentido prático/estatístico, tais como: 'Fator de Crescimento', 'Deslocamento Base', 'Colunas Multiplicativas', 'Barras Aditivas'.
   - O simulador DEVE modelar um cenário estatístico/matemático CONCRETO com dados verossímeis e rótulos claros:
     * Para Gráficos de Barras / Colunas / Setores: Utilize categorias temáticas reais (ex: 'Regiões: Norte, Nordeste, Sudeste, Sul', 'Nível de Escolaridade', 'Cursos Universitários', 'Faixas de Renda'). Crie controles para: alterar a frequência/contagem de cada categoria, alternar entre 'Frequência Absoluta' e 'Frequência Relativa (%)', ordenar as barras (Decrescente / Crescente / Original), ou comparar duas séries reais (ex: 2023 vs 2024).
     * Para Histogramas: Controles para alterar 'Número de Classes / Largura do Intervalo (bins)', 'Tamanho da Amostra (n)', 'Média da População' e 'Assimetria'.
     * Para Boxplots: Controles para alterar 'Mediana', 'Dispersão Interquartil (IQR)', 'Assimetria' e adicionar 'Outliers (Pontos Discrepantes)'.
     * Para Gráficos de Dispersão e Regressão: Sliders para 'Inclinação da Reta (beta1)', 'Intercepto (beta0)', 'Dispersão dos Erros (sigma)' e 'Tamanho Amostral (n)'.
     * Para Distribuições de Probabilidade: Sliders com parâmetros reais (ex: probabilidade p, média mu, desvio padrao sigma, graus de liberdade).
     * Para Séries Temporais: Sliders para 'Tendência', 'Amplitude Sazonal' e 'Ruído Aleatório'.

[DIRETRIZ MESTRE 2: EIXOS FIXOS E ESTÁVEIS - OS DADOS MUDAM, NÃO A GRADE!]
1. LIMITES FIXOS NO LAYOUT:
   - No `layout` do Plotly, configure SEMPRE limites fixos e bem calibrados com `autorange: false` e `range: [min, max]` (ex: `yaxis: {{ range: [0, 50], autorange: false }}`).
   - MOTIVO: Quando o aluno move o slider, ele deve ver as barras subirem/descerem ou a curva se movimentar contra uma grade estável. É proibido fazer o slider mudar apenas a escala dos eixos.

2. DINÂMICA EM TEMPO REAL E EXPLICAÇÃO PEDAGÓGICA:
   - Na função `updateChart()`:
     a) Leia o valor de cada `<input type="range">` ou `<select>`.
     b) Atualize o `<span>` do valor correspondente formatado.
     c) Recalcule os dados estatísticos reais e atualize o gráfico com `Plotly.react('grafico', traces, layout, config)`.
     d) Atualize o elemento `<p id="explicacao_dinamica">` com um texto pedagógico em português que interpreta o resultado atual para o aluno.

[DIRETRIZES DE ARQUITETURA E LAYOUT VERTICAL]
1. HIERARQUIA: CABEÇALHO -> PAINEL DE CONTROLES (SLIDERS COM LABELS CLAROS) -> CONTAINER DO GRÁFICO (100% LARGURA, MIN-HEIGHT 420px) -> CARD EXPLICATIVO DINÂMICO NO RODAPÉ.
2. INICIALIZAÇÃO BLINDADA COM POLLING DO PLOTLY.

[CÓDIGO DE PARTIDA ESPERADO]
Retorne APENAS um documento HTML completo e válido (começando com <!DOCTYPE html> e terminando com </html>). É PROIBIDO usar marcadores de markdown (como ```html).
"""

from pydantic import BaseModel, Field

class SimuladorHTMLOutput(BaseModel):
    codigo_html_completo: str = Field(
        description="Código HTML5 completo contendo <!DOCTYPE html>, Tailwind CSS, Plotly.js e Javascript interativo em uma única string sem blocos de markdown."
    )

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
