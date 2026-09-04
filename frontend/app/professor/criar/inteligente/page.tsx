"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { db, auth } from "@/lib/firebase";
import { collection, getDocs, addDoc, serverTimestamp } from "firebase/firestore";
import { onAuthStateChanged } from "firebase/auth";

export default function CriarSalaInteligente() {
  const router = useRouter();
  
  // Data
  const [disciplinas, setDisciplinas] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Form State
  const [selectedDisciplina, setSelectedDisciplina] = useState("");
  const [modoDefinicao, setModoDefinicao] = useState<"padrao" | "auto" | "manual">("padrao");
  const [qtdManual, setQtdManual] = useState<number>(30);
  const [aulasComplementares, setAulasComplementares] = useState(false);
  const [modeloLlm, setModeloLlm] = useState<"2.5" | "3.5">("3.5");
  const [showGlobalAdvanced, setShowGlobalAdvanced] = useState(false);

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

  const handleSubmit = async () => {
    if (!selectedDisciplina) return alert("Selecione uma disciplina.");
    if (modoDefinicao === "manual" && (qtdManual < 1 || qtdManual > 100)) {
        return alert("Quantidade manual deve ser entre 1 e 100.");
    }
    
    setSubmitting(true);
    
    try {
      const code = Math.floor(1000 + Math.random() * 9000).toString();
      const disc = disciplinas.find(d => d.id_disciplina === selectedDisciplina);
      
      // Salva a "Sala do Semestre" no Firestore
      const docRef = await addDoc(collection(db, "classrooms"), {
        code,
        teacherId: auth.currentUser?.uid || "TEST_PROFESSOR_123",
        id_disciplina: selectedDisciplina,
        nome_disciplina: disc?.nome || "Disciplina",
        createdAt: serverTimestamp(),
        status: "creating_semester",
        modo_criacao: "inteligente"
      });

      // Mapeamento para o Backend
      let payloadTipoCarga = "padrao_30";
      let payloadLimite = 30; // Default

      if (modoDefinicao === "padrao") {
          payloadTipoCarga = "auto_ementa"; // Backend vai usar a CH da ementa
      } else if (modoDefinicao === "auto") {
          payloadTipoCarga = "auto_ia"; // Novo tipo no backend
      } else if (modoDefinicao === "manual") {
          payloadTipoCarga = "manual";
          payloadLimite = qtdManual;
      }

      const payload = {
        id_sala: docRef.id,
        id_disciplina: selectedDisciplina,
        modo: "inteligente",
        instrucoes_personalizadas: "",
        max_aulas: payloadLimite, 
        limite_execucao: payloadLimite,
        tipo_carga_horaria: payloadTipoCarga,
        permitir_aprofundamento: aulasComplementares,
        tipo_crie_seu_jeito: "bloco_a_bloco",
        arquivo_global_pdf: "",
        aulas_manuais: [],
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
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      <nav className="bg-blue-900 text-white px-6 py-4 flex justify-between items-center shadow-md">
        <div>
          <h1 className="text-xl font-bold">Painel do Professor</h1>
        </div>
        <button onClick={() => router.push("/professor/dashboard")} className="text-sm bg-blue-800 px-4 py-2 rounded hover:bg-blue-700 transition">Voltar</button>
      </nav>

      <main className="max-w-3xl mx-auto mt-12 p-6">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8">
            <div className="flex items-center gap-4 mb-6">
                <div className="text-4xl">✨</div>
                <div>
                    <h2 className="text-2xl font-bold text-slate-800">Criar Sala Inteligente</h2>
                    <p className="text-slate-500">A IA construirá o cronograma estritamente via ementa oficial.</p>
                </div>
            </div>

            <div className="mb-8">
                <label className="block text-sm font-bold text-slate-700 mb-2">Disciplina da Grade Oficial</label>
                <select
                className="w-full p-4 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 text-slate-800 bg-slate-50"
                value={selectedDisciplina}
                onChange={(e) => setSelectedDisciplina(e.target.value)}
                >
                {disciplinas.map((d) => (
                    <option key={d.id_disciplina} value={d.id_disciplina}>
                    {d.id_disciplina} - {d.nome}
                    </option>
                ))}
                </select>
            </div>

            <div className="mb-8 p-6 border border-slate-200 rounded-xl bg-slate-50">
                <label className="block text-sm font-bold text-slate-700 mb-4">Definição da Quantidade de Aulas</label>
                
                <div className="space-y-3">
                    <label className="flex items-center gap-3 p-3 bg-white border border-slate-200 rounded-lg cursor-pointer hover:border-blue-400">
                        <input type="radio" name="modo_aulas" checked={modoDefinicao === "padrao"} onChange={() => setModoDefinicao("padrao")} className="w-4 h-4 text-blue-600" />
                        <span className="font-medium text-slate-700">Usar carga horária da ementa (Padrão)</span>
                    </label>
                    <label className="flex items-center gap-3 p-3 bg-white border border-slate-200 rounded-lg cursor-pointer hover:border-blue-400">
                        <input type="radio" name="modo_aulas" checked={modoDefinicao === "auto"} onChange={() => setModoDefinicao("auto")} className="w-4 h-4 text-blue-600" />
                        <span className="font-medium text-slate-700">Deixar a IA decidir (entre 20 e 40 aulas)</span>
                    </label>
                    <label className="flex items-center gap-3 p-3 bg-white border border-slate-200 rounded-lg cursor-pointer hover:border-blue-400">
                        <input type="radio" name="modo_aulas" checked={modoDefinicao === "manual"} onChange={() => setModoDefinicao("manual")} className="w-4 h-4 text-blue-600" />
                        <span className="font-medium text-slate-700">Manual (Quantidade exata)</span>
                    </label>
                </div>

                {modoDefinicao === "manual" && (
                    <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-100 flex items-center gap-4 animate-fade-in">
                        <label className="text-sm font-bold text-blue-900">Quantas aulas deseja no semestre?</label>
                        <input 
                            type="number" 
                            min="1" max="100" 
                            value={qtdManual} 
                            onChange={e => setQtdManual(Number(e.target.value))} 
                            className="p-2 border border-blue-200 rounded w-24 text-center font-bold text-blue-900"
                        />
                    </div>
                )}
            </div>

            {/* Expander de Configurações Avançadas do Semestre */}
            <div className="mb-8 border border-slate-200 rounded-xl bg-white shadow-sm overflow-hidden">
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
                            <div className="flex items-start p-4 rounded-xl border-2 border-emerald-600 bg-emerald-50/70 shadow-sm">
                                <span className="text-2xl mr-3">⚡</span>
                                <div>
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="font-bold text-slate-800 text-sm">Gemini 3.5 Flash-Lite</span>
                                        <span className="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full font-bold">Ultra Econômico & Rápido</span>
                                    </div>
                                    <div className="text-xs text-slate-600 leading-relaxed mb-2">Todos os agentes rodam 100% no Gemini 3.5 Flash-Lite com velocidade máxima e auditoria de tokens.</div>
                                    <div className="text-xs font-semibold text-emerald-700">~R$ 0,17 / aula completa</div>
                                </div>
                            </div>
                        </div>

                        <hr className="border-slate-200" />

                        <div>
                            <label className="flex items-center gap-3 p-4 border border-slate-300 rounded-xl bg-slate-50/50 cursor-pointer hover:bg-slate-50">
                                <input 
                                type="checkbox" 
                                checked={aulasComplementares}
                                onChange={(e) => setAulasComplementares(e.target.checked)}
                                className="w-5 h-5 text-blue-600 rounded"
                                />
                                <div>
                                <span className="block font-bold text-slate-800">Permitir Aulas Complementares de Aprofundamento</span>
                                <span className="text-sm text-slate-500">Autoriza a IA a ultrapassar o limite de aulas sugerindo tópicos de nivelamento/aprofundamento.</span>
                                </div>
                            </label>
                        </div>
                    </div>
                )}
            </div>

            <div className="pt-6 border-t border-slate-200 flex justify-end gap-4">
                <button 
                  onClick={() => router.push("/professor/dashboard")}
                  className="px-6 py-3 rounded-lg font-bold text-slate-600 bg-slate-100 hover:bg-slate-200 transition"
                >
                  Cancelar
                </button>
                <button 
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 rounded-lg font-bold shadow-md transition-all flex justify-center items-center gap-2"
                >
                  {submitting ? "Iniciando IA..." : "Gerar Semestre Inteligente 🚀"}
                </button>
            </div>
        </div>
      </main>
    </div>
  );
}
