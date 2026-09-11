"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { doc, onSnapshot, collection, getDocs, updateDoc, deleteDoc } from "firebase/firestore";
import { db, auth } from "@/lib/firebase";
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkBreaks from 'remark-breaks';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Menu, X, Play, RefreshCw } from 'lucide-react';
import AgentDebuggerModal from '@/components/AgentDebuggerModal';
import { sanitizeLatex } from '@/app/utils/latexSanitizer';

function SimuladorInterativo({ temaAula, nomeSimulador, htmlCode }: { temaAula: string, nomeSimulador: string, htmlCode?: string }) {
  const prepararHtmlSimulador = (rawHtml: string) => {
    if (!rawHtml) return rawHtml;

    // 1. Cura preventiva de sintaxe LaTeX em simuladores já persistidos (ex: \phi^|h| -> \phi^{|h|})
    let sanitizado = rawHtml
      .replace(/\^\|([^|]+)\|/g, '^{|$1|}')
      .replace(/_\|([^|]+)\|/g, '_{|$1|}');

    // 2. Cura preventiva contra erros de escape de backslash em simuladores legados no Firestore
    sanitizado = sanitizado
      .split("val.includes('\\')").join("val.indexOf(String.fromCharCode(92)) !== -1")
      .split("val.includes('\\\\')").join("val.indexOf(String.fromCharCode(92)) !== -1")
      .split("val.includes('\t')").join("val.indexOf('\\t') !== -1")
      .split("val.includes('\x0c')").join("val.indexOf('\\x0c') !== -1")
      .split("val.includes('\x08')").join("val.indexOf('\\x08') !== -1");

    // 3. Remove delimitadores \( e \[ que estavam virando '(' e '[' e quebrando todos os parênteses
    sanitizado = sanitizado
      .replace(/\{\s*left:\s*['"][^'"]*?\(['"],\s*right:\s*['"][^'"]*?\)['"][^}]*\},?/g, '')
      .replace(/\{\s*left:\s*['"][^'"]*?\[['"],\s*right:\s*['"][^'"]*?\]['"][^}]*\},?/g, '')
      .replace(/\.replace\(\/\(\?<!\[.*?\]\)rac.*?;/g, ';')
      .replace(/[\x0c\u000c]+/g, "")
      .replace(/\\f\s*frac/g, "\\frac");

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
            var h = Math.max(hRoot, hBody, hDoc);
            if (!h) h = 900;
            var finalH = Math.min(Math.max(h + 50, 650), 2600);
            if (Math.abs(finalH - (window.__lastSentSafeH || 0)) >= 3) {
              window.__lastSentSafeH = finalH;
              window.parent.postMessage({ type: 'simulador_resize', height: finalH }, '*');
            }
          }
          function reforcarRenderLatex() {
            try {
              if (typeof window.renderizarLatex === 'function') {
                window.renderizarLatex();
              } else if (window.renderMathInElement && document.getElementById('simulador-root')) {
                var bslash = String.fromCharCode(92);
                window.renderMathInElement(document.getElementById('simulador-root'), {
                  delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '$', right: '$', display: false}
                  ],
                  throwOnError: false
                });
              }
            } catch (e) {}
          }
          window.emitirAltura = recalcularAlturaSegura;
          window.addEventListener('load', function() {
            reforcarRenderLatex();
            recalcularAlturaSegura();
            setTimeout(function() { reforcarRenderLatex(); recalcularAlturaSegura(); }, 150);
            setTimeout(function() { reforcarRenderLatex(); recalcularAlturaSegura(); }, 500);
            setTimeout(function() { reforcarRenderLatex(); recalcularAlturaSegura(); }, 1000);
          });
          if (window.ResizeObserver) {
            var roSafe = new ResizeObserver(function() { recalcularAlturaSegura(); });
            var r = document.getElementById('simulador-root');
            if (r) roSafe.observe(r);
            if (document.body) roSafe.observe(document.body);
          }
        })();
      </script>
    `;

    if (sanitizado.includes('</head>')) {
      sanitizado = sanitizado.replace('</head>', `${antiScrollAndResizeScript}</head>`);
    } else {
      sanitizado = antiScrollAndResizeScript + sanitizado;
    }

    if (sanitizado.includes('</body>')) {
      sanitizado = sanitizado.replace('</body>', `${overrideResizeScript}</body>`);
    } else {
      sanitizado = sanitizado + overrideResizeScript;
    }

    return sanitizado;
  };

  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [html, setHtml] = useState<string | null>(htmlCode ? prepararHtmlSimulador(htmlCode) : null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [iframeHeight, setIframeHeight] = useState(1200);

  useEffect(() => {
    if (htmlCode) {
      setHtml(prepararHtmlSimulador(htmlCode));
    } else if (!html && !loading && !error) {
      // Dispara automaticamente a geração em tempo real se ainda não foi gerado
      carregarSimulador();
    }
  }, [htmlCode]);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Isola a mensagem exclusivamente para o iframe correspondente a este componente
      if (iframeRef.current && event.source !== iframeRef.current.contentWindow) {
        return;
      }
      if (event.data && (event.data.type === 'simulador_resize' || event.data.type === 'resize') && event.data.height) {
        const h = Math.min(Math.max(Number(event.data.height), 650), 2600);
        setIframeHeight(h);
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
      <div className="my-8 p-12 border border-indigo-100 rounded-xl bg-indigo-50/30 flex flex-col items-center justify-center space-y-4">
        <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin" />
        <p className="text-sm font-semibold text-indigo-900">Construindo Simulador Interativo com IA...</p>
        <p className="text-xs text-indigo-600/70">Programando lógica matemática e interface gráfica</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="my-8 p-6 border border-red-200 rounded-xl bg-red-50 text-center">
        <p className="text-sm text-red-600 font-semibold mb-2">Não foi possível carregar o simulador interativo.</p>
        <button 
          onClick={carregarSimulador}
          className="px-4 py-2 bg-red-600 text-white text-xs font-bold rounded-lg hover:bg-red-700 transition"
        >
          Tentar Novamente
        </button>
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
        style={{ height: `${iframeHeight}px`, width: '100%', border: 'none', display: 'block' }}
        className="w-full border-none bg-white transition-all duration-200"
        sandbox="allow-scripts allow-same-origin"
        scrolling="auto"
        title="Simulador Interativo"
      />
    </div>
  );
}

function BlockEditor({
  valorInicial,
  caminhoBloco,
  salaId,
  aulaId,
  onSaved
}: { valorInicial: string, caminhoBloco: string, salaId: string, aulaId: string, onSaved: () => void }) {
  const [editMode, setEditMode] = useState(false);
  const [conteudo, setConteudo] = useState(valorInicial);
  const [promptIA, setPromptIA] = useState("");
  const [saving, setSaving] = useState(false);

  const salvar = async () => {
    setSaving(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      await fetch(`${apiUrl}/api/editar_aula_bloco`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sala_id: salaId,
          aula_id: aulaId,
          caminho_bloco: caminhoBloco,
          novo_conteudo: conteudo,
          prompt_ia: promptIA
        })
      });
      setEditMode(false);
      onSaved();
    } catch (e) {
      alert("Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  };

  if (!editMode) {
    return (
      <button onClick={() => setEditMode(true)} className="text-xs bg-slate-200 text-slate-700 px-3 py-1 rounded hover:bg-slate-300 flex items-center gap-1 mb-4 font-bold shadow-sm">
        ✏️ Editar Bloco
      </button>
    );
  }

  return (
    <div className="bg-yellow-50 border border-yellow-200 p-4 rounded-xl mb-4 shadow-inner">
      <h4 className="font-bold text-yellow-800 text-sm mb-2">Modo de Edição (Markdown/LaTeX)</h4>
      <textarea
        className="w-full h-40 p-3 border border-yellow-300 rounded focus:outline-none focus:ring-2 focus:ring-yellow-500 font-mono text-sm bg-white text-slate-900"
        value={conteudo}
        onChange={(e) => setConteudo(e.target.value)}
      />
      <div className="mt-4">
        <label className="text-xs font-bold text-yellow-800 mb-1 block">Pedir para IA reescrever (opcional):</label>
        <input
          type="text"
          placeholder="Ex: Deixe este texto mais didático e inclua um exemplo prático."
          className="w-full p-2 border border-yellow-300 rounded text-sm bg-white"
          value={promptIA}
          onChange={(e) => setPromptIA(e.target.value)}
        />
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={() => setEditMode(false)} className="px-4 py-2 text-sm bg-white border border-slate-300 rounded hover:bg-slate-100">Cancelar</button>
        <button onClick={salvar} disabled={saving} className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 font-bold flex items-center gap-2">
          {saving ? "Salvando..." : "💾 Salvar Alterações"}
        </button>
      </div>
    
      
    </div>

  );
}

function formatFileSize(bytes: number): string {
  if (!bytes || isNaN(bytes)) return "";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

export default function ProfessorSemesterViewer() {
  const params = useParams();
  const router = useRouter();

  // Agora que o Backend garante a formatação rigorosa via o Agente Formatador LaTeX,
  const processLatex = (text: string) => sanitizeLatex(text);
  const id = params.id as string;

  const [classroom, setClassroom] = useState<any>(null);
  const [aulasGeradas, setAulasGeradas] = useState<any[]>([]);
  const [selectedAula, setSelectedAula] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [debuggerState, setDebuggerState] = useState<{salaId: string, aulaNum: number} | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<'teoria' | 'exercicios' | 'referencias'>('teoria');
  
  const [modalNovaAulaOpen, setModalNovaAulaOpen] = useState(false);
  const [novaAulaTitulo, setNovaAulaTitulo] = useState("");
  const [novaAulaFormato, setNovaAulaFormato] = useState<"ia_decide" | "so_temas" | "desenhar_aula">("ia_decide");
  const [novaAulaDescricao, setNovaAulaDescricao] = useState("");
  const [novaAulaModeloLlm, setNovaAulaModeloLlm] = useState<"2.5" | "3.5">("3.5");
  const [novaAulaPdf, setNovaAulaPdf] = useState("");
  const [novaAulaArquivoId, setNovaAulaArquivoId] = useState("");
  const [novaAulaNomeArquivo, setNovaAulaNomeArquivo] = useState("");
  const [novaAulaTamanhoArquivo, setNovaAulaTamanhoArquivo] = useState("");
  const [novaAulaSyncing, setNovaAulaSyncing] = useState(false);
  const [novaAulaUploadError, setNovaAulaUploadError] = useState(false);
  const [novaAulaGerarExercicios, setNovaAulaGerarExercicios] = useState(true);
  const [novaAulaSugestoesExercicios, setNovaAulaSugestoesExercicios] = useState("");
  const [novaAulaGerarSimulador, setNovaAulaGerarSimulador] = useState(true);
  const [novaAulaSugestoesSimulador, setNovaAulaSugestoesSimulador] = useState("");
  const [modalSucessoOpen, setModalSucessoOpen] = useState(false);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadNovaAulaPromiseRef = useRef<Promise<any> | null>(null);

  const handleFileUpload = (file: File) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) return alert("Somente arquivos PDF são aceitos.");

    // 0ms feedback instantâneo no frontend
    setNovaAulaNomeArquivo(file.name);
    setNovaAulaTamanhoArquivo(formatFileSize(file.size));
    setNovaAulaSyncing(true);
    setNovaAulaUploadError(false);
    setNovaAulaArquivoId("");
    setNovaAulaPdf("");

    const formData = new FormData();
    formData.append("files", file);

    const p = (async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${apiUrl}/api/upload_pdf`, { method: "POST", body: formData });
        const data = await res.json();
        if (res.ok) {
          setNovaAulaPdf(data.texto_extraido || (data.arquivo_id ? `[PDF_ID:${data.arquivo_id}]` : ""));
          setNovaAulaArquivoId(data.arquivo_id || "");
          setNovaAulaSyncing(false);
        } else {
          console.error("Erro no upload do PDF:", data.detail);
          setNovaAulaSyncing(false);
          setNovaAulaUploadError(true);
        }
      } catch (e) {
        console.error("Erro de rede no upload:", e);
        setNovaAulaSyncing(false);
        setNovaAulaUploadError(true);
      }
    })();

    uploadNovaAulaPromiseRef.current = p;
  };

  const handleRemoveArquivoNovaAula = () => {
    uploadNovaAulaPromiseRef.current = null;
    setNovaAulaNomeArquivo("");
    setNovaAulaTamanhoArquivo("");
    setNovaAulaPdf("");
    setNovaAulaArquivoId("");
    setNovaAulaSyncing(false);
    setNovaAulaUploadError(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleCriarAulaAvulsa = async () => {
    if (!novaAulaTitulo) return alert("Título é obrigatório");
    try {
      if (uploadNovaAulaPromiseRef.current) {
        await uploadNovaAulaPromiseRef.current;
      }
      const nextNum = (classroom?.total_aulas || classroom?.cronograma_oficial?.length || 0) + 1;
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      await fetch(`${apiUrl}/api/gerar_aula_avulsa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sala_id: id,
          id_disciplina: classroom?.id_disciplina,
          numero_aula: nextNum,
          aula_manual: {
            titulo: novaAulaTitulo,
            descricao: novaAulaDescricao + (novaAulaGerarExercicios && novaAulaSugestoesExercicios ? `\n(Dica p/ Exercícios: ${novaAulaSugestoesExercicios})` : "") + (novaAulaGerarSimulador && novaAulaSugestoesSimulador ? `\n(Dica p/ Simulador: ${novaAulaSugestoesSimulador})` : ""),
            texto_base_pdf: novaAulaPdf,
            arquivo_base_id: novaAulaArquivoId,
            nome_arquivo: novaAulaNomeArquivo,
            gerar_exercicios: novaAulaGerarExercicios,
            gerar_simulador: novaAulaGerarSimulador
          },
          modelo_llm: novaAulaModeloLlm
        })
      });
      setModalNovaAulaOpen(false);
      setNovaAulaTitulo("");
      setNovaAulaDescricao("");
      setNovaAulaPdf("");
      setNovaAulaArquivoId("");
      setNovaAulaNomeArquivo("");
      setNovaAulaTamanhoArquivo("");
      setNovaAulaSyncing(false);
      setNovaAulaUploadError(false);
      uploadNovaAulaPromiseRef.current = null;
      setModalSucessoOpen(true);
    } catch (e) {
      alert("Erro ao criar nova aula");
    }
  };

  const handleExcluirAula = async (aula: any) => {
    const confirmou = window.confirm(`Tem certeza que deseja excluir a aula "${aula.titulo}"? Esta ação não pode ser desfeita.`);
    if (!confirmou) return;
    try {
      await deleteDoc(doc(db, "classrooms", id, "aulas", aula.id));
      setSelectedAula(null);
    } catch (error) {
      alert("Erro ao excluir a aula.");
    }
  };

  const togglePublish = async (aula: any) => {
    try {
      const aulaRef = doc(db, "classrooms", id, "aulas", aula.id);
      await updateDoc(aulaRef, { publicada: !aula.publicada });
    } catch (error) {
      alert("Erro ao alterar visibilidade da aula.");
    }
  };

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
      const aulasList = snap.docs.map(d => ({ id: d.id, ...d.data() }));
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
        <div className="flex gap-2 shrink-0">
          <button onClick={() => router.push("/professor/dashboard")} className="text-xs sm:text-sm bg-blue-800 px-3 py-1.5 sm:px-4 sm:py-2 rounded hover:bg-blue-700 transition">
            Voltar
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden relative">
        {/* Backdrop escuro no Mobile quando a Sidebar está aberta */}
        {isSidebarOpen && (
          <div 
            onClick={() => setIsSidebarOpen(false)}
            className="fixed inset-0 bg-slate-900/40 z-30 md:hidden transition-opacity"
          />
        )}

        {/* Sidebar: Cronograma (Menu de Aulas - Gaveta no Mobile) */}
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
          {(isGenerating || status.startsWith("erro")) && (
              <div className={`mx-4 mt-3 text-xs p-3 rounded-lg border shadow-sm flex flex-col gap-2 ${status.startsWith("erro") ? "bg-red-50 border-red-200 text-red-600" : "bg-blue-50 border-blue-200 text-blue-600"}`}>
                <div className={`flex items-center gap-2 font-semibold ${!status.startsWith("erro") && "animate-pulse"}`}>
                  <span>🤖</span> {status.startsWith("erro") ? "Erro ao gerar aulas" : `IA gerando aulas (${classroom?.aulas_geradas || 0} de ${classroom?.total_aulas || '?'})`}
                </div>
                <button 
                  onClick={() => setDebuggerState({salaId: params.id as string, aulaNum: (classroom?.aulas_geradas || 0) + 1})}
                  className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-1.5 px-3 rounded shadow-sm transition"
                >
                  Acompanhar Agentes
                </button>
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
                    <div className="flex justify-between items-start mb-1 gap-1">
                      <span className={`font-bold ${aulaCompleta ? 'text-blue-700' : 'text-slate-500'}`}>Aula {numero}</span>
                      {aulaCompleta && (
                        <div className="flex items-center gap-1.5 flex-wrap justify-end">
                          {aulaCompleta.conteudo_json?.telemetria_custo && (
                            <span 
                              className="text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 px-1.5 py-0.5 rounded font-bold"
                              title={`Custo IA: ${aulaCompleta.conteudo_json.telemetria_custo.custo_formatado_usd || ''} (${aulaCompleta.conteudo_json.telemetria_custo.tokens_total?.toLocaleString('pt-BR') || 0} tokens)`}
                            >
                              💰 {aulaCompleta.conteudo_json.telemetria_custo.custo_formatado_brl || `R$ ${aulaCompleta.conteudo_json.telemetria_custo.custo_total_brl?.toFixed(2)}`}
                            </span>
                          )}
                          <span className="text-[10px] bg-green-100 text-green-700 px-1 rounded uppercase font-bold">Pronta</span>
                          {!aulaCompleta.publicada && <span className="text-[10px] bg-slate-200 text-slate-600 px-1 rounded uppercase font-bold" title="Oculta para alunos">🙈 Oculta</span>}
                        </div>
                      )}
                    </div>
                    <p className={`font-medium line-clamp-2 ${aulaCompleta ? 'text-slate-800' : 'text-slate-500'}`}>
                      {aulaMeta.titulo}
                    </p>
                  
      
    </div>
                );
              })
            ) : (
                <div className="text-center p-6 text-slate-500 text-sm">
                  {classroom?.status === "creating_semester" || classroom?.status === "fatiando_ementa" ? (
                    <div className="flex flex-col items-center gap-3">
                      <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                      <p className="font-semibold text-slate-700">Estruturando Cronograma...</p>
                      <p className="text-xs text-slate-400">A IA está fatiando a ementa oficial e montando o plano de ensino.</p>
                    </div>
                  ) : classroom?.status?.startsWith("erro") ? (
                    <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs">
                      <p className="font-bold mb-1">Erro no Processamento</p>
                      <p className="text-[11px]">{classroom.status}</p>
                    </div>
                  ) : (
                    <p className="text-slate-400">O cronograma ainda não foi estruturado pelo Coordenador.</p>
                  )}
                </div>
            )}
          </div>
          <div className="p-4 mt-auto border-t border-slate-200">
            <button 
              onClick={() => setModalNovaAulaOpen(true)}
              className="w-full bg-blue-100 text-blue-700 hover:bg-blue-200 border border-blue-300 font-bold py-2 px-4 rounded transition"
            >
              + Adicionar Nova Aula
            </button>
          </div>
        </aside>

        {/* Modal de Nova Aula */}
        {modalNovaAulaOpen && (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl overflow-y-auto max-h-[90vh]">
              <div className="bg-indigo-900 p-4 flex justify-between items-center text-white sticky top-0 z-10">
                <h3 className="font-bold text-lg">Criar Aula Extra</h3>
                <button onClick={() => setModalNovaAulaOpen(false)} className="hover:bg-indigo-800 p-1 rounded"><X size={20}/></button>
              </div>
                            <div className="p-6 space-y-6">
                
                {/* Título (Sempre visível) */}
                <div>
                  <label className="block text-sm font-bold text-slate-800 mb-1">Título / Tema da Aula <span className="text-red-500">*</span></label>
                  <input className="w-full border border-slate-300 rounded-lg p-3 focus:ring-2 focus:ring-indigo-500 text-slate-900" value={novaAulaTitulo} onChange={e => setNovaAulaTitulo(e.target.value)} placeholder="Ex: Exercícios Avançados de Dinâmica" />
                </div>

                {/* Motor IA */}
                <div>
                  <label className="block text-sm font-bold text-slate-800 mb-1">Motor de IA & Modo de Custo</label>
                  <div className="flex items-start p-3 rounded-xl border-2 border-indigo-600 bg-indigo-50/70 shadow-sm">
                    <span className="text-xl mr-2">🚀</span>
                    <div>
                      <div className="flex items-center gap-1 mb-0.5">
                        <span className="font-bold text-slate-800 text-xs">Gemini 3.5 Flash-Lite</span>
                        <span className="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full font-bold">Padrão</span>
                      </div>
                      <div className="text-[10px] text-slate-500 leading-tight mb-1">Geração rápida e econômica com <strong>3.5 Flash-Lite</strong>.</div>
                      <div className="text-[11px] font-bold text-emerald-700">~R$ 0,15 / aula</div>
                    </div>
                  </div>
                </div>

                {/* PDF */}
                <div>
                  <label className="block text-sm font-bold text-slate-800 mb-1">Upload de Material Base (PDF Opcional)</label>
                  <input type="file" ref={fileInputRef} className="hidden" onChange={e => e.target.files && handleFileUpload(e.target.files[0])} accept=".pdf" />
                  {!novaAulaNomeArquivo ? (
                    <button 
                      type="button"
                      onClick={() => fileInputRef.current?.click()} 
                      className="bg-slate-50 border border-slate-300 hover:bg-slate-100 text-slate-700 font-bold px-4 py-3 rounded-lg text-sm w-full transition flex items-center justify-center gap-2 shadow-sm"
                    >
                      <span>📎</span> Anexar PDF Específico
                    </button>
                  ) : (
                    <div className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm shadow-sm">
                      <div className="flex items-center gap-2.5 overflow-hidden mr-2">
                        <span className="text-lg">📄</span>
                        <div className="truncate text-left">
                          <span className="font-bold text-blue-900 truncate block text-xs sm:text-sm">{novaAulaNomeArquivo}</span>
                          <div className="flex items-center gap-1.5 text-[11px] text-blue-600">
                            {novaAulaTamanhoArquivo && <span>{novaAulaTamanhoArquivo}</span>}
                            <span>•</span>
                            {novaAulaSyncing ? (
                              <span className="inline-flex items-center gap-1 text-amber-600 font-medium">
                                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-ping"></span>
                                Sincronizando em background...
                              </span>
                            ) : novaAulaUploadError ? (
                              <span className="text-red-500 font-semibold">Falha no envio</span>
                            ) : (
                              <span className="text-emerald-700 font-semibold">✓ Anexado (IA analisará em background)</span>
                            )}
                          </div>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={handleRemoveArquivoNovaAula}
                        className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-md transition font-bold"
                        title="Remover arquivo"
                      >
                        ✕
                      </button>
                    </div>
                  )}
                </div>

                {/* Artesão Completo */}
                <div className="space-y-4 border-t border-slate-200 pt-4">
                  <div>
                    <label className="block text-sm font-bold text-slate-800 mb-1">Diretrizes / Notas Opcionais</label>
                    <textarea className="w-full border border-slate-300 rounded-lg p-3 h-20 focus:ring-2 focus:ring-indigo-500 text-slate-900" value={novaAulaDescricao} onChange={e => setNovaAulaDescricao(e.target.value)} placeholder="O que a IA deve cobrir especificamente nesta aula?" />
                  </div>
                  
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-4">
                    <div>
                      <label className="flex items-center gap-2 font-bold text-slate-800 cursor-pointer">
                          <input type="checkbox" checked={novaAulaGerarExercicios} onChange={(e) => setNovaAulaGerarExercicios(e.target.checked)} className="w-5 h-5 text-indigo-600 rounded" />
                          Gerar Exercícios ao Final
                      </label>
                      {novaAulaGerarExercicios && (
                          <input type="text" placeholder="Sugestões? (Ex: 3 abertas). Deixe em branco p/ IA decidir." className="w-full mt-2 p-3 border border-slate-300 rounded-lg text-sm text-slate-900" value={novaAulaSugestoesExercicios} onChange={(e) => setNovaAulaSugestoesExercicios(e.target.value)} />
                      )}
                    </div>
                    <hr className="border-slate-200" />
                    <div>
                      <label className="flex items-center gap-2 font-bold text-slate-800 cursor-pointer">
                          <input type="checkbox" checked={novaAulaGerarSimulador} onChange={(e) => setNovaAulaGerarSimulador(e.target.checked)} className="w-5 h-5 text-indigo-600 rounded" />
                          Injetar Simulador Interativo
                      </label>
                      {novaAulaGerarSimulador && (
                          <input type="text" placeholder="Ex: Mostrar um bloco deslizando. Deixe em branco p/ IA decidir." className="w-full mt-2 p-3 border border-slate-300 rounded-lg text-sm text-slate-900" value={novaAulaSugestoesSimulador} onChange={(e) => setNovaAulaSugestoesSimulador(e.target.value)} />
                      )}
                    </div>
                  </div>
                </div>

                <button onClick={handleCriarAulaAvulsa} className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-4 rounded-xl shadow-lg transition text-lg mt-4">
                  Gerar Nova Aula 🚀
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Main Content: Visualizador da Aula Selecionada */}
        <main className="flex-1 bg-slate-50 overflow-y-auto p-4 sm:p-6 md:p-8">
          {!selectedAula ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 py-16">
              <div className="text-5xl sm:text-6xl mb-4">📖</div>
              <p className="text-base sm:text-lg text-center px-4">Selecione uma aula no cronograma lateral para estudar.</p>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto pb-20">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6 pb-2 border-b-2 border-slate-200">
                <h2 className="text-2xl sm:text-3xl font-bold text-blue-900 flex flex-wrap items-center gap-2">
                  <span>Aula {selectedAula.numero_aula}:</span>
                  <ReactMarkdown remarkPlugins={[remarkMath, remarkBreaks]} rehypePlugins={[[rehypeKatex, {strict: false}]]} components={{p: "span"}}>
                    {processLatex(selectedAula.titulo)}
                  </ReactMarkdown>
                </h2>
                <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
                  <button
                    onClick={() => handleExcluirAula(selectedAula)}
                    className="px-3 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm rounded-full font-bold shadow-sm transition-colors flex items-center gap-1.5 bg-red-50 text-red-600 hover:bg-red-100 border border-red-200"
                  >
                    🗑️ Excluir
                  </button>
                  <button
                    onClick={() => togglePublish(selectedAula)}
                  className={`px-3 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm rounded-full font-bold shadow-sm transition-colors flex items-center gap-1.5 ${
                    selectedAula.publicada 
                      ? 'bg-green-100 text-green-700 hover:bg-green-200 border border-green-300' 
                      : 'bg-slate-200 text-slate-600 hover:bg-slate-300 border border-slate-300'
                  }`}
                >
                  {selectedAula.publicada ? "👁️ Visível" : "🙈 Oculta"}
                </button>
                </div>
              </div>

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
                  <div className="mt-4">
                    <BlockEditor 
                      valorInicial={selectedAula.conteudo_json.resumo_executivo_aula}
                      caminhoBloco="conteudo_json.resumo_executivo_aula"
                      salaId={classroom.id}
                      aulaId={selectedAula.id}
                      onSaved={() => {}}
                    />
                  </div>
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
                      
                      <BlockEditor 
                        valorInicial={textoProsa}
                        caminhoBloco={isLapidada ? `conteudo_json.paginas_conteudo.${idx}.discussao_teorica_prosa` : `conteudo_json.conteudo_paginas.${idx}.conteudo.conceito_intuitivo`}
                        salaId={classroom.id}
                        aulaId={selectedAula.id}
                        onSaved={() => {}}
                      />

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
                                    key={`sim-prof-${idx}-${sIdx}`}
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
                <section className="bg-white p-4 sm:p-6 md:p-8 rounded-xl sm:rounded-2xl shadow-sm border border-slate-200 mt-8 sm:mt-12">
                  <h3 className="text-xl sm:text-2xl font-bold text-slate-800 mb-6 sm:mb-8 pb-3 sm:pb-4 border-b-2 border-slate-100 flex items-center gap-2 sm:gap-3">
                    <span>📝</span> Caderno de Exercícios
                  </h3>

                  <div className="space-y-8 sm:space-y-12">
                    {/* Múltipla Escolha */}
                    {selectedAula.conteudo_json.exercicios_da_aula.questoes_multipla_escolha?.length > 0 && (
                      <div>
                        <h4 className="text-lg sm:text-xl font-bold text-indigo-900 mb-4 sm:mb-6 flex items-center gap-2">
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
        {/* Modal de Sucesso */}
        {modalSucessoOpen && (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 text-center animate-fade-in">
              <div className="text-6xl mb-4">⏳</div>
              <h3 className="font-bold text-2xl text-blue-900 mb-2">Sua aula está sendo preparada!</h3>
              <p className="text-slate-600 mb-6">
                A IA está estruturando todo o conteúdo. Isso pode levar alguns minutos. Você não precisa atualizar a página, o cronograma lateral será atualizado automaticamente quando ela ficar pronta.
              </p>
              <button 
                onClick={() => setModalSucessoOpen(false)}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-lg shadow transition"
              >
                Entendi
              </button>
            </div>
          </div>
        )}
    
      
      {debuggerState && (

    
      
        <AgentDebuggerModal 

    
      
          salaId={debuggerState.salaId} 

    
      
          numeroAula={debuggerState.aulaNum} 

    
      
          onClose={() => setDebuggerState(null)} 

    
      
        />

    
      
      )}

    
      
    </div>
  );
}