import re
import json

def sanitize_display_math(content: str) -> str:
    """Sanitiza o conteúdo interno de um bloco de Display Math ($$...$$)."""
    c = content.strip()
    
    # 1. Remove qualquer cifrão interno ($), pois no KaTeX é terminantemente proibido $ dentro de $$
    c = c.replace('$', '')
    
    # 2. Converte ambientes incompatíveis com o rehype-katex
    c = re.sub(r'\\begin\{(align\*?|equation\*?|gather\*?|split\*?)\}', r'\\begin{aligned}', c)
    c = re.sub(r'\\end\{(align\*?|equation\*?|gather\*?|split\*?)\}', r'\\end{aligned}', c)
    
    # 3. Converte macros incompatíveis e comandos inexistentes
    c = re.sub(r'\\hat\{\\Y\}', r'\\hat{Y}', c)
    c = re.sub(r'\\Y(?=[_^\s\{\}\)])', r'Y', c)
    c = re.sub(r'\\bm\{', r'\\boldsymbol{', c)
    c = re.sub(r'\\bold\{', r'\\mathbf{', c)
    c = re.sub(r'\\+boldsymbol\\+\{([^}]+)\}', r'\\boldsymbol{\1}', c)
    c = re.sub(r'\\+boldsymbol\\+\{', r'\\boldsymbol{', c)
    c = re.sub(r'\\+mathbf\\+\{', r'\\mathbf{', c)
    c = re.sub(r'(\t|\\+)hicksim', r'\\sim', c)
    c = re.sub(r'\\+nginxed', r'\\in', c)
    
    # 4. Corrige chaves fechadas com escape indevido em subscritos, \text{...}\} ou \frac{...}\}
    c = re.sub(r'([_^])\\\{', r'\1{', c)
    c = re.sub(r'\\text\{([^}]+)\\\}', r'\\text{\1}', c)
    c = re.sub(r'\\text\{([^}]+)\}\\\}', r'\\text{\1}}', c)
    if r'\{' not in c:
        c = c.replace(r'\}', '}')
    
    # 5. Converte moedas dentro do math
    c = re.sub(r'\\text\{R[\\\$]*\}', r'\\text{R\\$}', c)
    c = re.sub(r'\\text\{US[\\\$]*\}', r'\\text{US\\$}', c)

    # 6. Escapa porcentagem solta dentro do math
    c = re.sub(r'(?<!\\)%', r'\\%', c)
    
    # 7.5 Recupera abertura de ambientes quando o modelo esqueceu o \begin{...} correspondente
    for env in ['pmatrix', 'bmatrix', 'matrix', 'vmatrix', 'cases', 'aligned']:
        if f'\\end{{{env}}}' in c and f'\\begin{{{env}}}' not in c:
            c = f"\\begin{{{env}}}\n" + c
        if f'\\begin{{{env}}}' in c and f'\\end{{{env}}}' not in c:
            c = c + f"\n\\end{{{env}}}"

    # 8. Se contiver quebra crua '\\' sem nenhum \begin{...} ambiente, encapsula em \begin{aligned}
    if r'\begin{' not in c and r'\\' in c:
        c = "\\begin{aligned}\n" + c + "\n\\end{aligned}"
    
    # 9. Se contiver múltiplos axiomas/equações separados por \quad ou \qquad, converte em \begin{aligned} com \\
    if r'\begin{' not in c and (r'\qquad' in c or r'\quad' in c):
        c_lines = [l.strip() for l in re.split(r'\\qquad|\\quad', c) if l.strip()]
        if len(c_lines) > 1:
            c = "\\begin{aligned}\n" + " \\\\\n".join(c_lines) + "\n\\end{aligned}"
    
    return c.strip()

