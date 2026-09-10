from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal

# ==========================================
# SCHEMA DE OVERRIDE DE DIRETRIZES
# ==========================================

class ItemNotacaoEspecifica(BaseModel):
    conceito: str = Field(description="O conceito matemático ou estatístico (ex: média populacional, desvio padrão, independência).")
    notacao_latex: str = Field(description="A notação exata em formato LaTeX exigida pelo professor (ex: \\mu, \\sigma, \\perp).")

class RegraOverride(BaseModel):
    tom_e_linguagem_professor: Optional[str] = Field(
        default=None,
        description="Perfil pedagógico descritivo e aprofundado (parágrafo rico e detalhado) capturando a voz e identidade do professor: tom didático (ex: instigante, acolhedor, pragmático, formal), nível de diálogo com o aluno, vocabulário e expressões características, tipo de metáforas/analogias preferidas e ritmo de condução das explicações."
    )
    notacoes_estatisticas_especificas: Optional[List[ItemNotacaoEspecifica]] = Field(
        default=None,
        description="Lista de mapeamentos de conceitos estatísticos/matemáticos para a notação exata em LaTeX exigida pelo professor."
    )
    topicos_obrigatorios: Optional[List[str]] = Field(
        default=None,
        description="Lista de tópicos ou subtópicos que não podem faltar no roteiro da aula."
    )
    estilo_exercicios: Optional[str] = Field(
        default=None,
        description="Instruções sobre o formato, dificuldade ou estilo dos exercícios gerados."
    )
    outras_diretrizes: Optional[str] = Field(
        default=None,
        description="Anotações gerais e contextuais extraídas do documento."
    )

class MaterialBaseExtraido(BaseModel):
    titulo_ou_tema: str = Field(description="Título ou tema central do documento PDF fornecido pelo professor.")
    visao_geral_pedagogica: str = Field(description="Resumo pedagógico e didático da abordagem e objetivos da aula contidos nas notas.")
    sequencia_topicos: List[str] = Field(description="Lista sequencial dos tópicos e subtópicos na ordem exata apresentada pelo professor.")
    formulas_e_definicoes_latex: List[str] = Field(description="Todas as fórmulas matemáticas, teoremas e definições transcritos rigorosamente em formato LaTeX ($ ou $$).")
    exemplos_e_exercicios: List[str] = Field(description="Exemplos numéricos, problemas propostos ou enunciados presentes nas notas.")
    convencoes_e_notacoes: List[str] = Field(description="Convenções de notação matemática e termos técnicos específicos empregados pelo professor.")
    conteudo_didatico_completo: str = Field(description="Texto aprofundado e completo articulando todo o conteúdo conceitual e didático das notas do professor.")

# ==========================================
# SCHEMAS DO AGENTE 1 (ROTEIRISTA PEDAGÓGICO)
# ==========================================

class SubtopicoRoteiro(BaseModel):
    titulo: str = Field(description="Título conceitual elegante e direto do sub-tópico.")
    conceitos_chave_rag: List[str] = Field(description="Lista de 3 a 5 termos estatísticos específicos e exatos para guiar a busca vetorial (RAG).")

class RoteiroCompletoAula(BaseModel):
    topico_principal: str = Field(description="Título principal e contextualizado da aula.")
    esquema_paginas: List[SubtopicoRoteiro] = Field(description="Sequência lógica e cronológica de subtópicos pedagógicos.")

# ==========================================
# SUB-OBJETOS AUXILIARES
# ==========================================

class EstruturaExemplo(BaseModel):
    enunciado: str = Field(description="O problema proposto com contextualização acadêmica detalhada.")
    passo_a_passo_solucao: List[str] = Field(description="Lista contendo os passos lógicos e cálculos intermediários em LaTeX.")
    resultado_final: str = Field(description="A conclusão direta e interpretação prática do problema.")

class ExemploResolvidoRico(BaseModel):
    contexto_e_enunciado: str = Field(
        description="Enunciado longo e contextualizado em um cenário real (mínimo 2 parágrafos). Deve descrever o problema prático, a origem dos dados e os objetivos da análise."
    )
    dados_brutos_sumarizados: str = Field(
        description="Exibição clara e organizada dos dados descritivos em LaTeX (ex: sum_x, sum_y, n, barras) necessários para o cálculo."
    )
    desenvolvimento_aritmético_passo_a_passo: List[str] = Field(
        description="Lista exaustiva mostrando a substituição numérica em cada fórmula. Proibido pular etapas de cálculo ou jogar resultados diretos."
    )
    conclusao_e_laudo_comercial: str = Field(
        description="Interpretação prática e qualitativa do resultado final para o tomador de decisão (mínimo 1 parágrafo denso)."
    )

