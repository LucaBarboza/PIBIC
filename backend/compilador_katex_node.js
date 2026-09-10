/**
 * Compilador e Validador KaTeX Real para o Backend do PIBIC.
 * Executa katex.renderToString com { throwOnError: true } em cada fórmula do JSON.
 * Retorna um relatório estruturado de compilação em JSON.
 */

const fs = require('fs');
const path = require('path');

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
  console.error(JSON.stringify({
    aprovado: false,
    total_formulas: 0,
    erros: [{ caminho: 'system', erro: 'Pacote KaTeX não encontrado no ambiente Node.js' }]
  }));
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
  console.error(JSON.stringify({
    aprovado: false,
    total_formulas: 0,
    erros: [{ caminho: 'input', erro: 'Falha ao parsear JSON de entrada: ' + err.message }]
  }));
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

function percorrerRecursivo(obj, objPath = 'root') {
  if (typeof obj === 'string') {
    inspecionarString(obj, objPath);
  } else if (Array.isArray(obj)) {
    obj.forEach((elem, idx) => percorrerRecursivo(elem, `${objPath}[${idx}]`));
  } else if (obj && typeof obj === 'object') {
    for (const k of Object.keys(obj)) {
      if (k === 'codigo_html_gerado' || k === 'telemetria_custo') continue;
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