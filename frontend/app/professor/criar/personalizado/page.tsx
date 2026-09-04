"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { db, auth } from "@/lib/firebase";
import { collection, getDocs, addDoc, serverTimestamp } from "firebase/firestore";
import { onAuthStateChanged } from "firebase/auth";
import DisciplinaSelect from "@/components/DisciplinaSelect";

export default function CriarSalaPersonalizada() {
  const router = useRouter();
  
  // Data
  const [disciplinas, setDisciplinas] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // General Settings
  const [selectedDisciplina, setSelectedDisciplina] = useState("");
  const [diretrizesGerais, setDiretrizesGerais] = useState("");
  
  // Logic Tree State
  const [modoCriacao, setModoCriacao] = useState<"magico" | "artesao">("magico");
  const [modeloLlm, setModeloLlm] = useState<"2.5" | "3.5">("3.5");

  // Expander States
  const [expandedBlocks, setExpandedBlocks] = useState<Record<number, boolean>>({});
  const [showGlobalAdvanced, setShowGlobalAdvanced] = useState(false);

  const toggleBlockExpand = (id: number) => {
    setExpandedBlocks(prev => ({ ...prev, [id]: !prev[id] }));
  };

  
  // Magic Mode Settings
  const [modoAulas, setModoAulas] = useState<"padrao" | "auto" | "manual">("padrao");
  const [qtdManual, setQtdManual] = useState<number>(30);

  // Upload Global (Quando for Mágico)
  const [uploadingGlobal, setUploadingGlobal] = useState(false);
  const [arquivoGlobalPdf, setArquivoGlobalPdf] = useState("");
  const [arquivoGlobalNome, setArquivoGlobalNome] = useState("");
  const globalPdfRef = useRef<HTMLInputElement>(null);

  // Blocos Manuais (Quando for Artesão)
  const [aulasManuais, setAulasManuais] = useState<any[]>([{
    id: 1,
    titulo: "",
    descricao: "",
    texto_base_pdf: "",
    texto_base_notacoes: "",
    nome_arquivo: "",
    nome_arquivo_notacoes: "",
    uploading: false,
    uploading_notacoes: false,
    gerar_exercicios: true,
    sugestoes_exercicios: "",
    gerar_simulador: true,
    sugestoes_simulador: ""
  }]);
  const fileInputRefs = useRef<any>({});
  const fileInputRefsNotacoes = useRef<any>({});

  useEffect(() => {
    async function loadDisciplinas() {
      try {
        const discSnapshot = await getDocs(collection(db, "disciplinas"));
        const discList = discSnapshot.docs.map(d => ({ id: d.id, ...(d.data() as any) }));
        setDisciplinas(discList);
        if (discList.length > 0) setSelectedDisciplina(discList[0].id_disciplina);
      } catch (error) {
        console.error("Erro ao carregar disciplinas:", error);
      } finally {
        setLoading(false);
      }
    }
    loadDisciplinas();
  }, []);

  const handleGlobalFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploadingGlobal(true);
    
    const formData = new FormData();
    let validFilesCount = 0;
    
    for (let i = 0; i < files.length; i++) {
        if (files[i].name.toLowerCase().endsWith(".pdf")) {
            formData.append("files", files[i]);
            validFilesCount++;
        }
    }
    
    if (validFilesCount === 0) {
        alert("Somente arquivos PDF são suportados.");
        setUploadingGlobal(false);
        return;
    }

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/upload_pdf`, { method: "POST", body: formData });
      const data = await res.json();
      if (res.ok) {
        setArquivoGlobalPdf(data.texto_extraido);
        setArquivoGlobalNome(`${validFilesCount} arquivo(s) processado(s) com sucesso`);
      } else {
        alert("Erro no upload: " + data.detail);
      }
    } catch (e) {
      alert("Erro de rede");
    } finally {
      setUploadingGlobal(false);
    }
  };

  const handleBlocoFileUpload = async (index: number, file: File) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) return alert("Somente arquivos PDF.");
    
    const updated = [...aulasManuais];
    updated[index].uploading = true;
    setAulasManuais(updated);

    const formData = new FormData();
    formData.append("files", file);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/upload_pdf`, { method: "POST", body: formData });
      const data = await res.json();
      const nextUpdated = [...aulasManuais];
      
      if (res.ok) {
        nextUpdated[index].texto_base_pdf = data.texto_extraido;
        nextUpdated[index].nome_arquivo = file.name;
      } else {
        alert("Erro no upload: " + data.detail);
      }
      nextUpdated[index].uploading = false;
      setAulasManuais(nextUpdated);
    } catch (e) {
      alert("Erro na rede ao enviar PDF");
      const nextUpdated = [...aulasManuais];
      nextUpdated[index].uploading = false;
      setAulasManuais(nextUpdated);
    }
  };

  const handleNotacoesFileUpload = async (index: number, file: File) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) return alert("Somente arquivos PDF.");
    
    const updated = [...aulasManuais];
    updated[index].uploading_notacoes = true;
    setAulasManuais(updated);

    const formData = new FormData();
    formData.append("files", file);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/upload_pdf`, { method: "POST", body: formData });
      const data = await res.json();
      const nextUpdated = [...aulasManuais];
      
      if (res.ok) {
        nextUpdated[index].texto_base_notacoes = data.texto_extraido;
        nextUpdated[index].nome_arquivo_notacoes = file.name;
      } else {
        alert("Erro no upload: " + data.detail);
      }
      nextUpdated[index].uploading_notacoes = false;
      setAulasManuais(nextUpdated);
    } catch (e) {
      alert("Erro na rede ao enviar PDF");
      const nextUpdated = [...aulasManuais];
      nextUpdated[index].uploading_notacoes = false;
      setAulasManuais(nextUpdated);
    }
  };

  const addBloco = () => {
    setAulasManuais([...aulasManuais, {
      id: aulasManuais.length + 1,
      titulo: "",
      descricao: "",
      texto_base_pdf: "",
      texto_base_notacoes: "",
      nome_arquivo: "",
      nome_arquivo_notacoes: "",
      uploading: false,
      uploading_notacoes: false,
      gerar_exercicios: true,
      sugestoes_exercicios: "",
      gerar_simulador: true,
      sugestoes_simulador: ""
    }]);
  };

  const removeBloco = (index: number) => {
    if (aulasManuais.length === 1) return;
    const updated = [...aulasManuais];
    updated.splice(index, 1);
    setAulasManuais(updated);
  };

  const handleSubmit = async () => {
    if (!selectedDisciplina) return alert("Selecione uma disciplina.");
    if (modoCriacao === "magico" && modoAulas === "manual" && (qtdManual < 1 || qtdManual > 100)) {
        return alert("Quantidade manual deve ser entre 1 e 100.");
    }
    if (modoCriacao === "artesao" && aulasManuais.some(a => !a.titulo.trim())) {
        return alert("Todas as aulas no Modo Artesão precisam de pelo menos um Título.");
    }
    
    setSubmitting(true);
    
    try {
      const code = Math.floor(1000 + Math.random() * 9000).toString();
      const disc = disciplinas.find(d => d.id_disciplina === selectedDisciplina);
      
      const docRef = await addDoc(collection(db, "classrooms"), {
        code,
        teacherId: auth.currentUser?.uid || "TEST_PROFESSOR_123",
        id_disciplina: selectedDisciplina,
        nome_disciplina: disc?.nome || "Disciplina",
        createdAt: serverTimestamp(),
        status: "creating_semester",
        modo_criacao: "livre"
      });

      // Mapeamento
      let payloadTipoCarga = "padrao_30";
      let payloadLimite = 30;
      const isBlocoABloco = modoCriacao === "artesao";

      if (isBlocoABloco) {
          payloadTipoCarga = "manual";
          payloadLimite = aulasManuais.length;
      } else {
          if (modoAulas === "padrao") {
              payloadTipoCarga = "auto_ementa"; 
          } else if (modoAulas === "auto") {
              payloadTipoCarga = "auto_ia"; 
          } else if (modoAulas === "manual") {
              payloadTipoCarga = "manual";
              payloadLimite = qtdManual;
          }
      }

      const formattedBlocos = isBlocoABloco ? aulasManuais.map(a => ({
          titulo: a.titulo || "Sem título",
          descricao: a.descricao + (a.gerar_exercicios && a.sugestoes_exercicios ? `\n(Dica p/ Exercícios: ${a.sugestoes_exercicios})` : "") + (a.gerar_simulador && a.sugestoes_simulador ? `\n(Dica p/ Simulador: ${a.sugestoes_simulador})` : ""),
          texto_base_pdf: a.texto_base_pdf || "",
          texto_base_notacoes: a.texto_base_notacoes || "",
          gerar_exercicios: a.gerar_exercicios,
          gerar_simulador: a.gerar_simulador
      })) : [];

      const payload = {
        id_sala: docRef.id,
        id_disciplina: selectedDisciplina,
        modo: "livre",
        instrucoes_personalizadas: diretrizesGerais,
        max_aulas: payloadLimite, 
        limite_execucao: payloadLimite,
        tipo_carga_horaria: payloadTipoCarga,
        permitir_aprofundamento: false, // Default desativado
        tipo_crie_seu_jeito: isBlocoABloco ? "bloco_a_bloco" : "automatico",
        arquivo_global_pdf: isBlocoABloco ? "" : arquivoGlobalPdf,
        aulas_manuais: formattedBlocos,
        modelo_llm: modeloLlm
      };

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      fetch(`${apiUrl}/api/gerar_semestre`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }).catch(err => {
        console.error("Erro ao chamar API de geração", err);
      });

      router.push("/professor/dashboard");

    } catch (error) {
      console.error("Erro ao criar sala:", error);
      alert("Erro ao criar a sala.");
      setSubmitting(false);
    }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center text-slate-500">Carregando...</div>;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-20">
      <nav className="bg-blue-900 text-white px-6 py-4 flex justify-between items-center shadow-md sticky top-0 z-50">
        <div>
          <h1 className="text-xl font-bold">Painel do Professor</h1>
        </div>
        <button onClick={() => router.push("/professor/dashboard")} className="text-sm bg-blue-800 px-4 py-2 rounded hover:bg-blue-700 transition">Voltar</button>
      </nav>

      <main className="max-w-4xl mx-auto mt-8 p-6">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8">
            <div className="flex items-center gap-4 mb-6">
                <div className="text-4xl">✏️</div>
                <div>
                    <h2 className="text-2xl font-bold text-slate-800">Crie do Seu Jeito</h2>
                    <p className="text-slate-500">Controle absoluto sobre a criação do semestre. Dite as regras gerais, forneça seus materiais e monte aula a aula se preferir.</p>
                </div>
            </div>

            <DisciplinaSelect
              disciplinas={disciplinas}
              value={selectedDisciplina}
              onChange={setSelectedDisciplina}
            />


            <div className="mb-8">
                <label className="block text-sm font-bold text-slate-700 mb-2">Diretrizes Gerais e Estilo (Opcional)</label>
                <textarea
                placeholder="Ex: Quero um tom provocativo, foco em aplicações práticas, e exercícios de nível IME/ITA..."
                className="w-full p-4 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 bg-slate-50"
                rows={4}
                value={diretrizesGerais}
                onChange={(e) => setDiretrizesGerais(e.target.value)}
                />
            </div>

            <div className="mb-8 p-6 bg-indigo-50 rounded-xl border border-indigo-100">
                <h4 className="text-lg font-bold text-indigo-900 mb-4">Como você deseja criar o semestre?</h4>
                <div className="flex flex-col md:flex-row gap-4">
                    <button 
                        onClick={() => setModoCriacao("magico")}
                        className={`flex-1 py-6 px-4 rounded-xl font-bold border-2 transition-all flex flex-col items-center justify-center ${modoCriacao === "magico" ? "bg-indigo-600 border-indigo-600 text-white shadow-lg scale-105" : "bg-white border-indigo-200 text-indigo-700 hover:bg-indigo-100"}`}
                    >
                        <span className="block text-4xl mb-3">🪄</span>
                        Modo Mágico
                        <span className="block text-sm font-normal opacity-90 mt-2 text-center">Jogue todos os seus PDFs e deixe a IA criar e dividir todo o cronograma.</span>
                    </button>
                    <button 
                        onClick={() => setModoCriacao("artesao")}
                        className={`flex-1 py-6 px-4 rounded-xl font-bold border-2 transition-all flex flex-col items-center justify-center ${modoCriacao === "artesao" ? "bg-indigo-600 border-indigo-600 text-white shadow-lg scale-105" : "bg-white border-indigo-200 text-indigo-700 hover:bg-indigo-100"}`}
                    >
                        <span className="block text-4xl mb-3">🛠️</span>
                        Modo Artesão
                        <span className="block text-sm font-normal opacity-90 mt-2 text-center">Monte você mesmo a lista de aulas, informando tópicos e PDFs individuais.</span>
                    </button>
                </div>
            </div>

            {/* ZONA CONDICIONAL: MODO MÁGICO VS MODO ARTESÃO */}
            {modoCriacao === "magico" ? (
                <div className="mt-12 p-8 border-2 border-dashed border-slate-300 rounded-2xl bg-slate-50 text-center animate-fade-in">
                    <div className="text-5xl mb-4">📚</div>
                    <h3 className="text-xl font-bold text-slate-800 mb-2">Piscina Global de Arquivos</h3>
                    <p className="text-slate-500 mb-6 max-w-lg mx-auto">Anexe seus materiais, anotações ou livros em PDF. A IA lerá tudo e moldará as aulas automaticamente baseada nisso.</p>
                    
                    <input type="file" ref={globalPdfRef} className="hidden" accept=".pdf" multiple onChange={e => handleGlobalFileUpload(e.target.files)} />
                    <button 
                        onClick={() => globalPdfRef.current?.click()}
                        className="bg-slate-800 text-white px-8 py-3 rounded-full font-bold shadow-md hover:bg-slate-700 transition"
                        disabled={uploadingGlobal}
                    >
                        {uploadingGlobal ? "Extraindo textos..." : "📎 Anexar Múltiplos PDFs"}
                    </button>
                    {arquivoGlobalNome && <p className="text-green-600 mt-4 font-bold bg-green-50 inline-block px-4 py-2 rounded-full border border-green-200">✓ {arquivoGlobalNome}</p>}

                    <div className="mt-12 text-left border-t border-slate-200 pt-8">
                        <h3 className="text-lg font-bold text-slate-800 mb-4">Quantidade de Aulas do Semestre</h3>
                        <div className="space-y-3">
                            <label className="flex items-center gap-3 p-3 bg-white border border-slate-200 rounded-lg cursor-pointer hover:border-blue-400">
                                <input type="radio" checked={modoAulas === "padrao"} onChange={() => setModoAulas("padrao")} className="w-4 h-4 text-blue-600" />
                                <span className="font-medium text-slate-700">Usar carga horária da ementa (Ex: 30 aulas)</span>
                            </label>
                            <label className="flex items-center gap-3 p-3 bg-white border border-slate-200 rounded-lg cursor-pointer hover:border-blue-400">
                                <input type="radio" checked={modoAulas === "auto"} onChange={() => setModoAulas("auto")} className="w-4 h-4 text-blue-600" />
                                <span className="font-medium text-slate-700">Deixar a IA decidir com base no tamanho do material</span>
                            </label>
                            <label className="flex items-center gap-3 p-3 bg-white border border-slate-200 rounded-lg cursor-pointer hover:border-blue-400">
                                <input type="radio" checked={modoAulas === "manual"} onChange={() => setModoAulas("manual")} className="w-4 h-4 text-blue-600" />
                                <span className="font-medium text-slate-700">Quero um número exato de aulas</span>
                            </label>
                        </div>
                    </div>

                    {modoAulas === "manual" && (
                        <div className="mt-4 p-4 bg-blue-50 rounded-xl border border-blue-100 flex items-center justify-center gap-4 animate-fade-in">
                            <label className="text-sm font-bold text-blue-900">Total Exato de Aulas:</label>
                            <input 
                                type="number" min="1" max="100" 
                                value={qtdManual} 
                                onChange={e => setQtdManual(Number(e.target.value))} 
                                className="p-2 border border-blue-200 rounded w-24 text-center font-bold text-blue-900 shadow-inner"
                            />
                        </div>
                    )}
                </div>
            ) : (
                <div className="mt-12 animate-fade-in">
                    <h3 className="text-2xl font-bold text-slate-800 mb-6 flex items-center gap-2">🛠️ Artesão de Aulas</h3>
                    <p className="text-slate-500 mb-8">Adicione blocos abaixo. Cada bloco gerará uma aula individual no seu semestre final. Você tem total controle.</p>
                    
                    <div className="space-y-8">
                    {aulasManuais.map((bloco, idx) => (
                        <div key={idx} className="border border-slate-300 bg-white shadow-sm p-6 rounded-2xl relative transition-all">
                            <div className="absolute -top-4 -left-4 bg-blue-600 text-white w-10 h-10 flex items-center justify-center rounded-full font-black text-lg border-4 border-slate-50 shadow">
                                {idx + 1}
                            </div>
                            

                            
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6 mt-2">
                                <div>
                                    <label className="block text-sm font-bold text-slate-700 mb-2">Título da Aula (Tema Principal)</label>
                                    <input 
                                        type="text" 
                                        className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500" 
                                        placeholder="Ex: Introdução à Dinâmica"
                                        value={bloco.titulo}
                                        onChange={(e) => { const n = [...aulasManuais]; n[idx].titulo = e.target.value; setAulasManuais(n); }}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-bold text-slate-700 mb-2">Arquivo Base da Aula (Opcional)</label>
                                    <div className="flex items-center gap-2">
                                        <input 
                                            type="file" accept=".pdf" className="hidden"
                                            ref={el => { fileInputRefs.current[idx] = el; }}
                                            onChange={(e) => { if (e.target.files && e.target.files[0]) handleBlocoFileUpload(idx, e.target.files[0]); }}
                                        />
                                        <button 
                                            onClick={() => fileInputRefs.current[idx]?.click()}
                                            className="bg-slate-50 border border-slate-300 text-slate-700 px-4 py-3 rounded-lg text-sm font-bold hover:bg-slate-100 flex-1 flex justify-center items-center transition shadow-sm"
                                            disabled={bloco.uploading}
                                        >
                                            {bloco.uploading ? "Lendo PDF..." : "📎 Escolher PDF Específico"}
                                        </button>
                                    </div>
                                    {bloco.nome_arquivo && <p className="text-xs text-green-600 mt-2 font-bold px-2">✓ {bloco.nome_arquivo}</p>}
                                </div>
                            </div>
                            
                            <div className="mb-6">
                                <label className="block text-sm font-bold text-slate-700 mb-2">Diretrizes ou O que cobrir? (Opcional)</label>
                                <textarea 
                                    className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500" 
                                    rows={2}
                                    placeholder="Ex: Explicar a segunda lei de Newton e dar exemplos do dia a dia..."
                                    value={bloco.descricao}
                                    onChange={(e) => { const n = [...aulasManuais]; n[idx].descricao = e.target.value; setAulasManuais(n); }}
                                />
                            </div>

                            {/* Expander de Configurações Avançadas da Aula */}
                            <div className="mt-6">
                                <button
                                    type="button"
                                    onClick={() => toggleBlockExpand(bloco.id)}
                                    className="flex items-center justify-between w-full py-3 px-4 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl transition text-sm"
                                >
                                    <span className="flex items-center gap-2">⚙️ Configurações Avançadas da Aula</span>
                                    <span>{expandedBlocks[bloco.id] ? "▲" : "▼"}</span>
                                </button>
                                {expandedBlocks[bloco.id] && (
                                    <div className="mt-4 p-5 border border-slate-200 bg-slate-50/50 rounded-2xl space-y-6">
                                        <div className="mb-4">
                                            <label className="block text-sm font-bold text-slate-700 mb-2">Arquivo de Notações Específicas (PDF)</label>
                                            <div className="flex items-center gap-2">
                                                <input 
                                                    type="file" accept=".pdf" className="hidden"
                                                    ref={el => { fileInputRefsNotacoes.current[bloco.id] = el; }}
                                                    onChange={(e) => { if (e.target.files && e.target.files[0]) handleNotacoesFileUpload(idx, e.target.files[0]); }}
                                                />
                                                <button 
                                                    type="button"
                                                    onClick={() => fileInputRefsNotacoes.current[bloco.id]?.click()}
                                                    className="bg-white border border-slate-300 text-slate-700 px-4 py-3 rounded-lg text-sm font-bold hover:bg-slate-100 flex-1 flex justify-center items-center transition shadow-sm"
                                                    disabled={bloco.uploading_notacoes}
                                                >
                                                    {bloco.uploading_notacoes ? "Lendo PDF..." : "📎 Carregar PDF de Notações"}
                                                </button>
                                            </div>
                                            {bloco.nome_arquivo_notacoes && (
                                                <p className="text-xs text-green-600 mt-2 font-bold px-2">✓ {bloco.nome_arquivo_notacoes}</p>
                                            )}
                                        </div>



                                        <div className="flex flex-col gap-4 p-4 bg-white border border-slate-200 rounded-xl">
                                            <div>
                                                <label className="flex items-center gap-2 font-bold text-slate-800 cursor-pointer">
                                                    <input type="checkbox" checked={bloco.gerar_exercicios} onChange={(e) => { const n = [...aulasManuais]; n[idx].gerar_exercicios = e.target.checked; setAulasManuais(n); }} className="w-5 h-5 text-blue-600 rounded" />
                                                    Gerar Exercícios ao Final
                                                </label>
                                                {bloco.gerar_exercicios && (
                                                    <input 
                                                        type="text" 
                                                        placeholder="Sugestões? (Ex: 3 abertas, 2 de múltipla escolha sobre atrito). Deixe em branco p/ IA decidir."
                                                        className="w-full mt-3 p-3 border border-slate-300 rounded-lg text-sm shadow-sm"
                                                        value={bloco.sugestoes_exercicios}
                                                        onChange={(e) => { const n = [...aulasManuais]; n[idx].sugestoes_exercicios = e.target.value; setAulasManuais(n); }}
                                                    />
                                                )}
                                            </div>
                                            <hr className="border-slate-200" />
                                            <div>
                                                <label className="flex items-center gap-2 font-bold text-slate-800 cursor-pointer">
                                                    <input type="checkbox" checked={bloco.gerar_simulador} onChange={(e) => { const n = [...aulasManuais]; n[idx].gerar_simulador = e.target.checked; setAulasManuais(n); }} className="w-5 h-5 text-blue-600 rounded" />
                                                    Injetar Simulador Interativo
                                                </label>
                                                {bloco.gerar_simulador && (
                                                    <input 
                                                        type="text" 
                                                        placeholder="Sugestões? (Ex: Mostrar um bloco deslizando num plano inclinado). Deixe em branco p/ IA decidir."
                                                        className="w-full mt-3 p-3 border border-slate-300 rounded-lg text-sm shadow-sm"
                                                        value={bloco.sugestoes_simulador}
                                                        onChange={(e) => { const n = [...aulasManuais]; n[idx].sugestoes_simulador = e.target.value; setAulasManuais(n); }}
                                                    />
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                            
                            {aulasManuais.length > 1 && (
                                <div className="mt-4 flex justify-end">
                                    <button 
                                        onClick={() => removeBloco(idx)}
                                        className="text-red-600 hover:bg-red-50 px-4 py-2 rounded-lg font-bold transition flex items-center gap-2 border border-transparent hover:border-red-200"
                                    >
                                        🗑️ Remover esta aula
                                    </button>
                                </div>
                            )}
                        </div>
                    ))}
                    </div>
                    
                    <button onClick={addBloco} className="mt-8 w-full py-5 border-2 border-dashed border-blue-400 text-blue-600 font-black text-xl rounded-2xl hover:bg-blue-50 transition shadow-sm flex items-center justify-center gap-2">
                        <span>➕</span> ADICIONAR PRÓXIMA AULA
                    </button>
                </div>
            )}

            {/* Expander de Configurações Avançadas do Semestre */}
            <div className="mt-8 border border-slate-200 rounded-xl bg-white shadow-sm overflow-hidden">
                <button
                    type="button"
                    onClick={() => setShowGlobalAdvanced(!showGlobalAdvanced)}
                    className="w-full p-6 text-left font-bold text-slate-800 flex justify-between items-center bg-slate-50 hover:bg-slate-100/80 transition"
                >
                    <span className="flex items-center gap-2">⚙️ Configurações Avançadas do Semestre</span>
                    <span>{showGlobalAdvanced ? "▲" : "▼"}</span>
                </button>
                {showGlobalAdvanced && (
                    <div className="p-6 border-t border-slate-200 space-y-6 bg-white">
                        <div>
                            <label className="block text-sm font-bold text-slate-700 mb-2">Motor de Inteligência Artificial & Modo de Custo</label>
                            <div className="flex items-start p-4 rounded-xl border-2 border-indigo-600 bg-indigo-50/70 shadow-sm">
                                <span className="text-2xl mr-3">🚀</span>
                                <div>
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="font-bold text-slate-800 text-sm">Gemini 3.6 Flash + 3.5 Flash-Lite</span>
                                        <span className="text-[10px] bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded-full font-bold">Alta Inteligência & Extensão</span>
                                    </div>
                                    <div className="text-xs text-slate-600 leading-relaxed mb-2">Escrita teórica densa e simuladores com <strong>Gemini 3.6 Flash</strong> + suporte rápido com <strong>Gemini 3.5 Flash-Lite</strong>.</div>
                                    <div className="text-xs font-semibold text-indigo-700">~R$ 0,35 a R$ 0,50 / aula completa</div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <div className="pt-8 mt-6 border-t border-slate-200 flex justify-end gap-4">
                <button 
                  onClick={() => router.push("/professor/dashboard")}
                  className="px-8 py-4 rounded-xl font-bold text-slate-600 bg-slate-100 hover:bg-slate-200 transition"
                >
                  Cancelar
                </button>
                <button 
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="flex-1 max-w-sm bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 rounded-xl font-black text-lg shadow-xl transition-all flex justify-center items-center gap-2"
                >
                  {submitting ? "Processando..." : "Construir Semestre 🚀"}
                </button>
            </div>
        </div>
      </main>
    </div>
  );
}