class FonteRDetalhada(BaseModel):
    livro_autor: str = Field(description="Nome do livro e sobrenome do autor (ex: Bussab & Morettin, Wooldridge).")
    capitulo: str = Field(description="Capítulo específico consultado no documento RAG.")
    paginas_utilizadas: str = Field(description="Número exato da página ou intervalo de páginas de onde o conteúdo foi extraído (ex: p. 234, pp. 112-115). Obrigatório.")

# ==========================================
# SCHEMAS DO AGENTE 2 (ESCRITOR TEÓRICO)
# ==========================================

class ConteudoSubtopico(BaseModel):
    """
    Modelo unificado e determinístico de conteúdo do subtópico.
    Evita o uso de Union (anyOf/oneOf) que gera erros de compatibilidade na API do Gemini (Structured Outputs).
    """
    tipo_bloco: Literal["teorico"] = Field(
        default="teorico",
        description="O tipo do bloco: sempre 'teorico'."
    )
    
    # ----------------------------------------------------
    # CAMPOS COMUNS
    # ----------------------------------------------------
    conceito_intuitivo: str = Field(description="Explicação profunda do conceito em linguagem natural e fluida, sem formalismo matemático ainda.")
    conceito_formal: Optional[str] = Field(default=None, description="Definição matemática precisa ou enunciado acadêmico formal em LaTeX. Se o subtópico for histórico/qualitativo/conceitual (sem fórmulas próprias), retorne estritamente null.")
    propriedades_do_conceito: Optional[List[str]] = Field(default=None, description="Lista de regras, teoremas ou leis que este conceito segue (ou null se qualitativo/histórico).")
    pre_requisitos_e_auxiliares: Optional[List[str]] = Field(default=None, description="Mapeamento de ferramentas matemáticas ou aulas passadas necessárias aqui (ou null se não houver).")
    condicoes_de_contorno: Optional[List[str]] = Field(default=None, description="Suposições obrigatórias para que a teoria seja válida (ou null/N/A se não aplicável).")
    
    # --- CAMPO ACIONADOR DE INTERATIVIDADE E MÚLTIPLOS GRÁFICOS ---
    simuladores_interativos_recomendados: Optional[List[str]] = Field(
        default=None, 
        description="Lista de propostas de simulações/visualizações interativas (priorizando Plotly com sliders/controles reativos) para este subtópico. Pode conter mais de uma proposta ou None se não aplicável."
    )
    
    # ----------------------------------------------------
    # CAMPOS ESPECÍFICOS DE CONTEÚDO TEÓRICO
    # ----------------------------------------------------
    deducao_formal_passo_a_passo: Optional[List[str]] = Field(
        default=None,
        description="O passo a passo detalhado da derivação matemática das fórmulas em LaTeX (ou null se for subtópico conceitual/qualitativo/histórico)."
    )
    interpretacao_geometrica_grafica: Optional[str] = Field(
        default=None,
        description="A descrição de como visualizar esse conceito espacialmente ou em gráficos (ou null se não aplicável)."
    )
    
    # ----------------------------------------------------
    # EXEMPLO CANÔNICO
    # ----------------------------------------------------
    exemplo_canonico: Optional[EstruturaExemplo] = Field(
        default=None,
        description="O exemplo estruturado ou None."
    )

class SubtopicoValidado(BaseModel):
    titulo_subtopico: str
    conteudo: ConteudoSubtopico = Field(description="O conteúdo do subtópico estruturado (teórico).")
    fontes_rag: List[FonteRDetalhada] = Field(description="Lista de fontes bibliográficas detalhadas extraídas estritamente do RAG.")

# ==========================================
# SCHEMAS DO AGENTE 3 (CRIADOR DE EXERCÍCIOS)
# ==========================================

class AlternativasFechadas(BaseModel):
    A: str = Field(description="Opção alternativa A.")
    B: str = Field(description="Opção alternativa B.")
    C: str = Field(description="Opção alternativa C.")
    D: str = Field(description="Opção alternativa D.")
    E: Optional[str] = Field(default=None, description="Opção alternativa E (opcional).")

