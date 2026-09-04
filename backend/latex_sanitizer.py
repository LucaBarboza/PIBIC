import re

def sanitize_display_math(content: str) -> str:
    """Sanitiza o conteúdo interno de um bloco de Display Math ($$...$$)."""
    c = content.strip()
    # 1. Converte ambientes incompatíveis com o rehype-katex
    c = re.sub(r'\\begin\{(align\*?|equation\*?|gather\*?|split\*?)\}', r'\\begin{aligned}', c)
    c = re.sub(r'\\end\{(align\*?|equation\*?|gather\*?|split\*?)\}', r'\\end{aligned}', c)
    
    # 2. Converte macros incompatíveis e limpa chaves escapadas
    c = re.sub(r'\\bm\{', r'\\boldsymbol{', c)
    c = re.sub(r'\\bold\{', r'\\mathbf{', c)
    c = re.sub(r'\\+boldsymbol\\+\{([^}]+)\}', r'\\boldsymbol{\1}', c)
    c = re.sub(r'\\+boldsymbol\\+\{', r'\\boldsymbol{', c)
    c = re.sub(r'\\+mathbf\\+\{', r'\\mathbf{', c)
    c = re.sub(r'(\t|\\+)hicksim', r'\\sim', c)
    c = re.sub(r'\\+nginxed', r'\\in', c)
    
    # 3. Converte \text{R...} ou moedas dentro do math
    c = re.sub(r'\\text\{R[\\\$]*\}', r'\\text{R\\$}', c)
    c = re.sub(r'\\text\{US[\\\$]*\}', r'\\text{US\\$}', c)

    # 4. Remove cifrões que o modelo possa ter inserido DENTRO de blocos matemáticos
    c = re.sub(r'(?<!\\)\$', '', c)

    # 5. Escapa porcentagem solta dentro do math
    c = re.sub(r'(?<!\\)%', r'\\%', c)
    
    # 6. Trunca falhas em \right
    c = re.sub(r'[\s\r\n\t]+ight([\)\}\]|\\])', r' \\right\1', c)
    c = re.sub(r'[\s\r\n\t]+ight', r' \\right', c)
    
    # 7. Se contiver quebra crua '\\' sem nenhum \begin{...} ambiente, encapsula em \begin{aligned}
    if r'\begin{' not in c and r'\\' in c:
        c = "\\begin{aligned}\n" + c + "\n\\end{aligned}"
    elif r'\begin{' not in c:
        # Se contiver múltiplos axiomas / propriedades em uma única linha
        has_multiple_quads = len(re.findall(r'\\q?quad', c)) >= 2
        has_comma_quad = bool(re.search(r',\s*\\q?quad', c))
        has_numbered_items = bool(re.search(r'\d+\.\s*(?:\\quad|\s*)', c))
        
        if has_comma_quad or (has_multiple_quads and len(c) > 40) or (has_numbered_items and len(c) > 30):
            if has_comma_quad:
                parts = re.split(r',\s*(?:\\q?quad|\s)+', c)
            elif has_numbered_items:
                parts = re.split(r'(?=(?:\d+\.|\bAxioma\s+\d+:?)\s*(?:\\quad|\s*))', c)
            else:
                parts = re.split(r'\s*(?:\\qquad|\\quad)+\s*', c)
                
            parts = [p.strip().rstrip(',;') for p in parts if p.strip()]
            if len(parts) > 1:
                c = "\\begin{aligned}\n" + " \\\\\n".join(parts) + "\n\\end{aligned}"
    
    return c.strip()

def sanitize_inline_math(content: str) -> str:
    """Sanitiza o conteúdo interno de um bloco de Inline Math ($...$)."""
    c = content
    c = re.sub(r'\\bm\{', r'\\boldsymbol{', c)
    c = re.sub(r'\\bold\{', r'\\mathbf{', c)
    c = re.sub(r'\\+boldsymbol\\+\{([^}]+)\}', r'\\boldsymbol{\1}', c)
    c = re.sub(r'\\+boldsymbol\\+\{', r'\\boldsymbol{', c)
    c = re.sub(r'\\+nginxed', r'\\in', c)
    c = re.sub(r'(?<!\\)%', r'\\%', c)
    c = re.sub(r'\\text\{R[\\\$]*\}', r'\\text{R\\$}', c)
    c = re.sub(r'\\text\{US[\\\$]*\}', r'\\text{US\\$}', c)
    c = re.sub(r'(?<!\\)\$', '', c)
    return c.strip()

