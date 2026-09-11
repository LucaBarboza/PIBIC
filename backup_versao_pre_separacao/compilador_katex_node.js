/**
 * Compilador e Validador KaTeX Real para o Backend do PIBIC.
 * Executa katex.renderToString com { throwOnError: true } em cada fórmula do JSON.
 * Retorna um relatório estruturado de compilação em JSON.
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

let katex;
const katexPaths = [
  path.join(__dirname, '..', 'frontend', 'node_modules', 'katex'),
  path.join(__dirname, 'node_modules', 'katex'),
  'katex'
];

for (const p of katexPaths) {
  try {
    katex = require(p);
    break;
  } catch (e) {}
}

if (!katex) {
  const errPayload = JSON.stringify({
    aprovado: false,
    total_formulas: 0,
    total_erros: 1,
    erros: [{ caminho: 'system', erro: 'Pacote KaTeX não encontrado no ambiente Node.js' }]
  }, null, 2);
  console.log(errPayload);
  process.exit(1);
}

function obterInput() {
  const args = process.argv.slice(2);
  if (args.length > 0) {
    if (!fs.existsSync(args[0])) {
      throw new Error(`Arquivo não encontrado: ${args[0]}`);
    }
    return fs.readFileSync(args[0], 'utf-8');
  }
  return fs.readFileSync(0, 'utf-8');
}

let inputData;
try {
  const raw = obterInput();
  inputData = JSON.parse(raw);
} catch (err) {
  const parseErrPayload = JSON.stringify({
    aprovado: false,
    total_formulas: 0,
    total_erros: 1,
    erros: [{ caminho: 'input', erro: 'Falha ao parsear JSON de entrada: ' + err.message }]
  }, null, 2);
  console.log(parseErrPayload);
  process.exit(1);
}

let totalFormulas = 0;
const erros = [];

function auditarFormula(formula, tipo, objPath) {
  if (!formula || !formula.trim()) return;
  const f = formula.trim();
  totalFormulas++;

  try {
    katex.renderToString(f, {
      displayMode: tipo === 'display',
      throwOnError: true,
      strict: false
    });
  } catch (err) {
    erros.push({
      caminho: objPath,
      tipo: tipo,
      formula: f,
      erro: err.message
    });
  }
}

function inspecionarString(str, objPath) {
  if (typeof str !== 'string' || !str.trim()) return;

  const displayRegex = /\$\$([\s\S]*?)\$\$/g;
  let match;
  let foundMath = false;

  while ((match = displayRegex.exec(str)) !== null) {
    foundMath = true;
    auditarFormula(match[1], 'display', objPath);
  }

  const inlineRegex = /(?<!\$)\$([^\$\n]+?)\$(?!\$)/g;
  while ((match = inlineRegex.exec(str)) !== null) {
    foundMath = true;
    auditarFormula(match[1], 'inline', objPath);
  }

  if (!foundMath && (objPath.includes('formalismo_latex') || objPath.includes('deducao_analitica') || objPath.includes('desenvolvimento_aritm'))) {
    if (str.includes('\\') || str.includes('=') || str.includes('^') || str.includes('_')) {
      auditarFormula(str, 'display', objPath);
    }
  }
}

function inspecionarHtmlSimulador(html, objPath) {
  if (!html || typeof html !== 'string') return;

  const htmlSemScripts = html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, ' ');

  // 1. Detecção de caracteres de controle corrompidos que quebram LaTeX (\beta -> \x08eta, \frac -> \x0crac)
  if (/[\x08\x0c\u0008\u000c]/.test(htmlSemScripts) || /[\x08\x0c\u0008\u000c](?:eta|rac|ar\{|inom|mathbf)/.test(html)) {
    erros.push({
      caminho: `${objPath}.corrupcao_caracteres`,
      tipo: 'corrupted_control_char',
      formula: 'Caracteres de controle corrompidos (ex: \\x08 / backspace em \\beta)',
      erro: 'O código do simulador contém caracteres de escape corrompidos (como \\x08 ou \\x0c) que impedem compilação KaTeX.'
    });
  }

  // 2. Auditoria Estrita de Sintaxe JavaScript dentro de tags <script>
  const scriptRegex = /<script\b[^>]*>([\s\S]*?)<\/script>/gi;
  let sMatch;
  let sIdx = 0;
  while ((sMatch = scriptRegex.exec(html)) !== null) {
    sIdx++;
    const code = sMatch[1];
    if (!code || !code.trim()) continue;
    try {
      new vm.Script(code);
    } catch (jsErr) {
      erros.push({
        caminho: `${objPath}.script[${sIdx}]`,
        tipo: 'javascript_syntax',
        formula: code.trim().slice(0, 120),
        erro: `Erro de sintaxe no JavaScript do simulador: ${jsErr.message}`
      });
    }

    // Inspeciona fórmulas dentro de strings/templates no JavaScript (neutraliza interpolação ${...})
    const stringRegex = /`([\s\S]*?)`|'([^'\n]*)'|"([^"\n]*)"/g;
    let strMatch;
    while ((strMatch = stringRegex.exec(code)) !== null) {
      let lit = strMatch[1] || strMatch[2] || strMatch[3];
      if (lit && (lit.includes('$') || lit.includes('\\\\') || lit.includes('\\(') || lit.includes('\\['))) {
        // Substitui interpolações ${...} de template strings JS por um termo neutro para não corromper fórmulas KaTeX
        lit = lit.replace(/\$\{[^}]+\}/g, '1');
        inspecionarString(lit, `${objPath}.script_strings`);
      }
    }
  }

  // 3. Auditoria de tags <option> (menus nativos HTML não suportam nós DOM do KaTeX)
  const optionRegex = /<option\b[^>]*>([\s\S]*?)<\/option>/gi;
  let optMatch;
  while ((optMatch = optionRegex.exec(html)) !== null) {
    const optText = optMatch[1];
    if (optText.includes('$') || /\\[a-zA-Z]/.test(optText)) {
      erros.push({
        caminho: `${objPath}.option_math_incompativel`,
        tipo: 'unsupported_option_math',
        formula: optText.trim().slice(0, 80),
        erro: 'Tags <option> nativas rejeitam nós HTML do KaTeX. Use caracteres Unicode (ex: μ, σ, ±, ², f(x)) e remova os delimitadores $.'
      });
    }
  }

  // 4. Auditoria de rótulos Plotly com cifrões crus em nomes de trace ou eixos
  const plotlyDollarRegex = /(?:name|title)\s*:\s*(`[\s\S]*?`|'[^'\n]*'|"[^"\n]*")/gi;
  let pMatch;
  while ((pMatch = plotlyDollarRegex.exec(html)) !== null) {
    const rawStr = pMatch[1];
    const semInterpolacao = rawStr.replace(/\$\{[^}]+\}/g, '');
    if (semInterpolacao.includes('$')) {
      erros.push({
        caminho: `${objPath}.plotly_label_dollar`,
        tipo: 'unsupported_plotly_math',
        formula: pMatch[0].trim().slice(0, 80),
        erro: 'Rótulos SVG do Plotly não renderizam KaTeX com cifrões crus $. Use texto limpo ou Unicode.'
      });
    }
  }

  // 5. Auditoria de Fórmulas KaTeX no corpo HTML (fora de <script> e <style>)
  inspecionarString(htmlSemScripts, `${objPath}.html_conteudo`);

  // 4. Detecção de macros matemáticas LaTeX soltas (sem delimitadores $, $$, \( ou \[)
  // Remove primeiro as fórmulas matemáticas delimitadas para que operadores como < ou > não sejam confundidos com tags HTML
  const textoPuro = htmlSemScripts
    .replace(/\$\$[\s\S]*?\$\$/g, ' ')
    .replace(/(?<!\$)\$[^\$\n]+?\$(?!\$)/g, ' ')
    .replace(/\\\([\s\S]*?\\\)/g, ' ')
    .replace(/\\\[[\s\S]*?\\\]/g, ' ')
    .replace(/<[^>]+>/g, ' ');
  const macroSoltaRegex = /\\(frac|binom|sqrt|sum|prod|int|alpha|beta|gamma|delta|epsilon|theta|lambda|mu|sigma|pi|tau|phi|omega|chi|psi|hat|bar|mathbf)\b/g;
  let mMatch;
  while ((mMatch = macroSoltaRegex.exec(textoPuro)) !== null) {
    const trecho = textoPuro.slice(Math.max(0, mMatch.index - 15), Math.min(textoPuro.length, mMatch.index + 35)).trim();
    erros.push({
      caminho: `${objPath}.macro_solta`,
      tipo: 'uncompiled_math',
      formula: trecho,
      erro: `Fórmula ou símbolo matemático não delimitado por $ ou $$: "${mMatch[0]}"`
    });
  }
}

function percorrerRecursivo(obj, objPath = 'root') {
  if (typeof obj === 'string') {
    inspecionarString(obj, objPath);
  } else if (Array.isArray(obj)) {
    obj.forEach((elem, idx) => percorrerRecursivo(elem, `${objPath}[${idx}]`));
  } else if (obj && typeof obj === 'object') {
    for (const k of Object.keys(obj)) {
      if (k === 'telemetria_custo') continue;
      if (k === 'codigo_html_gerado') {
        inspecionarHtmlSimulador(obj[k], `${objPath}.${k}`);
        continue;
      }
      percorrerRecursivo(obj[k], `${objPath}.${k}`);
    }
  }
}

percorrerRecursivo(inputData);

const resultado = {
  aprovado: erros.length === 0,
  total_formulas: totalFormulas,
  total_erros: erros.length,
  erros: erros
};

console.log(JSON.stringify(resultado, null, 2));
process.exit(resultado.aprovado ? 0 : 2);