class QuestaoFechada(BaseModel):
    enunciado: str = Field(description="O problema prático com uma situação estatística clara.")
    alternativas: AlternativasFechadas = Field(description="As alternativas estruturadas contendo exatamente de A a D (e opcionalmente E).")
    alternativa_correta: str = Field(description="A letra da alternativa correta (Ex: 'A', 'B', 'C', 'D' ou 'E').")
    dica: str = Field(description="Orientação sutil para o aluno pensar, sem dar a resposta direta.")
    gabarito_comentado: str = Field(description="Explicação detalhada do porquê aquela alternativa é a correta.")

class QuestaoAberta(BaseModel):
    enunciado: str = Field(description="Pergunta discursiva ou problema de cálculo estatístico detalhado.")
    dica: str = Field(description="Diretriz conceitual ou fórmula que o aluno deve lembrar para resolver.")
    gabarito_passo_a_passo: List[str] = Field(description="Passo a passo matemático para se chegar à resolução completa.")

class CadernoExerciciosValidado(BaseModel):
    topico_aula: str
    questoes_multipla_escolha: List[QuestaoFechada] = Field(
        description="Lista contendo obrigatoriamente pelo menos 5 questões de múltipla escolha complexas."
    )
    questoes_discursivas: List[QuestaoAberta] = Field(
        description="Lista contendo obrigatoriamente pelo menos 3 questões discursivas/cálculos complexas."
    )

class PaginaLapidada(BaseModel):
    titulo_subtopico: str
    discussao_teorica_prosa: str = Field(description="Texto em prosa dividida em parágrafos bem espaçados (use \\n\\n para separar). É proibido usar listas ou bullets.")
    prosa_longa_expandida: Optional[str] = Field(default=None, description="Texto extremamente longo, denso e exaustivo em prosa fluida gerado pelo Construtor de Prosa.")
    formalismo_latex: Optional[str] = Field(default=None, description="Bloco de fórmulas em LaTeX ($$). Se o subtópico for histórico, filosófico ou qualitativo (sem equações próprias), retorne estritamente null.")
    
    # Mudança de String para List para forçar a abertura de todas as linhas matemáticas
    deducao_analitica_linhas: Optional[List[str]] = Field(
        default=None,
        description="A derivação matemática completa dividida linha por linha em LaTeX ($$). Se o assunto for conceitual/histórico e não exigir demonstração algébrica, retorne estritamente null."
    )
    
    # Exemplos práticos: ricos quando o tópico demandar cálculo, ou lista vazia [] em páginas puramente conceituais/históricas
    exemplos_praticos_ricos: Optional[List[ExemploResolvidoRico]] = Field(
        default_factory=list,
        description="Lista contendo exemplos práticos e resolvidos sobre o subtópico (ou lista vazia [] se o subtópico for puramente qualitativo/histórico)."
    )

class MapeamentoSimulador(BaseModel):
    indice_pagina: str = Field(description="O índice da página (ex: '1', '2', '3') onde o simulador interativo deve ser carregado.")
    nome_simulador: str = Field(description="O nome descritivo do simulador interativo correspondente (ex: 'Visualizador de Erros').")
    codigo_html_gerado: Optional[str] = Field(default=None, description="O código HTML gerado nativamente pelo Agente Simulador.")

class AulaUnificadaELapidada(BaseModel):
    tema_global: str
    resumo_executivo_aula: str = Field(description="Resumo executivo de alto nível (1 a 2 parágrafos) do que será ensinado nesta aula. Escrito em tom acolhedor e instigante.")
    paginas_conteudo: List[PaginaLapidada] = Field(description="A sequência de páginas da aula, livre de repetições textuais ou conceituais.")
    # --- MAPEAMENTO CENTRALIZADO DE SIMULADORES (Acaba com gráficos repetidos) ---
    simuladores_da_aula: List[MapeamentoSimulador] = Field(
        description="Lista contendo o mapeamento de onde os gráficos devem entrar. Atribua gráficos apenas onde for vital, garantindo que nenhum gráfico seja igual ao outro."
    )
    # --- O RODAPÉ EXIGIDO PELO PROFESSOR ---
    referencias_bibliograficas_finais: List[str] = Field(description="Lista consolidada e unificada de livros e páginas reais utilizadas em toda a extensão da aula (sem duplicatas).")
    # --- EXERCÍCIOS PARA MÉTRICAS DA FASE 3 ---
    exercicios_da_aula: Optional[CadernoExerciciosValidado] = Field(default=None, description="O caderno de exercícios construído para a aula.")
