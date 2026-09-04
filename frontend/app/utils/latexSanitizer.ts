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
  } else if (!c.includes('\\begin{')) {
    const hasMultipleQuads = (c.match(/\\q?quad/g) || []).length >= 2;
    const hasCommaQuad = /,\s*\\q?quad/.test(c);
    const hasNumberedItems = /\d+\.\s*(?:\\quad|\s*)/.test(c);

    if (hasCommaQuad || (hasMultipleQuads && c.length > 40) || (hasNumberedItems && c.length > 30)) {
      let parts: string[] = [];
      if (hasCommaQuad) {
        parts = c.split(/,\s*(?:\\q?quad|\s)+/);
      } else if (hasNumberedItems) {
        parts = c.split(/(?=(?:\d+\.|\bAxioma\s+\d+:?)\s*(?:\\quad|\s*))/);
      } else {
        parts = c.split(/\s*(?:\\qquad|\\quad)+\s*/);
      }
      parts = parts.map(p => p.trim().replace(/[,;]+$/, '')).filter(Boolean);
      if (parts.length > 1) {
        c = `\\begin{aligned}\n${parts.join(' \\\\\n')}\n\\end{aligned}`;
      }
    }
  }

  return c.trim();
}

function sanitizeInlineMath(content: string): string {
  let c = content;
  c = c.replace(/\\bm\{/g, '\\boldsymbol{');
  c = c.replace(/\\bold\{/g, '\\mathbf{');
  c = c.replace(/\\+boldsymbol\\+\{([^}]+)\}/g, '\\boldsymbol{$1}');
  c = c.replace(/\\+boldsymbol\\+\{/g, '\\boldsymbol{');
  c = c.replace(/\\+nginxed/g, '\\in');
  c = c.replace(/(?<!\\)%/g, '\\%');
  
  // Converte \text{R...} dentro de inline
  c = c.replace(/\\text\{R[\\\$]*\}/g, '\\text{R\\$}');
  c = c.replace(/\\text\{US[\\\$]*\}/g, '\\text{US\\$}');
  
  // Remove cifrões aninhados
  c = c.replace(/(?<!\\)\$/g, '');
  
  // Resolve artefatos onde o LLM insere múltiplas barras antes de comandos gregos
  c = c.replace(/\\\\+/g, '\\');
  
  return c.trim();
}

export function sanitizeLatex(text: string): string {
  if (!text) return "";
  let processed = text.trim();

  // 0.1 Limpa erros de moedas do modelo antes de tokenizar
  processed = processed.replace(/\\text\{R[\\\$]*\}\s*/g, 'R__DOLLAR__ ');
  processed = processed.replace(/\\text\{US[\\\$]*\}\s*/g, 'US__DOLLAR__ ');
  processed = processed.replace(/\\text\{R\}\s*/g, 'R__DOLLAR__ ');

  // 0.2 Corrige ordinais corrompidos como 1$ vitória -> 1ª vitória
  processed = processed.replace(/(\d+)\$\s+([a-zA-Zá-ÿÁ-Ý]+)/g, '$1ª $2');

  // 0.3 Protege moedas padrão (R$ 1.000 ou US$ 500)
  processed = processed.replace(/(?<!\\)R\$\s*(\d)/g, 'R__DOLLAR__ $1');
  processed = processed.replace(/(?<!\\)US\$\s*(\d)/g, 'US__DOLLAR__ $1');
  processed = processed.replace(/R\$(?!\$)/g, 'R__DOLLAR__ ');
  processed = processed.replace(/US\$(?!\$)/g, 'US__DOLLAR__ ');

  // 0.4 Normaliza vírgula decimal na prosa: 1.200{,}00 -> 1.200,00
  processed = processed.replace(/(\d+)\{,\}(\d+)/g, '$1,$2');

  // 1. Normaliza delimitadores clássicos LaTeX
  processed = processed.replace(/\\\[/g, '\n$$\n').replace(/\\\]/g, '\n$$\n');
  processed = processed.replace(/\\\(/g, '$').replace(/\\\)/g, '$');

  // 1.0 Desembrulha \text{...} solto na prosa
  processed = processed.replace(/^\s*\\text\{([^}]+)\}\s*$/gm, '$1');

  // 1.1 Se um bloco $ ... $ contém prosa longa em português, desembrulha a prosa
  processed = processed.replace(/(?<!\$)\$(?!\$)([\s\S]*?)(?<!\$)\$(?!\$)/g, (match, inner) => {
    const words = inner.trim().split(/\s+/);
    const hasLongProse = words.length > 5 && /[a-zA-ZáàâãéèêíóòôõúçÁÀÂÃÉÈÊÍÓÒÔÕÚÇ]{4,}/.test(inner);
    if (hasLongProse && !inner.includes('\\frac') && !inner.includes('\\sum') && !inner.includes('\\int')) {
      return inner;
    }
    return match;
  });

  // 1.2 Corrige cifrões desbalanceados por parágrafo
  const paragraphs = processed.split('\n\n');
  const balancedParagraphs = paragraphs.map(p => {
    const tempP = p.replace(/\$\$/g, '');
    const matches = tempP.match(/(?<!\\)\$/g);
    const singleDollars = matches ? matches.length : 0;
    if (singleDollars % 2 !== 0) {
      return p.replace(/(\$[^$\n]+?)([\.\,\;\:\?\!]|(?=\n)|$)/, '$1$$2');
    }
    return p;
  });
  processed = balancedParagraphs.join('\n\n');

  // 2. Se a string contiver \begin{aligned} ou \begin{...} sem $$, envolve em $$
  if (!processed.includes('$$') && processed.includes('\\begin{')) {
    processed = processed.replace(/(\\begin\{[a-zA-Z*]+\}[\s\S]*?\\end\{[a-zA-Z*]+\})/g, '\n$$\n$1\n$$\n');
  }

  // 3. Divide a string em tokens de Display Math ($$...$$), Inline Math ($...$) e Prosa
  const pattern = /(?<!\\)(\$\$[\s\S]*?(?<!\\)\$\$|(?<!\\)\$(?:[^\$\n]|\\\$)+?(?<!\\)\$)/g;
  const parts = processed.split(pattern);

  const resultParts: string[] = [];
  for (const part of parts) {
    if (!part) continue;

    if (part.startsWith('$$') && part.endsWith('$$') && part.length >= 4) {
      const inner = part.slice(2, -2).trim();
      // Se o bloco de display for na verdade um parágrafo de texto puro em português (ex: \text{Dado um conjunto...})
      const cleanText = inner.replace(/^\s*\\text\{([^}]+)\}\s*$/, '$1');
      const words = cleanText.split(/\s+/);
      if (words.length > 6 && /[a-zA-ZáàâãéèêíóòôõúçÁÀÂÃÉÈÊÍÓÒÔÕÚÇ]{4,}/.test(cleanText) && !inner.includes('\\frac') && !inner.includes('\\sum') && !inner.includes('=')) {
        resultParts.push(`\n\n${cleanText}\n\n`);
        continue;
      }

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

  // 4. Anexa pontuações isoladas
  processed = processed.replace(/(\$\$[\s\S]*?\$\$)\s*\n+\s*([.,;:!?])/g, '$1$2\n\n');
  processed = processed.replace(/\n+\s*([.,;:!?])\s+(?=[A-Za-z0-9Á-ÿ])/g, '$1 ');
  processed = processed.replace(/\n+\s*([.,;:!?])\s*\n+/g, '$1\n\n');
  processed = processed.replace(/\.{2,}/g, '.');

  // 5. Ajusta o espaçamento ao redor de inline math colado em palavras em português
  processed = processed.replace(/([a-zA-Z0-9áàâãéèêíóòôõúçÁÀÂÃÉÈÊÍÓÒÔÕÚÇ])\$([^$\n]+?)\$/g, (_, w, m) => `${w} $${m}$`);
  processed = processed.replace(/\$([^$\n]+?)\$([a-zA-Z0-9áàâãéèêíóòôõúçÁÀÂÃÉÈÊÍÓÒÔÕÚÇ])/g, (_, m, w) => `$${m}$ ${w}`);

  // 6. Remove espaços em branco no início de cada linha
  const lines = processed.split('\n');
  const processedLines = lines.map(line => line.replace(/^[ \t]+/, ''));
  processed = processedLines.join('\n');

  // 7. Remove excesso de quebras de linha mantendo no máximo parágrafo duplo
  processed = processed.replace(/\n{3,}/g, '\n\n');

  // 8. Restaura os símbolos monetários devidamente escapados
  processed = processed.replace(/R__DOLLAR__/g, 'R\\$');
  processed = processed.replace(/US__DOLLAR__/g, 'US\\$');

  return processed;
}