def sanitize_inline_math(content: str) -> str:
    """Sanitiza o conteúdo interno de um bloco de Inline Math ($...$)."""
    c = content.strip()
    c = c.replace('$', '')
    c = re.sub(r'\\hat\{\\Y\}', r'\\hat{Y}', c)
    c = re.sub(r'\\Y(?=[_^\s\{\}\)])', r'Y', c)
    c = re.sub(r'\\bm\{', r'\\boldsymbol{', c)
    c = re.sub(r'\\bold\{', r'\\mathbf{', c)
    c = re.sub(r'\\+boldsymbol\\+\{([^}]+)\}', r'\\boldsymbol{\1}', c)
    c = re.sub(r'\\+boldsymbol\\+\{', r'\\boldsymbol{', c)
    c = re.sub(r'\\+nginxed', r'\\in', c)
    c = re.sub(r'(?<!\\)%', r'\\%', c)
    c = re.sub(r'\\text\{R[\\\$]*\}', r'\\text{R\\$}', c)
    c = re.sub(r'\\text\{US[\\\$]*\}', r'\\text{US\\$}', c)
    c = re.sub(r'([_^])\\\{', r'\1{', c)
    c = re.sub(r'\\text\{([^}]+)\\\}', r'\\text{\1}', c)
    c = re.sub(r'\\text\{([^}]+)\}\\\}', r'\\text{\1}}', c)
    if r'\{' not in c:
        c = c.replace(r'\}', '}')
    c = re.sub(r'\\\s*$', '', c)
    return c.strip()

