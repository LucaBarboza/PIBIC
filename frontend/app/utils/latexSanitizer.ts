/**
 * Sanitizador Universal de LaTeX para a Interface Frontend (Next.js)
 * Enforces 100% valid KaTeX / ReactMarkdown parsing across titles, boxes, and prose.
 */

function splitChainedDisplayMath(content: string): string {
  if (content.includes('\\begin{')) {
    return content;
  }

  const chunks: string[] = [];
  let currentChunk: string[] = [];
  let depth = 0;
  const n = content.length;
  let i = 0;

  while (i < n) {
    const char = content[i];
    if (char === '{' || char === '[') {
      depth++;
      currentChunk.push(char);
      i++;
    } else if (char === '}' || char === ']') {
      depth = Math.max(0, depth - 1);
      currentChunk.push(char);
      i++;
    } else if (char === '=' && depth === 0) {
      const prevStr = currentChunk.join('').trimEnd();
      if (
        prevStr.endsWith('\\le') ||
        prevStr.endsWith('\\ge') ||
        prevStr.endsWith('\\ne') ||
        prevStr.endsWith('\\leq') ||
        prevStr.endsWith('\\geq') ||
        prevStr.endsWith('\\approx') ||
        prevStr.endsWith('\\equiv') ||
        prevStr.endsWith('!') ||
        prevStr.endsWith('<') ||
        prevStr.endsWith('>') ||
        prevStr.endsWith(':') ||
        prevStr.endsWith('~')
      ) {
        currentChunk.push(char);
        i++;
      } else if (i + 1 < n && content[i + 1] === '=') {
        currentChunk.push('==');
        i += 2;
      } else {
        chunks.push(currentChunk.join('').trim());
        currentChunk = [];
        i++;
      }
    } else {
      currentChunk.push(char);
      i++;
    }
  }

  if (currentChunk.length > 0) {
    chunks.push(currentChunk.join('').trim());
  }

  if (chunks.length >= 3 && content.length > 35) {
    const first = chunks[0];
    const rest = chunks.slice(1);
    const alignedLines = [`${first} &= ${rest[0]}`];
    for (let idx = 1; idx < rest.length; idx++) {
      alignedLines.push(`&= ${rest[idx]}`);
    }
    return `\\begin{aligned}\n${alignedLines.join(' \\\\\n')}\n\\end{aligned}`;
  }

  return content;
}

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

  // 8. Converte equações encadeadas longas (A = B = C = D) em \begin{aligned} multilinhas
  c = splitChainedDisplayMath(c);

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

  // 1. Protege moedas na prosa normal
  processed = processed.replace(/\\text\{R[\\\$]*\}\s*/g, 'R\\$ ');
  processed = processed.replace(/\\text\{US[\\\$]*\}\s*/g, 'US\\$ ');
  processed = processed.replace(/\\text\{R\}\s*/g, 'R\\$ ');
  processed = processed.replace(/(?<!\\)R\$\s*(\d)/g, 'R\\$ $1');
  processed = processed.replace(/(?<!\\)US\$\s*(\d)/g, 'US\\$ $1');

  // 2. Normaliza delimitadores clássicos LaTeX
  processed = processed.replace(/\\\[/g, '\n$$\n').replace(/\\\]/g, '\n$$\n');
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
      const chained = splitChainedDisplayMath(sanitizedInner);
      if (chained.includes('\\begin{aligned}')) {
        resultParts.push(`\n$$\n${chained}\n$$\n`);
      } else {
        resultParts.push(`$${sanitizedInner}$`);
      }
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
