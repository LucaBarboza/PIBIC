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
  const [html, setHtml] = useState<string | null>(htmlCode || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [iframeHeight, setIframeHeight] = useState(900);

  useEffect(() => {
    if (htmlCode) {
      setHtml(htmlCode);
    } else if (!html && !loading && !error) {
      // Dispara automaticamente a geração em tempo real se ainda não foi gerado
      carregarSimulador();
    }
  }, [htmlCode]);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data && event.data.type === 'resize' && event.data.height) {
         setIframeHeight(Math.max(event.data.height + 80, 850));
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
      setHtml(data.html_code);
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
        <p className="text-slate-600 font-medium animate-pulse">Engenheiro de IA programando o simulador...</p>
        <p className="text-slate-400 text-sm mt-2">Isso pode levar até 20 segundos (código sendo escrito do zero)</p>
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
        srcDoc={html!}
        style={{ height: `${iframeHeight}px`, minHeight: "750px" }}
        className="w-full border-none bg-white"
        sandbox="allow-scripts allow-same-origin"
        scrolling="no"
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
  const [novaAulaGerarExercicios, setNovaAulaGerarExercicios] = useState(true);
  const [novaAulaSugestoesExercicios, setNovaAulaSugestoesExercicios] = useState("");
  const [novaAulaGerarSimulador, setNovaAulaGerarSimulador] = useState(true);
  const [novaAulaSugestoesSimulador, setNovaAulaSugestoesSimulador] = useState("");
  const [uploadingNovaAula, setUploadingNovaAula] = useState(false);
  const [modalSucessoOpen, setModalSucessoOpen] = useState(false);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (file: File) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) return alert("Somente PDF");
    setUploadingNovaAula(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/upload_pdf`, { method: "POST", body: formData });
      const data = await res.json();
      if (res.ok) {
        setNovaAulaPdf(data.texto_extraido);
      } else {
        alert("Erro no upload");
      }
    } catch (e) {
      alert("Erro na rede");
    } finally {
      setUploadingNovaAula(false);
    }
  };

  const handleCriarAulaAvulsa = async () => {
    if (!novaAulaTitulo) return alert("Título é obrigatório");
    try {
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
                    <div className="flex justify-between items-start mb-1">
                      <span className={`font-bold ${aulaCompleta ? 'text-blue-700' : 'text-slate-500'}`}>Aula {numero}</span>
                      {aulaCompleta && (
                        <div className="flex items-center gap-1">
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
                        <span className="font-bold text-slate-800 text-xs">Gemini 3.6 Flash + 3.5 Flash-Lite</span>
                        <span className="text-[10px] bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded-full font-bold">Padrão</span>
                      </div>
                      <div className="text-[10px] text-slate-500 leading-tight mb-1">Escrita com <strong>Gemini 3.6 Flash</strong> e suporte com <strong>3.5 Flash-Lite</strong>.</div>
                      <div className="text-[11px] font-bold text-indigo-700">~R$ 0,35 / aula</div>
                    </div>
                  </div>
                </div>

                {/* PDF */}
                <div>
                  <label className="block text-sm font-bold text-slate-800 mb-1">Upload de Material Base (PDF Opcional)</label>
                  <input type="file" ref={fileInputRef} className="hidden" onChange={e => e.target.files && handleFileUpload(e.target.files[0])} accept=".pdf" />
                  <button onClick={() => fileInputRef.current?.click()} className="bg-slate-50 border border-slate-300 hover:bg-slate-100 text-slate-700 font-bold px-4 py-3 rounded-lg text-sm w-full transition" disabled={uploadingNovaAula}>
                    {uploadingNovaAula ? "Extraindo texto do PDF..." : "📎 Anexar PDF Específico"}
                  </button>
                  {novaAulaPdf && <p className="text-green-700 text-xs mt-2 font-bold bg-green-50 p-2 rounded border border-green-200">✓ PDF carregado e lido com sucesso!</p>}
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
                            <div className="text-base sm:text-lg text-left inline-block w-full break-words overflow-x-auto max-w-full pb-2">
                              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[[rehypeKatex, {strict: false}]]}>
                                {processLatex(latexCode.startsWith('$$') || latexCode.startsWith('$') ? latexCode : `$$\n${latexCode}\n$$`)}
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
                                <div key={pIdx} className="text-slate-600 text-xs sm:text-sm leading-relaxed overflow-x-auto max-w-full pb-1">
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

              {/* CARD DE TELEMETRIA & CONTADOR DE GASTOS */}
              {selectedAula.conteudo_json?.telemetria_custo && (
                <section className="mt-12 bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 text-white p-6 sm:p-8 rounded-2xl shadow-xl border border-slate-700/80">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-6 border-b border-slate-700">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xl">📊</span>
                        <h3 className="text-lg sm:text-xl font-bold text-white tracking-tight">
                          Telemetria & Contador de Gastos da Aula
                        </h3>
                      </div>
                      <p className="text-xs sm:text-sm text-slate-400">
                        Consumo real de tokens auditado via API do Google Gemini AI
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs bg-indigo-500/20 text-indigo-300 px-3 py-1.5 rounded-full border border-indigo-500/30 font-semibold">
                        {selectedAula.conteudo_json.telemetria_custo.modo_label || "Modo IA"}
                      </span>
                      <div className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 px-4 py-1.5 rounded-xl text-center">
                        <div className="text-[10px] uppercase font-bold text-emerald-400">Custo Total</div>
                        <div className="text-lg font-black text-emerald-300">
                          {selectedAula.conteudo_json.telemetria_custo.custo_formatado_brl || `R$ ${selectedAula.conteudo_json.telemetria_custo.custo_total_brl?.toFixed(3)}`}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Grid de Métricas Chave */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 my-6">
                    <div className="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
                      <span className="text-slate-400 text-xs block mb-1">Total de Tokens</span>
                      <span className="text-xl sm:text-2xl font-black text-white">
                        {selectedAula.conteudo_json.telemetria_custo.tokens_total?.toLocaleString("pt-BR") || 0}
                      </span>
                      <span className="text-[10px] text-slate-400 block mt-0.5">tokens processados</span>
                    </div>
                    <div className="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
                      <span className="text-slate-400 text-xs block mb-1">Tokens de Entrada</span>
                      <span className="text-xl sm:text-2xl font-bold text-blue-400">
                        {selectedAula.conteudo_json.telemetria_custo.tokens_prompt?.toLocaleString("pt-BR") || 0}
                      </span>
                      <span className="text-[10px] text-slate-400 block mt-0.5">prompts & ementa</span>
                    </div>
                    <div className="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
                      <span className="text-slate-400 text-xs block mb-1">Tokens de Saída</span>
                      <span className="text-xl sm:text-2xl font-bold text-purple-400">
                        {selectedAula.conteudo_json.telemetria_custo.tokens_resposta?.toLocaleString("pt-BR") || 0}
                      </span>
                      <span className="text-[10px] text-slate-400 block mt-0.5">conteúdo & código JS</span>
                    </div>
                    <div className="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
                      <span className="text-slate-400 text-xs block mb-1">Custo em Dólar</span>
                      <span className="text-xl sm:text-2xl font-bold text-emerald-400">
                        {selectedAula.conteudo_json.telemetria_custo.custo_formatado_usd || `$${selectedAula.conteudo_json.telemetria_custo.custo_total_usd?.toFixed(4)}`}
                      </span>
                      <span className="text-[10px] text-slate-400 block mt-0.5">USD (câmbio ~R$ 5,50)</span>
                    </div>
                  </div>

                  {/* Tabela de Consumo por Agente */}
                  {selectedAula.conteudo_json.telemetria_custo.detalhe_agentes?.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-slate-700/80">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                        <span>🤖</span> Detalhamento do Consumo por Agente
                      </h4>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs">
                          <thead>
                            <tr className="border-b border-slate-700 text-slate-400">
                              <th className="pb-2 font-semibold">Agente</th>
                              <th className="pb-2 font-semibold">Modelo</th>
                              <th className="pb-2 font-semibold text-right">Prompt</th>
                              <th className="pb-2 font-semibold text-right">Resposta</th>
                              <th className="pb-2 font-semibold text-right">Tempo</th>
                              <th className="pb-2 font-semibold text-right">Custo Estimado</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800">
                            {selectedAula.conteudo_json.telemetria_custo.detalhe_agentes.map((item: any, idx: number) => (
                              <tr key={idx} className="hover:bg-slate-800/40 transition">
                                <td className="py-2.5 font-bold text-slate-200">{item.agente}</td>
                                <td className="py-2.5 text-indigo-300 font-mono text-[11px]">{item.nome_modelo || item.modelo}</td>
                                <td className="py-2.5 text-right text-slate-300">{item.tokens_prompt?.toLocaleString("pt-BR")}</td>
                                <td className="py-2.5 text-right text-slate-300">{item.tokens_resposta?.toLocaleString("pt-BR")}</td>
                                <td className="py-2.5 text-right text-slate-400">{item.tempo_segundos}s</td>
                                <td className="py-2.5 text-right font-bold text-emerald-400">R$ {item.custo_brl?.toFixed(4)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </section>
              )}
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