def sanitize_latex_string(text: str) -> str:
    """
    Sanitiza e normaliza deterministicamente qualquer string contendo notações LaTeX
    usando uma abordagem de tokenização por Árvore de Blocos segura e sem destruição de delimitadores.
    """
    if not isinstance(text, str) or not text.strip():
        return text

    processed = text.strip()

    # 1.0 Converte quebras de linha literais escapadas (\n\n ou \n) para quebras de linha reais no Markdown
    processed = processed.replace(r'\r\n', '\n')
    processed = re.sub(r'\\n\\n+', '\n\n', processed)
    processed = re.sub(r'\\n(?=[\s\n\r\t\d.,;:!?\(\)\[\]\{\}"\'“”«»A-ZÁ-ÿ])', '\n', processed)
    processed = re.sub(r'\\n(?![a-z])', '\n', processed)

    # 1.1 Limpa moedas isoladas para evitar criação de falsos ambientes matemáticos
    processed = re.sub(r'(?<!\\)R\$\s*(\d)', r'R\\$ \1', processed)
    processed = re.sub(r'(?<!\\)US\$\s*(\d)', r'US\\$ \1', processed)
    processed = re.sub(r'R\$\\(?!\$)', r'R\\$', processed)

    # 1.2 Limpa entidades HTML corrompidas ou grafias quebradas comuns
    processed = processed.replace("&bar;", r"\bar ").replace("&sum;", r"\sum ").replace("&Sigma;", r"\Sigma ")
    processed = re.sub(r'\\bar([a-zA-Z])(?![a-zA-Z])', r'\\bar{\1}', processed)
    processed = re.sub(r'\\Sigma(?=\s*\(x_i)', r'\\sum', processed)

    # 1.3 Recupera caracteres de controle gerados por escape indevido em JS (\f -> \frac, \b -> \bar, perda de barras)
    processed = re.sub(r'[\x0c\u000c]rac', r'\\frac', processed)
    processed = re.sub(r'[\x08\u0008]ar\{', r'\\bar{', processed)
    processed = re.sub(r'[\x08\u0008]eta', r'\\beta', processed)
    processed = re.sub(r'[\x08\u0008]inom', r'\\binom', processed)
    processed = re.sub(r'[\x08\u0008]mathbf', r'\\mathbf', processed)
    processed = re.sub(r'(?<![\\f\x0c\u000c])rac\{', r'\\frac{', processed)
    processed = re.sub(r'(?<!\\)omega([_\s\^\{])', r'\\omega\1', processed)
    processed = re.sub(r'(?<!\\)quad(?=[\s\$\(\)])', r'\\quad', processed)

    # 1.4 Elimina blocos vazios de $$ repetidos antes de normalizar
    processed = re.sub(r'\$\$\s*\$\$', '', processed)
    processed = re.sub(r'(\n?\$\$\s*\n?){2,}', '\n$$\n', processed)

    # 2. Normaliza delimitadores clássicos LaTeX preservando espaçamento vertical como \\[8pt]
    processed = re.sub(r'(?<!\\)\\\[(?![\d\w\s.]*\])', '\n$$\n', processed)
    processed = re.sub(r'(?<!\\)\\\]', '\n$$\n', processed)
    processed = processed.replace(r'\(', '$').replace(r'\)', '$')

    # 2.3 Eleva blocos $...$ com matrizes/ambientes para $$...$$
    processed = re.sub(r'(?<!\$)\$([^\$\n]*?\\begin\{(?:pmatrix|bmatrix|matrix|cases|aligned|array)\}[\s\S]*?)\$(?!\$)', r'\n$$\n\1\n$$\n', processed)

    # 2.5 Desaninha equações onde o modelo abriu $ antes da fórmula e depois colocou $$ para a matriz
    processed = re.sub(r'(?<!\\)\$\s*([^$\n]*?)\s*\n*\$\$([\s\S]*?)\$\$\s*(?<!\\)\$', r'\n$$\n\1 \2\n$$\n', processed)
    processed = re.sub(r'(?<!\\)\$\s*\$\$', '\n$$\n', processed)
    processed = re.sub(r'\$\$\s*(?<!\\)\$', '\n$$\n', processed)

    # 3. Se a string contiver \begin{aligned} ou \begin{...} sem $$, envolve em $$
    if '$$' not in processed and r'\begin{' in processed:
        processed = re.sub(r'(\\begin\{[a-zA-Z*]+\}[\s\S]*?\\end\{[a-zA-Z*]+\})', r'\n$$\n\1\n$$\n', processed)

    # 4. Divide a string em tokens de Display Math ($$...$$), Inline Math ($...$) e Prosa
    pattern = r'(?<!\\)(\$\$[\s\S]*?(?<!\\)\$\$|(?<!\\)\$(?:[^\$\n]|\\\$)+?(?<!\\)\$)'
    parts = re.split(pattern, processed, flags=re.DOTALL)
    
    result_parts = []
    for part in parts:
        if not part:
            continue
            
        if part.startswith('$$') and part.endswith('$$') and len(part) >= 4:
            inner = part[2:-2].strip()
            if not inner:
                continue
            sanitized_inner = sanitize_display_math(inner)
            if sanitized_inner:
                result_parts.append(f"\n$$\n{sanitized_inner}\n$$\n")
        elif part.startswith('$') and part.endswith('$') and len(part) >= 2 and '\n' not in part:
            inner = part[1:-1].strip()
            if not inner:
                continue
            sanitized_inner = sanitize_inline_math(inner)
            if sanitized_inner:
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

    # 5. Anexa pontuações isoladas
    processed = re.sub(r'(\$\$[\s\S]*?\$\$)\s*\n+\s*([.,;:!?])', r'\1\2\n\n', processed)
    processed = re.sub(r'\n+\s*([.,;:!?])\s+(?=[A-Za-z0-9Á-ÿ])', r'\1 ', processed)
    processed = re.sub(r'\n+\s*([.,;:!?])\s*\n+', r'\1\n\n', processed)
    processed = re.sub(r'\.{2,}', '.', processed)

    # 6. Ajusta o espaçamento ao redor de inline math colado em palavras em português
    processed = re.sub(r'([a-zA-Z0-9áàâãéèêíóòôõúçÁÀÂÃÉÈÊÍÓÒÔÕÚÇ])\$([^$\n]+?)\$', r'\1 $\2$', processed)
    processed = re.sub(r'\$([^$\n]+?)\$([a-zA-Z0-9áàâãéèêíóòôõúçÁÀÂÃÉÈÊÍÓÒÔÕÚÇ])', r'$\1$ \2', processed)

    # 7. Remove espaços em branco no início de cada linha
    lines = processed.split('\n')
    processed_lines = [line.lstrip(' \t') for line in lines]
    processed = '\n'.join(processed_lines)

    # 8. Remove excesso de quebras de linha múltiplas e blocos vazios residuais
    processed = re.sub(r'\n{3,}', '\n\n', processed)
    processed = re.sub(r'\$\$\s*\$\$', '', processed)

    return processed.strip()

