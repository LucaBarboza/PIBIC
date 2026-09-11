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

  // 1. Auditoria Estrita de Sintaxe JavaScript dentro de tags <script>
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
  }

  // 2. Auditoria de Fórmulas KaTeX no corpo HTML (fora de <script> e <style>)
  const htmlSemScripts = html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, ' ');
  inspecionarString(htmlSemScripts, `${objPath}.html_conteudo`);
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