def sanitize_latex_string(text: str) -> str:
    """
    Sanitiza e normaliza deterministicamente qualquer string contendo notações LaTeX
    usando uma abordagem de tokenização por Árvore de Blocos (Context-Aware).
    """
    if not isinstance(text, str) or not text.strip():
        return text

    processed = text.strip()

    # 0.1 Limpa erros de moedas do modelo antes de tokenizar
    processed = re.sub(r'\\text\{R[\\\$]*\}\s*', 'R__DOLLAR__ ', processed)
    processed = re.sub(r'\\text\{US[\\\$]*\}\s*', 'US__DOLLAR__ ', processed)
    processed = re.sub(r'\\text\{R\}\s*', 'R__DOLLAR__ ', processed)

    # 0.2 Corrige ordinais corrompidos como 1$ vitória -> 1ª vitória
    processed = re.sub(r'(\d+)\$\s+([a-zA-Zá-ÿÁ-Ý]+)', r'\1ª \2', processed)

    # 0.3 Protege moedas padrão (R$ 1.000 ou US$ 500)
    processed = re.sub(r'(?<!\\)R\$\s*(\d)', r'R__DOLLAR__ \1', processed)
    processed = re.sub(r'(?<!\\)US\$\s*(\d)', r'US__DOLLAR__ \1', processed)
    processed = re.sub(r'R\$(?!\$)', 'R__DOLLAR__ ', processed)
    processed = re.sub(r'US\$(?!\$)', 'US__DOLLAR__ ', processed)

    # 0.4 Normaliza vírgula decimal na prosa: 1.200{,}00 -> 1.200,00
    processed = re.sub(r'(\d+)\{,\}(\d+)', r'\1,\2', processed)

    # 1. Normaliza delimitadores clássicos LaTeX
    processed = processed.replace(r'\[', '\n$$\n').replace(r'\]', '\n$$\n')
    processed = processed.replace(r'\(', '$').replace(r'\)', '$')

    # 1.0 Desembrulha \text{...} solto na prosa
    processed = re.sub(r'^\s*\\text\{([^}]+)\}\s*$', r'\1', processed, flags=re.MULTILINE)

    # 1.1 Se um bloco $ ... $ contém prosa longa em português, desembrulha a prosa
    def desembrulhar_prosa_em_inline(m):
        inner = m.group(1)
        words = inner.strip().split()
        has_long_prose = len(words) > 5 and bool(re.search(r'[a-zA-ZáàâãéèêíóòôõúçÁÀÂÃÉÈÊÍÓÒÔÕÚÇ]{4,}', inner))
        if has_long_prose and r'\frac' not in inner and r'\sum' not in inner and r'\int' not in inner:
            return inner
        return m.group(0)
    processed = re.sub(r'(?<!\$)\$(?!\$)([\s\S]*?)(?<!\$)\$(?!\$)', desembrulhar_prosa_em_inline, processed)

    # 1.2 Corrige cifrões desbalanceados por parágrafo
    paragraphs = processed.split('\n\n')
    balanced_paragraphs = []
    for p in paragraphs:
        temp_p = p.replace('$$', '')
        single_dollars = len(re.findall(r'(?<!\\)\$', temp_p))
        if single_dollars % 2 != 0:
            p = re.sub(r'(\$[^$\n]+?)([\.\,\;\:\?\!]|(?=\n)|$)', r'\1$\2', p, count=1)
        balanced_paragraphs.append(p)
    processed = '\n\n'.join(balanced_paragraphs)

    # 2. Se a string contiver \begin{aligned} ou \begin{...} sem $$, envolve em $$
    if '$$' not in processed and r'\begin{' in processed:
        processed = re.sub(r'(\\begin\{[a-zA-Z*]+\}[\s\S]*?\\end\{[a-zA-Z*]+\})', r'\n$$\n\1\n$$\n', processed)

    # 3. Divide a string em tokens de Display Math ($$...$$), Inline Math ($...$) e Prosa
    pattern = r'(?<!\\)(\$\$[\s\S]*?(?<!\\)\$\$|(?<!\\)\$(?:[^\$\n]|\\\$)+?(?<!\\)\$)'
    parts = re.split(pattern, processed, flags=re.DOTALL)
    
    result_parts = []
    for part in parts:
        if not part:
            continue
            
        if part.startswith('$$') and part.endswith('$$') and len(part) >= 4:
            inner = part[2:-2].strip()
            # Se o bloco de display for na verdade um parágrafo de texto puro em português (ex: \text{Dado um conjunto...})
            clean_text = re.sub(r'^\s*\\text\{([^}]+)\}\s*$', r'\1', inner)
            words = clean_text.split()
            if len(words) > 6 and bool(re.search(r'[a-zA-ZáàâãéèêíóòôõúçÁÀÂÃÉÈÊÍÓÒÔÕÚÇ]{4,}', clean_text)) and r'\frac' not in inner and r'\sum' not in inner and '=' not in inner:
                result_parts.append(f"\n\n{clean_text}\n\n")
                continue

            sanitized_inner = sanitize_display_math(inner)
            result_parts.append(f"\n$$\n{sanitized_inner}\n$$\n")
        elif part.startswith('$') and part.endswith('$') and len(part) >= 2 and '\n' not in part:
            inner = part[1:-1]
            sanitized_inner = sanitize_inline_math(inner)
            result_parts.append(f"${sanitized_inner}$")
        else:
            # Prosa comum (fora de cifrões)
            prose = part
            # Auto-wrap para binom solto na prosa
            prose = re.sub(r'(?<!\$)(?<!\\)(\\(?:d?binom|tbinom)\{[^}]+\}\{[^}]+\})(?!\$)', r' $\1$ ', prose)
            
            # Desembrulha \text{...} solto na prosa
            prose = re.sub(r'\\text\{([^}]+)\}', r'\1', prose)

            # Símbolos gregos e matemáticos isolados soltos na prosa
            symbols_to_wrap = r'\\(?:mu|sigma|alpha|beta|theta|lambda|pi|gamma|delta|epsilon|varepsilon|phi|omega|rho|tau|eta|chi|psi|zeta|Omega|Sigma|Delta|Theta|Gamma|Phi|Psi|Lambda|forall|exists|rightarrow|Rightarrow|infty|partial|mathcal\{[A-Za-z]\})'
            prose = re.sub(r'(?<!\$)(?<!\\)(' + symbols_to_wrap + r')(?!\$)', r' $\1$ ', prose)
            result_parts.append(prose)

    processed = "".join(result_parts)

    # 4. Anexa pontuações isoladas
    processed = re.sub(r'(\$\$[\s\S]*?\$\$)\s*\n+\s*([.,;:!?])', r'\1\2\n\n', processed)
    processed = re.sub(r'\n+\s*([.,;:!?])\s+(?=[A-Za-z0-9Á-ÿ])', r'\1 ', processed)
    processed = re.sub(r'\n+\s*([.,;:!?])\s*\n+', r'\1\n\n', processed)
    processed = re.sub(r'\.{2,}', '.', processed)

    # 5. Ajusta o espaçamento ao redor de inline math colado em palavras em português
    processed = re.sub(r'([a-zA-Z0-9áàâãéèêíóòôõúçÁÀÂÃÉÈÊÍÓÒÔÕÚÇ])\$([^$\n]+?)\$', r'\1 $\2$', processed)
    processed = re.sub(r'\$([^$\n]+?)\$([a-zA-Z0-9áàâãéèêíóòôõúçÁÀÂÃÉÈÊÍÓÒÔÕÚÇ])', r'$\1$ \2', processed)

    # 6. Remove espaços em branco no início de cada linha
    lines = processed.split('\n')
    processed_lines = [line.lstrip(' \t') for line in lines]
    processed = '\n'.join(processed_lines)

    # 7. Remove excesso de quebras de linha múltiplas mantendo no máximo parágrafo duplo (\n\n)
    processed = re.sub(r'\n{3,}', '\n\n', processed)

    # 8. Restaura símbolos monetários
    processed = processed.replace('R__DOLLAR__', r'R\$')
    processed = processed.replace('US__DOLLAR__', r'US\$')

    return processed

def sanitize_json_recursively(obj):
    """
    Percorre recursivamente um dicionário ou lista JSON e aplica sanitize_latex_string em cada campo de texto,
    preservando intactos códigos brutos como 'codigo_html_gerado'.
    """
    if isinstance(obj, str):
        return sanitize_latex_string(obj)
    elif isinstance(obj, dict):
        return {k: (v if k == "codigo_html_gerado" else sanitize_json_recursively(v)) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_json_recursively(elem) for elem in obj]
    return obj
