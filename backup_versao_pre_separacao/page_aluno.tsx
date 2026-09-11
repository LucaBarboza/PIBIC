"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { doc, onSnapshot, collection, getDocs } from "firebase/firestore";
import { db, auth } from "@/lib/firebase";
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkBreaks from 'remark-breaks';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import * as katexModule from 'katex';
// @ts-ignore
import * as autoRenderModule from 'katex/dist/contrib/auto-render';
import { Menu, X, Play, RefreshCw } from 'lucide-react';
import { sanitizeLatex } from '@/app/utils/latexSanitizer';

const katexObj = (katexModule as any).default || katexModule;
const autoRenderFunc = (autoRenderModule as any).default || autoRenderModule;

if (typeof window !== 'undefined') {
  (window as any).katex = katexObj;
  (window as any).renderMathInElement = autoRenderFunc;
}

function SimuladorInterativo({ temaAula, nomeSimulador, htmlCode }: { temaAula: string, nomeSimulador: string, htmlCode?: string }) {
  const prepararHtmlSimulador = (rawHtml: string) => {
    if (!rawHtml) return rawHtml;

    // 1. Cura preventiva de sintaxe LaTeX em simuladores já persistidos (ex: \phi^|h| -> \phi^{|h|})
    // 1. Cura preventiva contra erros de escape de backslash ou corrupções em simuladores legados no Firestore
    let sanitizado = rawHtml
      .split("val.includes('^{|') |}|").join("val.indexOf('^|') !== -1")
      .split("val.includes('\\')").join("val.indexOf(String.fromCharCode(92)) !== -1")
      .split("val.includes('\\\\')").join("val.indexOf(String.fromCharCode(92)) !== -1")
      .split("val.includes('\t')").join("val.indexOf('\\t') !== -1")
      .split("val.includes('\x0c')").join("val.indexOf('\\x0c') !== -1")
      .split("val.includes('\x08')").join("val.indexOf('\\x08') !== -1");

    // 2. Normalização de Layout Plotly Anti-Sobreposição (Padrão Visual UFBA)
    sanitizado = sanitizado
      .replace(/legend:\s*\{\s*orientation:\s*['"]h['"],\s*y:\s*1\.\d+[^}]*\}/g, 'legend: { orientation: "h", y: -0.22, x: 0.5, xanchor: "center" }')
      .replace(/y:\s*1\.(?:15|1|2|25)/g, 'y: -0.22, x: 0.5, xanchor: "center"')
      .replace(/b:\s*(?:30|40)(?=[\s,}])/g, 'b: 65');

    const traduzirLatexParaUnicode = (texto: string): string => {
      if (!texto) return texto;
      let t = texto;
      const subs: [RegExp, string][] = [
        [/\\mu/g, 'μ'], [/\\sigma/g, 'σ'], [/\\alpha/g, 'α'], [/\\beta/g, 'β'],
        [/\\gamma/g, 'γ'], [/\\delta/g, 'δ'], [/\\epsilon/g, 'ε'], [/\\varepsilon/g, 'ε'],
        [/\\theta/g, 'θ'], [/\\lambda/g, 'λ'], [/\\pi/g, 'π'], [/\\rho/g, 'ρ'],
        [/\\tau/g, 'τ'], [/\\phi/g, 'φ'], [/\\varphi/g, 'φ'], [/\\chi/g, 'χ'],
        [/\\psi/g, 'ψ'], [/\\omega/g, 'ω'], [/\\Delta/g, 'Δ'], [/\\Theta/g, 'Θ'],
        [/\\Lambda/g, 'Λ'], [/\\Sigma/g, 'Σ'], [/\\Phi/g, 'Φ'], [/\\Psi/g, 'Ψ'],
        [/\\Omega/g, 'Ω'], [/\\pm/g, '±'], [/\\mp/g, '∓'], [/\\times/g, '×'],
        [/\\cdot/g, '·'], [/\\div/g, '÷'], [/\\approx/g, '≈'], [/\\neq/g, '≠'],
        [/\\ne/g, '≠'], [/\\leq/g, '≤'], [/\\le/g, '≤'], [/\\geq/g, '≥'],
        [/\\ge/g, '≥'], [/\\infty/g, '∞'], [/\\partial/g, '∂'], [/\\nabla/g, '∇'],
        [/\\in/g, '∈'], [/\\forall/g, '∀'], [/\\exists/g, '∃'],
        [/\\sqrt\{([^}]+)\}/g, '√($1)'], [/\\frac\{([^}]+)\}\{([^}]+)\}/g, '($1)/($2)'],
        [/\^2/g, '²'], [/\^3/g, '³'],
        [/_0/g, '₀'], [/_1/g, '₁'], [/_2/g, '₂'], [/_3/g, '₃'], [/_i/g, 'ᵢ'], [/_n/g, 'ₙ'], [/_x/g, 'ₓ'],
        [/\\log_\{10\}/g, 'log₁₀'], [/\\log_10/g, 'log₁₀'], [/\\log/g, 'log'],
        [/\\ln/g, 'ln'], [/\\exp/g, 'exp']
      ];
      for (const [padrao, sub] of subs) {
        t = t.replace(padrao, sub);
      }
      t = t.replace(/([A-Za-z]+)_\{([^}]+)\}/g, '$1($2)');
      t = t.replace(/([A-Za-z]+)_([a-zA-Z0-9])/g, '$1($2)');
      t = t.replace(/\$([^\$]+)\$/g, '$1');
      t = t.replace(/\$/g, '');
      t = t.replace(/\\([a-zA-Z]+)/g, '$1');
      return t;
    };

    // 3. Higienização de rótulos do Plotly para não exibir $ crus em SVG
    sanitizado = sanitizado.replace(/((?:name|title|text))\s*:\s*([`'"])([\s\S]*?)\2/g, (match, prefix, quote, content) => {
      let interpolacoes: string[] = [];
      const conteudoProtegido = content.replace(/\$\{[^}]+\}/g, (im: string) => {
        interpolacoes.push(im);
        return `__INTERP_${interpolacoes.length - 1}__`;
      });
      let limpo = traduzirLatexParaUnicode(conteudoProtegido);
      interpolacoes.forEach((interp, i) => {
        limpo = limpo.replace(`__INTERP_${i}__`, interp);
      });
      return `${prefix}: ${quote}${limpo}${quote}`;
    });

    // 4. Limpeza de rótulos em tags <option> (menus suspensos nativos não suportam KaTeX)
    sanitizado = sanitizado.replace(/<option\b([^>]*)>([\s\S]*?)<\/option>/gi, (match, attrs, content) => {
      const limpo = traduzirLatexParaUnicode(content);
      return `<option${attrs}>${limpo}</option>`;
    });

    // 5. Limpeza de rótulos de sliders ($n$): -> (n):
    sanitizado = sanitizado.replace(/\(\$([a-zA-Z0-9_]+)\$\):/g, '($1):');

    // 5.5. Pré-renderização síncrona do Card 'Modelo Matemático do Laboratório' com KaTeX puro
    sanitizado = sanitizado.replace(
      /(<div[^>]*class="[^"]*font-semibold text-slate-800[^"]*"[^>]*>)([\s\S]*?)(<\/div>)/gi,
      (match, openTag, content, closeTag) => {
        const renderizado = content.replace(/\$([^\$]+)\$/g, (_: string, formula: string) => {
          try {
            if (katexObj && typeof katexObj.renderToString === 'function') {
              return katexObj.renderToString(formula.trim(), { displayMode: false, throwOnError: false });
            }
            return `$${formula}$`;
          } catch (e) {
            return `$${formula}$`;
          }
        });
        return `${openTag}${renderizado}${closeTag}`;
      }
    );

    // 6. Aponta KaTeX para o servidor local Next.js (/vendor/katex) com carregamento instantâneo
    if (!sanitizado.includes('/vendor/katex/katex.min.js')) {
      sanitizado = sanitizado
        .replace('https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css', '/vendor/katex/katex.min.css')
        .replace('https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js', '/vendor/katex/katex.min.js')
        .replace('https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js', '/vendor/katex/contrib/auto-render.min.js');
    }

    const antiScrollAndResizeScript = `
      <style>
        html, body {
          height: auto !important;
          min-height: 0 !important;
          max-height: none !important;
          overflow-x: hidden !important;
          margin: 0 !important;
          padding: 8px 12px 24px 12px !important;
        }
        #simulador-root {
          padding-bottom: 8px !important;
          margin-bottom: 0 !important;
        }
        /* Erradica barras de rolagem em KaTeX, Fórmulas e Textos no Simulador */
        .katex, .katex-display, .katex-html, .katex *, 
        #explicacao_dinamica, #explicacao_dinamica *,
        #simulador-root * {
          overflow-x: visible !important;
          overflow-y: visible !important;
          scrollbar-width: none !important;
          -ms-overflow-style: none !important;
        }
        .katex::-webkit-scrollbar, .katex *::-webkit-scrollbar,
        .katex-display::-webkit-scrollbar, .katex-html::-webkit-scrollbar,
        #explicacao_dinamica::-webkit-scrollbar, #explicacao_dinamica *::-webkit-scrollbar {
          display: none !important;
          width: 0 !important;
          height: 0 !important;
        }
        .katex-display {
          margin: 0.35em 0 !important;
          max-width: 100% !important;
          white-space: normal !important;
        }
        .katex-display > .katex {
          white-space: normal !important;
          text-align: center;
        }
        #explicacao_dinamica {
          word-break: break-word;
          overflow: visible !important;
        }
      </style>
    `;

    const overrideResizeScript = `
      <script>
        (function() {
          function recalcularAlturaSegura() {
            var root = document.getElementById('simulador-root');
            var hRoot = root ? Math.ceil(root.getBoundingClientRect().height || root.offsetHeight || 0) : 0;
            var hBody = document.body ? Math.ceil(document.body.scrollHeight || 0) : 0;
            var hDoc = document.documentElement ? Math.ceil(document.documentElement.scrollHeight || 0) : 0;
            var h = Math.max(hRoot, hBody, hDoc, 800);
            var finalH = Math.min(Math.max(h + 70, 750), 2800);
            if (Math.abs(finalH - (window.__lastSentSafeH || 0)) >= 3) {
              window.__lastSentSafeH = finalH;
              window.parent.postMessage({ type: 'simulador_resize', height: finalH }, '*');
            }
          }
          function reforcarRenderLatex() {
            try {
              var renderMath = (typeof window.renderMathInElement === 'function')
                ? window.renderMathInElement
                : (window.parent && typeof window.parent.renderMathInElement === 'function')
                  ? window.parent.renderMathInElement
                  : (window.parent && window.parent.renderMathInElement && typeof window.parent.renderMathInElement.default === 'function')
                    ? window.parent.renderMathInElement.default
                    : null;

              var target = document.getElementById('simulador-root') || document.body;
              if (renderMath && target) {
                var bslash = String.fromCharCode(92);
                var sngl = String.fromCharCode(36);
                var dbl = sngl + sngl;
                renderMath(target, {
                  delimiters: [
                    {left: dbl, right: dbl, display: true},
                    {left: sngl, right: sngl, display: false},
                    {left: bslash + '(', right: bslash + ')', display: false},
                    {left: bslash + '[', right: bslash + ']', display: true}
                  ],
                  ignoredClasses: ["katex", "katex-html", "katex-mathml", "katex-error"],
                  throwOnError: false
                });
              } else if (typeof window.renderizarLatex === 'function') {
                window.renderizarLatex();
              } else {
                if (!window.__safeLatexRetries) window.__safeLatexRetries = 0;
                if (window.__safeLatexRetries < 80) {
                  window.__safeLatexRetries++;
                  setTimeout(reforcarRenderLatex, 40);
                }
              }
            } catch (e) {}
          }
          reforcarRenderLatex();
          if (document.readyState === 'complete' || document.readyState === 'interactive') {
            reforcarRenderLatex();
            recalcularAlturaSegura();
          }
          window.emitirAltura = recalcularAlturaSegura;
          window.addEventListener('load', function() {
            reforcarRenderLatex();
            recalcularAlturaSegura();
            setTimeout(function() { reforcarRenderLatex(); recalcularAlturaSegura(); }, 150);
            setTimeout(function() { reforcarRenderLatex(); recalcularAlturaSegura(); }, 400);
            setTimeout(function() { reforcarRenderLatex(); recalcularAlturaSegura(); }, 800);
            setTimeout(function() { reforcarRenderLatex(); recalcularAlturaSegura(); }, 1500);
          });
          if (window.ResizeObserver) {
            var roSafe = new ResizeObserver(function() { recalcularAlturaSegura(); });
            if (document.body) roSafe.observe(document.body);
            var r = document.getElementById('simulador-root');
            if (r) roSafe.observe(r);
            var exp = document.getElementById('explicacao_dinamica');
            if (exp) roSafe.observe(exp);
          }
          var rootTarget = document.getElementById('simulador-root') || document.body;
          if (window.MutationObserver && rootTarget) {
            var timerMut = null;
            var moSafe = new MutationObserver(function(mutations) {
              var apenasKatex = mutations.every(function(m) {
                var t = m.target;
                return t && t.classList && (t.classList.contains('katex') || t.classList.contains('katex-html'));
              });
              if (apenasKatex) return;
              if (timerMut) clearTimeout(timerMut);
              timerMut = setTimeout(function() {
                reforcarRenderLatex();
                recalcularAlturaSegura();
              }, 25);
            });
            moSafe.observe(rootTarget, { childList: true, subtree: true, characterData: true });
          }
          document.addEventListener('input', function() {
            setTimeout(function() { reforcarRenderLatex(); recalcularAlturaSegura(); }, 30);
          }, true);
          document.addEventListener('change', function() {
            setTimeout(function() { reforcarRenderLatex(); recalcularAlturaSegura(); }, 30);
          }, true);
        })();
      </script>
    `;

    if (sanitizado.includes('</head>')) {
      sanitizado = sanitizado.replace('</head>', () => `${antiScrollAndResizeScript}</head>`);
    } else {
      sanitizado = antiScrollAndResizeScript + sanitizado;
    }

    if (sanitizado.includes('</body>')) {
      sanitizado = sanitizado.replace('</body>', () => `${overrideResizeScript}</body>`);
    } else {
      sanitizado = sanitizado + overrideResizeScript;
    }

    return sanitizado;
  };

  const [html, setHtml] = useState<string | null>(htmlCode ? prepararHtmlSimulador(htmlCode) : null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [iframeHeight, setIframeHeight] = useState(1150);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const executarKatexNoIframe = () => {
    try {
      const iframe = iframeRef.current;
      if (!iframe) return;
      const doc = iframe.contentDocument || iframe.contentWindow?.document;
      const win = iframe.contentWindow;
      if (!doc || !win) return;

      // Injeta instâncias pai do KaTeX diretamente na janela do iframe (0ms de latência)
      (win as any).katex = (window as any).katex || katexObj;
      (win as any).renderMathInElement = (window as any).renderMathInElement || autoRenderFunc;

      const fn = (window as any).renderMathInElement || autoRenderFunc;
      const target = doc.getElementById('simulador-root') || doc.body;
      if (typeof fn === 'function' && target) {
        fn(target, {
          delimiters: [
            { left: '$$', right: '$$', display: true },
            { left: '$', right: '$', display: false },
            { left: '\\(', right: '\\)', display: false },
            { left: '\\[', right: '\\]', display: true }
          ],
          ignoredClasses: ["katex", "katex-html", "katex-mathml", "katex-error"],
          throwOnError: false
        });
      }
      if (typeof (win as any).renderizarLatex === 'function') {
        (win as any).renderizarLatex();
      }
      if (typeof (win as any).emitirAltura === 'function') {
        (win as any).emitirAltura();
      }
    } catch (e) {}
  };

  useEffect(() => {
    if (htmlCode) {
      setHtml(prepararHtmlSimulador(htmlCode));
    } else if (!html && !loading && !error) {
      // Dispara automaticamente a geração em tempo real se ainda não foi gerado
      carregarSimulador();
    }
  }, [htmlCode]);

  useEffect(() => {
    const t1 = setTimeout(executarKatexNoIframe, 60);
    const t2 = setTimeout(executarKatexNoIframe, 200);
    const t3 = setTimeout(executarKatexNoIframe, 600);
    const t4 = setTimeout(executarKatexNoIframe, 1200);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
    };
  }, [html]);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data && (event.data.type === 'simulador_resize' || event.data.type === 'resize') && event.data.height) {
        const h = Math.min(Math.max(Number(event.data.height), 750), 2800);
        setIframeHeight(h);
        executarKatexNoIframe();
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  const carregarSimulador = async () => {
    setLoading(true);
    setError(false);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/gerar_simulador`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tema_aula: temaAula, nome_simulador: nomeSimulador })
      });
      if (!res.ok) throw new Error("Erro na API");
      const data = await res.json();
      setHtml(prepararHtmlSimulador(data.html_code));
    } catch (e) {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  if (!html && !loading && !error) {
    return null;
  }

  if (loading) {
    return (
      <div className="my-8 bg-slate-50 border border-slate-200 rounded-xl p-12 text-center shadow-inner">
        <RefreshCw className="animate-spin text-indigo-500 mx-auto mb-4" size={32} />
        <p className="text-slate-600 font-medium animate-pulse">Engenheiro de IA programando o simulador no padrão acadêmico...</p>
        <p className="text-slate-400 text-sm mt-2">Isso pode levar até 20 segundos (código sendo gerado e validado)</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="my-8 bg-red-50 text-red-600 p-6 rounded-xl border border-red-200 text-center">
        <p>Ocorreu um erro ao gerar a simulação.</p>
        <button onClick={carregarSimulador} className="mt-4 underline text-red-800">Tentar Novamente</button>
      </div>
    );
  }

  return (
    <div className="my-8 border border-slate-200 rounded-xl overflow-hidden shadow-lg bg-white">
      <div className="bg-slate-800 text-slate-100 px-4 py-3 flex justify-between items-center">
        <div className="font-bold text-sm flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-red-500"></span>
          <span className="w-3 h-3 rounded-full bg-yellow-500"></span>
          <span className="w-3 h-3 rounded-full bg-green-500"></span>
          <span className="ml-2 text-slate-300">Lab Virtual: {nomeSimulador}</span>
        </div>
      </div>
      <iframe 
        ref={iframeRef}
        srcDoc={html!}
        onLoad={executarKatexNoIframe}
        style={{ height: `${iframeHeight}px`, width: '100%', border: 'none', display: 'block' }}
        className="w-full border-none bg-white transition-all duration-200"
        sandbox="allow-scripts allow-same-origin"
        scrolling="auto"
        title="Simulador Interativo"
      />
    </div>
  );
}

