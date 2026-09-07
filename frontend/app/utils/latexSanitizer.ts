/**
 * Sanitizador Universal de LaTeX para a Interface Frontend (Next.js)
 * Enforces 100% valid KaTeX / ReactMarkdown parsing across titles, boxes, and prose.
 */

function sanitizeDisplayMath(content: string): string {
  let c = content.trim();
  // 1. Converte ambientes incompatíveis com o rehype-katex
  c = c.replace(/\\begin\{(align\*?|equation\*?|gather\*?|split\*?)\}/g, '\\begin{aligned}');
  c = c.replace(/\\end\{(align\*?|equation\*?|gather\*?|split\*?)\}/g, '\\end{aligned}');

  // 2. Converte macros incompatíveis e limpa chaves escapadas
  c = c.replace(/\\bm\{/g, '\\boldsymbol{');
  c = c.replace(/\\bold\{/g, '\\mathbf{');
  c = c.replace(/\\+boldsymbol\\+\{([^}]+)\}/g, '\\boldsymbol{$1}');
  c = c.replace(/\\+boldsymbol\\+\{/g, '\\boldsymbol{');
  c = c.replace(/\\+mathbf\\+\{/g, '\\mathbf{');
  c = c.replace(/(\t|\\+)hicksim/g, '\\sim');
  c = c.replace(/\\+nginxed/g, '\\in');

  // 3. Converte \text{R...} ou moedas dentro do math
  c = c.replace(/\\text\{R[\\\$]*\}/g, '\\text{R\\$}');
  c = c.replace(/\\text\{US[\\\$]*\}/g, '\\text{US\\$}');

  // 4. Remove cifrões que o modelo possa ter inserido DENTRO de blocos matemáticos
  c = c.replace(/(?<!\\)\$/g, '');

  // 5. Escapa porcentagem solta dentro do math
  c = c.replace(/(?<!\\)%/g, '\\%');

  // 6. Trunca falhas em \right
  c = c.replace(/[\s\r\n\t]+ight([\)\}\]|\\])/g, ' \\right$1');
  c = c.replace(/[\s\r\n\t]+ight/g, ' \\right');

  // 7. Se contiver quebra crua '\\' sem nenhum \begin{...} ambiente, encapsula em \begin{aligned}
  if (!c.includes('\\begin{') && c.includes('\\\\')) {
    c = `\\begin{aligned}\n${c}\n\\end{aligned}`;
  }

  return c.trim();
}

