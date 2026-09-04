# Diretrizes Padrão de Notação e Design Âncora (Plataforma 2.0)

Este documento atua como a âncora oficial de padronização estética, terminológica e notacional para a geração de conteúdos teóricos e componentes interativos na plataforma de aulas. A inteligência artificial (Gemini 3.1 Flash-Lite e outros agentes) deve ler e aplicar estas diretrizes de forma estrita em todas as etapas da geração da plataforma.

---

## 📐 1. Tabela Estrita de Tradução de Notações Matemáticas

Sempre que o agente traduzir ou deduzir formulações teóricas extraídas do RAG ou de bases científicas, ele deve converter a notação original dos livros estritamente para os símbolos padronizados abaixo. Não é permitida nenhuma variação informal ou notação divergente (como usar `n` maiúsculo para tamanho amostral ou `p` para probabilidade sem LaTeX).

### 1.1 Elementos Fundamentais de População e Amostra
| Conceito Estatístico | Símbolo Obrigatório (LaTeX) | Descrição e Contexto de Aplicação |
| :--- | :--- | :--- |
| **Tamanho Amostral** | $n$ | Número total de observações na amostra (sempre minúsculo). |
| **Tamanho Populacional** | $N$ | Total de elementos da população (sempre maiúsculo). |
| **Média Populacional** | $\mu$ | Parâmetro populacional desconhecido (média real). |
| **Média Amostral** | $\bar{X}$ | Estimador pontual da média da amostra (sempre X maiúsculo com barra). |
| **Variância Populacional** | $\sigma^2$ | Parâmetro populacional de dispersão teórica. |
| **Variância Amostral** | $S^2$ | Estimador não-viciado da variância com denominador $n-1$ (S maiúsculo). |
| **Desvio Padrão Populacional** | $\sigma$ | Raiz quadrada da variância populacional. |
| **Desvio Padrão Amostral** | $S$ | Raiz quadrada da variância amostral (S maiúsculo). |
| **Proporção Populacional** | $p$ | Parâmetro binomial de sucesso na população. |
| **Proporção Amostral** | $\hat{p}$ | Estimador da proporção de sucessos na amostra (p com acento circunflexo). |
| **Margem de Erro** | $E$ | Semi-amplitude de intervalos de confiança (E maiúsculo). |
| **Intervalo de Confiança** | $IC$ | Intervalo estimado com nível de confiança $1-\alpha$. |
| **Erro Padrão da Média** | $EP(\bar{X})$ ou $\sigma_{\bar{X}}$ | Desvio padrão da distribuição amostral da média. |

### 1.2 Testes de Hipóteses e Inferência
| Conceito Estatístico | Símbolo Obrigatório (LaTeX) | Descrição e Contexto de Aplicação |
| :--- | :--- | :--- |
| **Hipótese Nula** | $H_0$ | Formulação de estabilidade, igualdade ou efeito nulo (H maiúsculo). |
| **Hipótese Alternativa** | $H_1$ | Formulação de diferença, efeito ou desvio (sempre subscrito 1, evitar $H_a$). |
| **Nível de Significância** | $\alpha$ | Limiar de probabilidade do Erro Tipo I (rejeitar $H_0$ sendo verdadeira). |
| **Nível de Confiança** | $1 - \alpha$ | Probabilidade de não rejeitar $H_0$ sob estabilidade legítima. |
| **Probabilidade do Erro Tipo II** | $\beta$ | Probabilidade de não rejeitar $H_0$ quando ela é falsa. |
| **Poder do Teste** | $1 - \beta$ | Probabilidade de rejeitar $H_0$ sendo ela de fato falsa. |
| **P-Valor** | $p\text{-valor}$ | Probabilidade de significância observada (p minúsculo, hífem, "valor" em LaTeX). |
| **Região de Rejeição** | $RC$ | Região Crítica; conjunto de valores que levam à rejeição de $H_0$. |
| **Graus de Liberdade** | $gl$ | Parâmetro das distribuições $t$, $\chi^2$ e $F$ (evitar "df" ou "d.f."). |
| **Graus de Liberdade (Numerador)**| $gl_{\text{num}}$ | Graus de liberdade do numerador em distribuições $F$. |
| **Graus de Liberdade (Denominador)**| $gl_{\text{den}}$ | Graus de liberdade do denominador em distribuições $F$. |
| **Estatística Z Calculada** | $Z_{\text{calc}}$ | Valor Z obtido a partir da fórmula e dados amostrais. |
| **Estatística t Calculada** | $t_{\text{calc}}$ | Valor t calculado em amostras pequenas com $\sigma$ desconhecido. |
| **Estatística Qui-Quadrado Calc.** | $\chi^2_{\text{calc}}$ | Estatística qui-quadrado calculada para testes de aderência ou associação. |
| **Estatística F Calculada** | $F_{\text{calc}}$ | Estatística F calculada para testes de variância ou ANOVA. |
| **Valor Crítico Z** | $Z_{\text{crit}}$ | Limiar crítico Z na tabela normal padronizada para o nível $\alpha$. |
| **Valor Crítico t** | $t_{\text{crit}}$ | Limiar crítico t na distribuição de Student para $\alpha$ e $gl$. |
| **Valor Crítico Qui-Quadrado** | $\chi^2_{\text{crit}}$ | Limiar crítico na distribuição qui-quadrado para $\alpha$ e $gl$. |
| **Valor Crítico F** | $F_{\text{crit}}$ | Limiar crítico na distribuição F para $\alpha$, $gl_{\text{num}}$ e $gl_{\text{den}}$. |