export default function SemesterViewer() {
  const params = useParams();
  const router = useRouter();

  // Agora que o Backend garante a formatação rigorosa via o Agente Formatador LaTeX,
  const processLatex = (text: string) => sanitizeLatex(text);
  const id = params.id as string;

  const [classroom, setClassroom] = useState<any>(null);
  const [aulasGeradas, setAulasGeradas] = useState<any[]>([]);
  const [selectedAula, setSelectedAula] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<'teoria' | 'exercicios' | 'referencias'>('teoria');

  useEffect(() => {
    if (!id) return;

    // Listener em tempo real da Sala (para pegar o progresso e o cronograma mestre)
    const unsubSala = onSnapshot(doc(db, "classrooms", id), (docSnap) => {
      if (docSnap.exists()) {
        setClassroom(docSnap.data());
      } else {
        alert("Sala não encontrada!");
        router.push("/aluno/dashboard");
      }
      setLoading(false);
    });

    // Listener da subcoleção de Aulas Geradas
    const unsubAulas = onSnapshot(collection(db, "classrooms", id, "aulas"), (snap) => {
      const aulasList = snap.docs
        .map(d => ({ id: d.id, ...d.data() }))
        .filter((a: any) => a.publicada === true);
      setAulasGeradas(aulasList);
    });

    return () => {
      unsubSala();
      unsubAulas();
    };
  }, [id, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-slate-600">Carregando cronograma do semestre...</p>
        </div>
      </div>
    );
  }

  const status = classroom?.status || "";
  const isGenerating = status.startsWith("fatiando") || status.startsWith("gerando");

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <header className="bg-blue-900 text-white p-3 sm:p-4 shadow-md flex justify-between items-center z-20 shrink-0">
        <div className="flex items-center gap-2 sm:gap-4 overflow-hidden">
          <button 
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="p-2 hover:bg-blue-800 rounded-lg transition shrink-0"
            title={isSidebarOpen ? "Esconder cronograma" : "Mostrar cronograma"}
          >
            {isSidebarOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
          <div className="truncate">
            <h1 className="text-base sm:text-xl font-bold truncate">{classroom?.id_disciplina} - {classroom?.nome_disciplina}</h1>
            <p className="text-[10px] sm:text-xs text-blue-200 truncate">Sala: {classroom?.code} | Status: {status}</p>
          </div>
        </div>
        <button onClick={() => router.back()} className="text-xs sm:text-sm bg-blue-800 px-3 py-1.5 sm:px-4 sm:py-2 rounded hover:bg-blue-700 transition shrink-0">
          Voltar
        </button>
      </header>

      <div className="flex flex-1 overflow-hidden relative">
        {/* Backdrop escuro no Mobile quando a Sidebar está aberta */}
        {isSidebarOpen && (
          <div 
            onClick={() => setIsSidebarOpen(false)}
            className="fixed inset-0 bg-slate-900/40 z-30 md:hidden transition-opacity"
          />
        )}

        {/* Sidebar: Cronograma (Gaveta Flutuante no Mobile, Painel Lateral no Desktop) */}
        <aside className={`
          bg-white border-r border-slate-200 overflow-y-auto flex flex-col shrink-0 transition-all duration-300 z-40
          fixed inset-y-0 left-0 top-[57px] sm:top-[65px] md:static md:top-auto
          ${isSidebarOpen ? 'w-80 shadow-2xl md:shadow-none' : '-translate-x-full md:translate-x-0 md:w-0 md:hidden'}
        `}>
          <div className="p-4 border-b border-slate-100 bg-slate-50 flex justify-between items-center">
            <h2 className="font-bold text-slate-800">Plano de Ensino</h2>
            <button onClick={() => setIsSidebarOpen(false)} className="p-1 rounded-md text-slate-400 hover:text-slate-600 md:hidden">
              <X size={18} />
            </button>
          </div>
          {isGenerating && (
            <div className="mx-4 mt-3 text-xs text-blue-600 bg-blue-50 p-2 rounded border border-blue-100 animate-pulse flex items-center gap-2">
              <span>🤖</span> IA gerando aulas ({classroom?.aulas_geradas || 0} de {classroom?.total_aulas || '?'})
            </div>
          )}
          
          <div className="p-4 space-y-2">
            {classroom?.cronograma_oficial ? (
              classroom.cronograma_oficial.map((aulaMeta: any, idx: number) => {
                const numero = aulaMeta.numero_aula || (idx + 1);
                // Verifica se o conteúdo completo dessa aula já foi gerado
                const aulaCompleta = aulasGeradas.find(a => String(a.numero_aula) === String(numero) || a.id === String(numero));
                
                const isSelected = selectedAula?.id === aulaCompleta?.id && aulaCompleta != null;

                return (
                  <div 
                    key={idx}
                    onClick={() => {
                      if (aulaCompleta) {
                        setSelectedAula(aulaCompleta);
                        setActiveTab('teoria');
                        // Fecha a sidebar no mobile para focar na leitura
                        if (window.innerWidth < 768) {
                          setIsSidebarOpen(false);
                        }
                      }
                    }}
                    className={`p-3 rounded-lg border text-sm transition-all ${
                      aulaCompleta 
                        ? isSelected ? 'bg-blue-50 border-blue-300 shadow-sm cursor-pointer' : 'bg-white border-slate-200 hover:border-blue-200 cursor-pointer'
                        : 'bg-slate-50 border-dashed border-slate-200 opacity-60 cursor-not-allowed'
                    }`}
                  >
                    <div className="flex justify-between items-start mb-1">
                      <span className={`font-bold ${aulaCompleta ? 'text-blue-700' : 'text-slate-500'}`}>Aula {numero}</span>
                      {aulaCompleta && <span className="text-[10px] bg-green-100 text-green-700 px-1 rounded uppercase font-bold">Pronta</span>}
                    </div>
                    <p className={`font-medium line-clamp-2 ${aulaCompleta ? 'text-slate-800' : 'text-slate-500'}`}>
                      {aulaMeta.titulo}
                    </p>
                  </div>
                );
              })
            ) : (
               <div className="text-center p-6 text-slate-400 text-sm">
                 O cronograma ainda não foi estruturado pelo Coordenador.
               </div>
            )}
          </div>
        </aside>

        {/* Main Content: Visualizador da Aula Selecionada */}
        <main className="flex-1 bg-slate-50 overflow-y-auto p-4 sm:p-6 md:p-8">
          {!selectedAula ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 py-16">
              <div className="text-5xl sm:text-6xl mb-4">📖</div>
              <p className="text-base sm:text-lg text-center px-4">Selecione uma aula no cronograma lateral para estudar.</p>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto pb-20">
              <h2 className="text-2xl sm:text-3xl font-bold text-blue-900 mb-6 pb-2 border-b-2 border-slate-200">
                Aula {selectedAula.numero_aula}: {selectedAula.titulo}
              </h2>

              {/* TABS NAVIGATION (Scroll horizontal suave no Mobile) */}
              <div className="flex gap-2 mb-8 bg-slate-200/50 p-1.5 rounded-lg w-full sm:w-fit overflow-x-auto border border-slate-200">
                <button
                  onClick={() => setActiveTab('teoria')}
                  className={`px-4 sm:px-6 py-2 sm:py-2.5 rounded-md font-semibold text-xs sm:text-sm whitespace-nowrap transition-all ${
                    activeTab === 'teoria' 
                      ? 'bg-white text-blue-900 shadow-sm border border-slate-200/60' 
                      : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  <span className="mr-1.5 sm:mr-2">📖</span> Teoria e Simuladores
                </button>
                <button
                  onClick={() => setActiveTab('exercicios')}
                  className={`px-4 sm:px-6 py-2 sm:py-2.5 rounded-md font-semibold text-xs sm:text-sm whitespace-nowrap transition-all ${
                    activeTab === 'exercicios' 
                      ? 'bg-white text-blue-900 shadow-sm border border-slate-200/60' 
                      : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  <span className="mr-1.5 sm:mr-2">📝</span> Caderno de Exercícios
                </button>
                <button
                  onClick={() => setActiveTab('referencias')}
                  className={`px-4 sm:px-6 py-2 sm:py-2.5 rounded-md font-semibold text-xs sm:text-sm whitespace-nowrap transition-all ${
                    activeTab === 'referencias' 
                      ? 'bg-white text-blue-900 shadow-sm border border-slate-200/60' 
                      : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  <span className="mr-1.5 sm:mr-2">📚</span> Referências
                </button>
              </div>

              {/* CONTEÚDO TEÓRICO (Ativo se aba = teoria) */}
              <div className={activeTab === 'teoria' ? 'block' : 'hidden'}>
                {/* Resumo Executivo / TOC */}
              {selectedAula.conteudo_json?.resumo_executivo_aula && (
                <div className="bg-blue-50 border-l-4 border-blue-500 p-4 sm:p-6 rounded-r-xl mb-8 sm:mb-10 shadow-sm">
                  <h3 className="text-base sm:text-lg font-bold text-blue-900 mb-2 flex items-center gap-2">
                    <span>🎯</span> Resumo da Aula
                  </h3>
                  <p className="text-blue-800 text-sm sm:text-base leading-relaxed">
                    {selectedAula.conteudo_json.resumo_executivo_aula}
                  </p>
                </div>
              )}

              {(() => {
                const paginas = selectedAula.conteudo_json?.paginas_conteudo || selectedAula.conteudo_json?.conteudo_paginas || [];
                return paginas.map((pagina: any, idx: number) => {
                  const isLapidada = !!pagina.discussao_teorica_prosa;
                  const titulo = pagina.titulo_subtopico || pagina.titulo || `Subtópico ${idx + 1}`;
                  const textoProsa = isLapidada 
                    ? pagina.discussao_teorica_prosa 
                    : (pagina.conteudo?.conceito_intuitivo + "\n\n" + pagina.conteudo?.conceito_formal);
                  const latexCode = isLapidada 
                    ? pagina.formalismo_latex 
                    : "";
                  const deducoes = isLapidada
                    ? (pagina.deducao_analitica_linhas || [])
                    : (pagina.conteudo?.deducao_formal_passo_a_passo || []);
                  const exemplos = isLapidada 
                    ? pagina.exemplos_praticos_ricos 
                    : (pagina.conteudo?.exemplo_canonico ? [pagina.conteudo.exemplo_canonico] : []);

                  return (
                    <section key={idx} className="mb-8 sm:mb-12 bg-white p-4 sm:p-6 md:p-8 rounded-xl sm:rounded-2xl shadow-sm border border-slate-200">
                      <h3 className="text-xl sm:text-2xl font-bold text-slate-800 mb-4 sm:mb-6 pb-2 border-b border-slate-100 flex items-center gap-2">
                        <span>{idx + 1}.</span>
                        <span><ReactMarkdown remarkPlugins={[remarkMath, remarkBreaks]} rehypePlugins={[[rehypeKatex, {strict: false}]]} components={{p: "span"}}>{processLatex(titulo)}</ReactMarkdown></span>
                      </h3>
                      
                      <div className="prose prose-base sm:prose-lg prose-blue max-w-none text-slate-700">
                        <div className="leading-relaxed mb-6 space-y-4 text-sm sm:text-base">
                          <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[[rehypeKatex, {strict: false}]]}>
                            {processLatex(textoProsa)}
                          </ReactMarkdown>
                        </div>

                        {(() => {
                          const simuladores = selectedAula.conteudo_json?.simuladores_da_aula?.filter(
                            (s: any) => String(s.indice_pagina) === String(idx + 1)
                          );
                          if (simuladores && simuladores.length > 0) {
                            return (
                              <div className="space-y-6 my-6">
                                {simuladores.map((simuladorInfo: any, sIdx: number) => (
                                  <SimuladorInterativo 
                                    key={`sim-${idx}-${sIdx}`}
                                    temaAula={`${selectedAula.titulo} - ${titulo}`} 
                                    nomeSimulador={simuladorInfo.nome_simulador} 
                                    htmlCode={simuladorInfo.codigo_html_gerado}
                                  />
                                ))}
                              </div>
                            );
                          }
                          return null;
                        })()}

                        {latexCode && latexCode !== "null" && (
                          <div className="my-6 sm:my-8 p-4 sm:p-6 bg-slate-50 rounded-xl border border-slate-200 text-center">
                            <span className="text-blue-800 font-bold block mb-2 text-xs sm:text-sm uppercase tracking-wider">Fórmula / Definição Formal</span>
                            <div className="text-base sm:text-lg text-left inline-block w-full break-words max-w-full pb-1">
                              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[[rehypeKatex, {strict: false}]]}>
                                {processLatex(latexCode.trim().startsWith('$$') ? latexCode : `$$\n${latexCode.replace(/^\$+|\$+$/g, '').trim()}\n$$`)}
                              </ReactMarkdown>
                            </div>
                          </div>
                        )}

                        {deducoes?.length > 0 && deducoes[0] !== "null" && (
                          <div className="mb-6 sm:mb-8 bg-slate-50/60 p-4 sm:p-6 rounded-xl border border-slate-200">
                            <h5 className="font-bold text-slate-800 mb-3 text-sm sm:text-base flex items-center gap-2">
                              <span>🔍</span> Demonstração Passo a Passo
                            </h5>
                            <div className="bg-white p-3 sm:p-4 rounded-lg border border-slate-200 shadow-sm space-y-3">
                              {deducoes.map((passo: string, pIdx: number) => (
                                <div key={pIdx} className="text-slate-700 text-xs sm:text-sm leading-relaxed break-words whitespace-normal pb-1 border-b border-slate-100 last:border-b-0 last:pb-0">
                                  <ReactMarkdown remarkPlugins={[remarkMath, remarkBreaks]} rehypePlugins={[[rehypeKatex, {strict: false}]]}>
                                    {processLatex(passo)}
                                  </ReactMarkdown>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {exemplos?.length > 0 && (
                          <div className="mt-6 sm:mt-8">
                            <h4 className="text-base sm:text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
                              <span>💡</span> Exemplos Práticos
                            </h4>
                            {exemplos.map((exemplo: any, eIdx: number) => (
                              <div key={eIdx} className="bg-blue-50/40 p-4 sm:p-6 rounded-xl mb-6 border border-blue-100">
                                <div className="font-semibold text-slate-800 mb-4 border-b border-blue-200 pb-2 text-sm sm:text-base">
                                  <div className="flex-1">
                                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[[rehypeKatex, {strict: false}]]}>
                                      {processLatex(exemplo.contexto_e_enunciado || exemplo.enunciado)}
                                    </ReactMarkdown>
                                  </div>
                                </div>
                                
                                <div className="mt-4 sm:mt-6">
                                  {(exemplo.desenvolvimento_aritmético_passo_a_passo || exemplo.passo_a_passo_solucao) && (
                                    <div className="bg-white p-3 sm:p-4 rounded-lg mb-4 border border-slate-200 shadow-sm space-y-2">
                                      <h5 className="font-bold text-slate-700 mb-2 text-xs sm:text-sm uppercase">Passo a Passo</h5>
                                      {(exemplo.desenvolvimento_aritmético_passo_a_passo || exemplo.passo_a_passo_solucao).map((passo: string, pIdx: number) => (
                                        <div key={pIdx} className="text-slate-600 text-xs sm:text-sm">
                                          <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[[rehypeKatex, {strict: false}]]}>
                                            {processLatex(passo)}
                                          </ReactMarkdown>
                                        </div>
                                      ))}
                                    </div>
                                  )}

                                  <div className="bg-green-50 p-3 sm:p-4 rounded-lg mt-4 border border-green-200 text-xs sm:text-sm">
                                    <strong className="text-green-800 block mb-1">Conclusão:</strong>
                                    <div className="text-green-900">
                                      <ReactMarkdown remarkPlugins={[remarkMath, remarkBreaks]} rehypePlugins={[[rehypeKatex, {strict: false}]]}>
                                        {processLatex(exemplo.conclusao_e_laudo_comercial || exemplo.resultado_final)}
                                      </ReactMarkdown>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </section>
                  );
                });
              })()}
              </div> {/* Fim Aba Teoria */}

              {/* ABA EXERCÍCIOS */}
              <div className={activeTab === 'exercicios' ? 'block' : 'hidden'}>

              {selectedAula.conteudo_json?.exercicios_da_aula && (
                <section className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200 mt-12">
                  <h3 className="text-2xl font-bold text-slate-800 mb-8 pb-4 border-b-2 border-slate-100 flex items-center gap-3">
                    <span>📝</span> Caderno de Exercícios
                  </h3>

                  <div className="space-y-12">
                    {/* Múltipla Escolha */}
                    {selectedAula.conteudo_json.exercicios_da_aula.questoes_multipla_escolha?.length > 0 && (
                      <div>
                        <h4 className="text-xl font-bold text-indigo-900 mb-6 flex items-center gap-2">
                          <span className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 text-sm">A</span>
                          Múltipla Escolha
                        </h4>
                        <div className="space-y-8">
                          {selectedAula.conteudo_json.exercicios_da_aula.questoes_multipla_escolha.map((q: any, i: number) => (
                            <div key={`mc-${i}`} className="bg-slate-50 p-6 rounded-xl border border-slate-200">
                              <div className="font-semibold text-slate-800 mb-6 flex items-start gap-2">
                                <span className="text-indigo-600 font-bold">{i + 1}.</span>
                                <span className="flex-1">
                                  <ReactMarkdown remarkPlugins={[remarkMath, remarkBreaks]} rehypePlugins={[[rehypeKatex, {strict: false}]]}>
                                    {processLatex(q.enunciado)}
                                  </ReactMarkdown>
                                </span>
                              </div>
                              <div className="space-y-3 mb-6">
                                {Object.entries(q.alternativas).filter(([k, v]) => v).sort(([a], [b]) => a.localeCompare(b)).map(([letra, texto]: any) => (
                                  <label key={letra} className="flex gap-4 p-4 rounded-lg border border-slate-200 bg-white hover:border-indigo-300 cursor-pointer transition-colors items-start">
                                    <input type="radio" name={`q-${i}`} className="mt-1" />
                                    <div>
                                      <strong className="text-slate-700 mr-2">{letra})</strong>
                                      <span className="flex-1 text-slate-600">
                                        <ReactMarkdown remarkPlugins={[remarkMath, remarkBreaks]} rehypePlugins={[[rehypeKatex, {strict: false}]]}>
                                          {processLatex(texto)}
                                        </ReactMarkdown>
                                      </span>
                                    </div>
                                  </label>
                                ))}
                              </div>
                              <div className="mt-4">
                                <div className="text-indigo-600 font-bold inline-flex items-center gap-1">
                                  <span>Gabarito:</span>
                                </div>
                                <div className="mt-4 p-4 bg-indigo-50 border border-indigo-100 rounded-lg text-sm text-indigo-900">
                                  <strong className="block mb-2">Alternativa Correta: {q.alternativa_correta}</strong>
                                  <div className="mt-2 text-slate-800">
                                    <ReactMarkdown remarkPlugins={[remarkMath, remarkBreaks]} rehypePlugins={[[rehypeKatex, {strict: false}]]}>
                                      {processLatex(q.gabarito_comentado)}
                                    </ReactMarkdown>
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Discursivas */}
                    {selectedAula.conteudo_json.exercicios_da_aula.questoes_discursivas?.length > 0 && (
                      <div>
                        <h4 className="text-xl font-bold text-indigo-900 mb-6 mt-12 flex items-center gap-2">
                          <span className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 text-sm">✏️</span>
                          Questões Discursivas
                        </h4>
                        <div className="space-y-8">
                          {selectedAula.conteudo_json.exercicios_da_aula.questoes_discursivas.map((q: any, i: number) => (
                            <div key={`disc-${i}`} className="bg-slate-50 p-6 rounded-xl border border-slate-200">
                              <div className="font-semibold text-slate-800 mb-4 flex items-start gap-2">
                                <span className="text-indigo-600 font-bold">Q{i + 1}.</span>
                                <span className="flex-1">
                                  <ReactMarkdown remarkPlugins={[remarkMath, remarkBreaks]} rehypePlugins={[[rehypeKatex, {strict: false}]]}>
                                    {processLatex(q.enunciado)}
                                  </ReactMarkdown>
                                </span>
                              </div>
                              <div className="mt-4">
                                <div className="text-indigo-600 font-bold inline-flex items-center gap-1">
                                  <span>Solução Passo a Passo:</span>
                                </div>
                                <div className="mt-4 p-4 sm:p-6 bg-white border border-slate-200 rounded-lg space-y-4">
                                  {q.gabarito_passo_a_passo.map((passo: string, pIdx: number) => (
                                    <div key={pIdx} className="text-slate-600 text-sm sm:text-base">
                                      <ReactMarkdown remarkPlugins={[remarkMath, remarkBreaks]} rehypePlugins={[[rehypeKatex, {strict: false}]]}>
                                        {processLatex(passo)}
                                      </ReactMarkdown>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </section>
              )}
              </div> {/* Fim Aba Exercícios */}

              {/* ABA REFERÊNCIAS */}
              <div className={activeTab === 'referencias' ? 'block' : 'hidden'}>

              {selectedAula.conteudo_json?.referencias_bibliograficas_finais?.length > 0 && (
                <section className="bg-slate-800 text-slate-300 p-8 rounded-2xl mt-12">
                  <h3 className="text-xl font-bold text-white mb-6">📚 Referências da Aula</h3>
                  <ul className="space-y-3">
                    {selectedAula.conteudo_json.referencias_bibliograficas_finais.map((ref: string, rIdx: number) => (
                      <li key={rIdx} className="flex gap-3">
                        <span className="text-blue-400">•</span>
                        <span>{ref}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              </div> {/* Fim Aba Referências */}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