function sanitizeInlineMath(content: string): string {
  let c = content.trim();
  c = c.replace(/\\bm\{/g, '\\boldsymbol{');
  c = c.replace(/\\bold\{/g, '\\mathbf{');
  c = c.replace(/\\+boldsymbol\\+\{([^}]+)\}/g, '\\boldsymbol{$1}');
  c = c.replace(/\\+boldsymbol\\+\{/g, '\\boldsymbol{');
  c = c.replace(/\\+nginxed/g, '\\in');
  c = c.replace(/(?<!\\)%/g, '\\%');
  c = c.replace(/\\text\{R[\\\$]*\}/g, '\\text{R\\$}');
  c = c.replace(/\\text\{US[\\\$]*\}/g, '\\text{US\\$}');
  c = c.replace(/(?<!\\)\$/g, '');
  c = c.replace(/\\\\+/g, '\\');
  return c.trim();
}

export function sanitizeLatex(text: string): string {
  if (!text) return "";
  let processed = text.trim();

  // 1.0 Converte quebras de linha literais escapadas (\n\n ou \n) para quebras de linha reais no Markdown
  processed = processed.replace(/\\r\\n/g, '\n');
  processed = processed.replace(/\\n\\n+/g, '\n\n');
  processed = processed.replace(/\\n(?=[\s\n\r\t\d.,;:!?\(\)\[\]\{\}"'“”«»A-ZÁ-ÿ])/g, '\n');
  processed = processed.replace(/\\n(?![a-z])/g, '\n');

  // 1.1 Limpa entidades HTML corrompidas ou grafias quebradas comuns
  processed = processed.replace(/&bar;/g, '\\bar ').replace(/&sum;/g, '\\sum ').replace(/&Sigma;/g, '\\Sigma ');
  processed = processed.replace(/\\bar([a-zA-Z])(?![a-zA-Z])/g, '\\bar{$1}');
  processed = processed.replace(/\\Sigma(?=\s*\(x_i)/g, '\\sum');

  // 1.2 Recupera caracteres de controle gerados por escape indevido em JS (\f -> \frac, \b -> \bar, perda de barras)
  processed = processed.replace(/[\x0c\u000c]rac/g, '\\frac');
  processed = processed.replace(/[\x08\u0008]ar\{/g, '\\bar{');
  processed = processed.replace(/[\x08\u0008]eta/g, '\\beta');
  processed = processed.replace(/[\x08\u0008]inom/g, '\\binom');
  processed = processed.replace(/[\x08\u0008]mathbf/g, '\\mathbf');
  processed = processed.replace(/(?<![\\f\x0c\u000c])rac\{/g, '\\frac{');
  processed = processed.replace(/(?<!\\)omega([_\s\^\{])/g, '\\omega$1');
  processed = processed.replace(/(?<!\\)quad(?=[\s\$\(\)])/g, '\\quad');

  // 2. Normaliza delimitadores clássicos LaTeX sem destruir quebras com espaçamento como \\[8pt]
  processed = processed.replace(/(?<!\\)\\\[(?![\d\w\s.]*\])/g, '\n$$\n').replace(/(?<!\\)\\\]/g, '\n$$\n');
  processed = processed.replace(/\\\(/g, '$').replace(/\\\)/g, '$');

  // 3. Se a string contiver \begin{aligned} ou \begin{...} sem $$, envolve em $$
  if (!processed.includes('$$') && processed.includes('\\begin{')) {
    processed = processed.replace(/(\\begin\{[a-zA-Z*]+\}[\s\S]*?\\end\{[a-zA-Z*]+\})/g, '\n$$\n$1\n$$\n');
  }

  // 4. Divide a string em tokens de Display Math ($$...$$), Inline Math ($...$) e Prosa
  const pattern = /(?<!\\)(\$\$[\s\S]*?(?<!\\)\$\$|(?<!\\)\$(?:[^\$\n]|\\\$)+?(?<!\\)\$)/g;
  const parts = processed.split(pattern);

  const resultParts: string[] = [];
  for (const part of parts) {
    if (!part) continue;

    if (part.startsWith('$$') && part.endsWith('$$') && part.length >= 4) {
      const inner = part.slice(2, -2).trim();
      const sanitizedInner = sanitizeDisplayMath(inner);
      resultParts.push(`\n$$\n${sanitizedInner}\n$$\n`);
    } else if (part.startsWith('$') && part.endsWith('$') && part.length >= 2 && !part.includes('\n')) {
      const inner = part.slice(1, -1);
      const sanitizedInner = sanitizeInlineMath(inner);
      resultParts.push(`$${sanitizedInner}$`);
    } else {
      // Prosa comum (fora de cifrões)
      let prose = part;
      
      // Auto-wrap para binom solto na prosa
      prose = prose.replace(/(?<!\$)(?<!\\)(\\(?:d?binom|tbinom)\{[^}]+\}\{[^}]+\})(?!\$)/g, ' $$1 ');

      // Desembrulha \text{...} solto na prosa
      prose = prose.replace(/\\text\{([^}]+)\}/g, '$1');

      // Símbolos gregos e matemáticos isolados soltos na prosa
      const symbolsToWrap = /(?<!\$)(?<!\\)(\\(?:mu|sigma|alpha|beta|theta|lambda|pi|gamma|delta|epsilon|varepsilon|phi|omega|rho|tau|eta|chi|psi|zeta|Omega|Sigma|Delta|Theta|Gamma|Phi|Psi|Lambda|forall|exists|rightarrow|Rightarrow|infty|partial|mathcal\{[A-Za-z]\}))(?!\$)/g;
      prose = prose.replace(symbolsToWrap, (_, sym) => ` $${sym}$ `);
      resultParts.push(prose);
    }
  }

  processed = resultParts.join('');

  // 5. Anexa pontuações isoladas
  processed = processed.replace(/(\$\$[\s\S]*?\$\$)\s*\n+\s*([.,;:!?])/g, '$1$2\n\n');
  processed = processed.replace(/\n+\s*([.,;:!?])\s+(?=[A-Za-z0-9Á-ÿ])/g, '$1 ');
  processed = processed.replace(/\n+\s*([.,;:!?])\s*\n+/g, '$1\n\n');
  processed = processed.replace(/\.{2,}/g, '.');

  // 6. Ajusta o espaçamento ao redor de inline math colado em palavras em português
  processed = processed.replace(/([a-zA-Z0-9áàâãéèêíóòôõúçÁÀÂÃÉÈÊÍÓÒÔÕÚÇ])\$([^$\n]+?)\$/g, (_, w, m) => `${w} $${m}$`);
  processed = processed.replace(/\$([^$\n]+?)\$([a-zA-Z0-9áàâãéèêíóòôõúçÁÀÂÃÉÈÊÍÓÒÔÕÚÇ])/g, (_, m, w) => `$${m}$ ${w}`);

  // 7. Remove espaços em branco no início de cada linha
  const lines = processed.split('\n');
  const processedLines = lines.map(line => line.replace(/^[ \t]+/, ''));
  processed = processedLines.join('\n');

  // 8. Remove excesso de quebras de linha mantendo no máximo parágrafo duplo
  processed = processed.replace(/\n{3,}/g, '\n\n');

  return processed;
}