### 1.3 Distribuições Teóricas
| Conceito Estatístico | Símbolo Obrigatório (LaTeX) | Descrição |
| :--- | :--- | :--- |
| **Distribuição Normal** | $N(\mu, \sigma^2)$ | Distribuição gaussiana com média $\mu$ e variância $\sigma^2$. |
| **Distribuição Normal Padrão** | $N(0, 1)$ | Distribuição normal parametrizada com média 0 e variância 1. |
| **Distribuição t de Student** | $t(gl)$ | Distribuição de caudas pesadas controlada por graus de liberdade $gl$. |
| **Distribuição Qui-Quadrado** | $\chi^2(gl)$ | Distribuição de somas de quadrados normalizadas com $gl$ graus de liberdade. |
| **Distribuição F de Snedecor** | $F(gl_{\text{num}}, gl_{\text{den}})$ | Distribuição do quociente de duas variâncias amostrais independentes. |
| **Distribuição Binomial** | $Bin(n, p)$ | Distribuição discreta de sucessos em ensaios independentes. |
| **Distribuição Poisson** | $Poi(\lambda)$ | Distribuição discreta de eventos em um intervalo contínuo com taxa $\lambda$. |

### 1.4 Regressão Linear, Correlação e Associação
| Conceito Estatístico | Símbolo Obrigatório (LaTeX) | Descrição e Contexto de Aplicação |
| :--- | :--- | :--- |
| **Correlação Populacional** | $\rho$ | Parâmetro de correlação linear (rho grego). |
| **Correlação Amostral** | $r$ | Coeficiente de correlação linear de Pearson na amostra (r minúsculo). |
| **Coeficiente de Determinação** | $R^2$ | Proporção da variância explicada pelo modelo de regressão (R maiúsculo). |
| **Covariância Populacional** | $\sigma_{XY}$ | Medida de associação linear entre X e Y na população. |
| **Covariância Amostral** | $S_{XY}$ | Estimador amostral de covariância linear entre X e Y. |
| **Intercepto Populacional** | $\beta_0$ | Coeficiente linear populacional da regressão. |
| **Inclinação Populacional** | $\beta_1$ | Coeficiente angular populacional da regressão. |
| **Intercepto Estimado** | $\hat{\beta}_0$ | Estimador amostral do intercepto (com acento circunflexo). |
| **Inclinação Estimada** | $\hat{\beta}_1$ | Estimador amostral da inclinação (com acento circunflexo). |
| **Resíduo Amostral** | $e_i$ | Diferença entre o valor real observador e o previsto pelo modelo: $e_i = Y_i - \hat{Y}_i$. |
| **Soma de Quadrados da Regressão** | $SQR$ | Medida de variabilidade explicada pela regressão ($SQR = \sum(\hat{Y}_i - \bar{Y})^2$). |
| **Soma de Quadrados do Erro** | $SQE$ | Medida de variabilidade não explicada/resíduo ($SQE = \sum e_i^2$). |
| **Soma de Quadrados Total** | $SQT$ | Medida de variabilidade total dos dados ($SQT = SQR + SQE$). |

---

## 📊 2. Diretrizes de Design Premium para Gráficos Estatísticos