def sanitize_json_recursively(obj):
    """
    Percorre recursivamente um dicionário ou lista JSON e aplica sanitize_latex_string em cada campo de texto,
    preservando intactos códigos brutos como 'codigo_html_gerado' e garantindo idempotência e delimitadores limpos.
    """
    if isinstance(obj, str):
        return sanitize_latex_string(obj)
    elif isinstance(obj, dict):
        res = {}
        for k, v in obj.items():
            if k == "codigo_html_gerado":
                if isinstance(v, str):
                    res[k] = (v
                        .replace("val.includes('\\')", "val.indexOf(String.fromCharCode(92)) !== -1")
                        .replace("val.includes('\\\\')", "val.indexOf(String.fromCharCode(92)) !== -1")
                        .replace("val.includes('\t')", "val.indexOf('\\t') !== -1")
                        .replace("val.includes('\x0c')", "val.indexOf('\\x0c') !== -1")
                        .replace("val.includes('\x08')", "val.indexOf('\\x08') !== -1")
                    )
                else:
                    res[k] = v
            elif k == "telemetria_custo":
                res[k] = v
            elif k == "formalismo_latex" and isinstance(v, str) and v.strip() and v.strip().lower() != "null":
                f = v.strip()
                if not f.startswith("$$"):
                    f = re.sub(r'^\$+|\$+$', '', f).strip()
                    if f:
                        f = f"$$\n{f}\n$$"
                res[k] = sanitize_latex_string(f)
            else:
                res[k] = sanitize_json_recursively(v)
        return res
    elif isinstance(obj, list):
        return [sanitize_json_recursively(elem) for elem in obj]
    return obj

def safe_json_loads(text: str):
    """
    Carrega JSON de forma ultra-resiliente contra sequências de escape do LaTeX,
    como \\underline, \\upsilon (que quebram no json.loads padrão com 'Invalid \\uXXXX escape'),
    além de comandos como \\frac, \\beta, \\text, \\times, aspas internas ou strings truncadas.
    """
    if not text or not isinstance(text, str):
        return {}
    
    # 1. Tenta parse direto mais rápido se o JSON já estiver perfeito
    try:
        return json.loads(text)
    except Exception:
        pass
    
    # 2. Pré-tratamento de comandos LaTeX comuns que colidem com escapes JSON (\\u, \\f, \\b, \\t)
    # \\u que não seja seguido de 4 dígitos hexadecimais (ex: \\underline, \\upsilon, \\url)
    t = re.sub(r'(?<!\\)\\u(?![0-9a-fA-F]{4})', r'\\\\u', text)
    t = re.sub(r'(?<!\\)\\f(rac|lat)', r'\\\\f\1', t)
    t = re.sub(r'(?<!\\)\\b(eta|ar|inom|mathbf|boldsymbol|m|ig|igg|ullet)', r'\\\\b\1', t)
    t = re.sub(r'(?<!\\)\\t(ext|imes|heta|au|op|iny|ilde)', r'\\\\t\1', t)
    
    try:
        return json.loads(t)
    except Exception:
        pass
    
    # 3. Corrige qualquer outro backslash solto que não seja escape JSON válido
    t = re.sub(r'(?<!\\)\\(?![\\"/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', t)
    try:
        return json.loads(t, strict=False)
    except Exception:
        pass
        
    # 4. Motor de auto-reparo profundo (json_repair) para aspas não escapadas, strings não terminadas ou delimitadores ausentes
    try:
        import json_repair
        repaired = json_repair.loads(t)
        if isinstance(repaired, (dict, list)):
            return repaired
    except Exception:
        pass
        
    try:
        import json_repair
        repaired_raw = json_repair.loads(text)
        if isinstance(repaired_raw, (dict, list)):
            return repaired_raw
    except Exception:
        pass
    
    return json.loads(t, strict=False)