Para garantir que os gráficos gerados pela IA sejam visualmente **extraordinários, refinados, estritamente padronizados e adequados para publicações científicas de alto impacto**, as diretrizes visuais abaixo devem ser injetadas de forma absoluta no código. **Nenhum gráfico gerado pode desviar desta folha de estilo.**

> [!IMPORTANT]
> **IMUTABILIDADE DE FORMATO E FONTE:**
> As diretrizes de formato de layout (como uso de fundos brancos/transparentes, legenda horizontal no topo, margens compactas e hoverlabels personalizados) e a família de fontes (sempre sem serifa - Arial ou DejaVu Sans) são **estritas e totalmente imutáveis**. Nem o agente gerador de código, nem os arquivos de aula individuais podem alterar estas definições de formato ou tipografia. Apenas as cores da paleta (cor principal e crítica) podem ser adaptadas dinamicamente de acordo com a identidade visual da aula.

### 🎨 2.1 Identidade Visual e Paleta de Cores Rigorosa

A paleta de cores é inspirada em design de dados moderno acadêmico, usando alta sobriedade e excelente contraste. Qualquer elemento visual deve adotar as cores hexadecimais abaixo de forma funcional:

```json
{
  "PRIMARY_BLUE": "#1E3A8A",      // Azul Escuro Acadêmico: Usado para curvas principais, dados observados e linhas de referência (customizável).
  "SECONDARY_GREEN": "#10B981",    // Verde Esmeralda: Usado para áreas de sucesso, limites de aceitação ou dados controle.
  "WARNING_AMBER": "#F59E0B",      // Laranja Âmbar: Usado para destacar pontos de transição ou desvios moderados.
  "CRITICAL_RED": "#991B1B",       // Vermelho Alerta Escuro: Usado estritamente para a Região de Rejeição (RC) e áreas críticas (customizável).
  "LIGHT_SLATE": "#F8FAFC",        // Fundo Sutil de Painel: Usado em áreas de preenchimento ou backgrounds de plotagem secundários.
  "GRID_GRAY": "#E2E8F0",          // Cinza Sutil para Grades: Usado nas linhas tracejadas de apoio (grid).
  "TEXT_MAIN": "#1E293B",          // Grafite Escuro: Usado para todos os títulos de eixos e textos principais.
  "TEXT_MUTED": "#64748B"          // Cinza Médio: Usado para rótulos secundários, ticks de eixos e legendas auxiliares.
}
```

### 🔤 2.2 Tipografia e Hierarquia de Fontes (Imutáveis)

Para assegurar legibilidade em qualquer dispositivo, a tipografia é fixa e não pode ser customizada ou alterada:
* **Família de Fontes Principal**: Utilizar fontes limpas e sem serifa (`'DejaVu Sans'`, `'Arial'`, `'sans-serif'`).
* **Uso de LaTeX**: Todas as fórmulas matemáticas inseridas em legendas, rótulos de eixos ou títulos do gráfico **devem ser escritas em formato de "raw string" LaTeX**, por exemplo: `r"Média Amostral ($\bar{X}$)"`.
* **Escala de Tamanhos Estrita**:
  * **Título Principal da Figura**: `14pt` (em negrito, cor `TEXT_MAIN`).
  * **Títulos dos Eixos (X e Y)**: `11pt` (cor `TEXT_MAIN`).
  * **Rótulos dos Eixos (Ticks)**: `9pt` (cor `TEXT_MUTED`).
  * **Textos de Legenda**: `9pt` (cor `TEXT_MUTED`).
  * **Anotações de Pontos Únicos**: `10pt` (cor `TEXT_MAIN`, peso normal).

---

### 🐍 Cenário A: Se o motor gráfico ativo for SEABORN / MATPLOTLIB

O código de plotagem em Python deve ser estruturado de forma milimétrica. A IA deve gerar os gráficos incorporando o seguinte template de estilização padrão:

```python
import matplotlib.pyplot as plt
import seaborn as sns

# 1. Configurar tema global antes de instanciar a figura
sns.set_theme(style="whitegrid", rc={
    "grid.linestyle": "--",
    "grid.alpha": 0.5,
    "grid.color": "#E2E8F0",
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans", "Helvetica"]
})

# 2. Instanciar figura com DPI alto e tamanho fixado para consistência
fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
fig.patch.set_facecolor('#FFFFFF')
ax.set_facecolor('#FFFFFF')

# [Espaço Reservado para a Geração do Gráfico - Linhas, Barras, Distribuições]
# Exemplo de preenchimento de curva com transparência (Shading)
# ax.fill_between(x, y, color="#1E3A8A", alpha=0.15)
# ax.plot(x, y, color="#1E3A8A", linewidth=2.5)

# 3. Limpeza de Bordas Acadêmica (Despine)
# Mantém apenas as linhas guia sutis inferiores e esquerdas se necessário
sns.despine(left=True, bottom=False, right=True, top=True)

# 4. Rótulos Estritos com LaTeX e Variáveis Notacionais Corretas
ax.set_title("Título Estruturado do Gráfico", fontsize=14, fontweight="bold", pad=15, color="#1E293B")
ax.set_xlabel(r"Eixo X ($\bar{X}$)", fontsize=11, labelpad=8, color="#1E293B")
ax.set_ylabel(r"Densidade de Probabilidade ($f(x)$)", fontsize=11, labelpad=8, color="#1E293B")

# 5. Estilização de Ticks
ax.tick_params(axis='both', which='major', labelsize=9, labelcolor="#64748B")

# 6. Estilização de Legenda (Se houver)
if ax.get_legend_handles_labels()[0]:
    legend = ax.legend(frameon=True, facecolor="#F8FAFC", edgecolor="#E2E8F0", fontsize=9)
    for text in legend.get_texts():
        text.set_color("#64748B")

# 7. Renderização Segura no Streamlit
st.pyplot(fig)
plt.close(fig) # Liberar memória explicitamente
```

---

### 📊 Cenário B: Se o motor gráfico ativo for PLOTLY

O programador deve forçar uma folha de estilo web premium, fluida e totalmente otimizada para mobile. O layout Plotly deve ser atualizado estritamente como demonstrado abaixo:

```python
import plotly.graph_objects as go

# 1. Instanciar figura
fig = go.Figure()

# [Adicionar traces com cores estritas da paleta]
# Exemplo: fig.add_trace(go.Scatter(x=x, y=y, name="Observado", line=dict(color="#1E3A8A", width=3)))
# Exemplo 2: fig.add_trace(go.Bar(x=cat, y=val, marker_color="#10B981"))

# 2. Configurações Estritas de Layout e Estética
fig.update_layout(
    template="plotly_white",
    height=420,
    margin=dict(l=55, r=30, t=65, b=55, pad=4),
    
    # Título Principal do Gráfico
    title=dict(
        text="<b>Título Estruturado do Gráfico</b>",
        font=dict(size=14, color="#1E293B", family="Arial, sans-serif"),
        x=0.0,  # Alinhamento à esquerda elegante
        y=0.95
    ),
    
    # Configuração de Eixos e Estabilidade Mobile (fixedrange=True)
    xaxis=dict(
        title=dict(
            text=r"Estatística de Teste ($Z_{\text{calc}}$)",
            font=dict(size=11, color="#1E293B", family="Arial, sans-serif")
        ),
        tickfont=dict(size=9, color="#64748B", family="Arial, sans-serif"),
        gridcolor="#E2E8F0",
        zerolinecolor="#CBD5E1",
        fixedrange=True  # Impede zoom acidental no celular ao rolar
    ),
    yaxis=dict(
        title=dict(
            text=r"Densidade",
            font=dict(size=11, color="#1E293B", family="Arial, sans-serif")
        ),
        tickfont=dict(size=9, color="#64748B", family="Arial, sans-serif"),
        gridcolor="#E2E8F0",
        zerolinecolor="#CBD5E1",
        fixedrange=True  # Impede zoom acidental no celular ao rolar
    ),
    
    # Posicionamento Dinâmico da Legenda (Horizontal sobre o gráfico)
    showlegend=True,
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1.0,
        font=dict(size=9, color="#64748B", family="Arial, sans-serif"),
        bgcolor="rgba(255, 255, 255, 0.8)",
        bordercolor="#E2E8F0",
        borderwidth=1
    ),
    
    # Caixa de Dica Flutuante Premium (Hover)
    hoverlabel=dict(
        bgcolor="#FFFFFF",
        font_size=12,
        font_color="#1E293B",
        font_family="Arial, sans-serif"
    )
)

# 3. Renderização no Streamlit forçando largura total responsiva
st.plotly_chart(fig, use_container_width=True)
```
