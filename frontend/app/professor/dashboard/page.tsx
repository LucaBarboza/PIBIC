"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { auth, db } from "@/lib/firebase";
import { signOut, onAuthStateChanged } from "firebase/auth";
import { collection, addDoc, serverTimestamp, getDocs, doc, getDoc, query, where, orderBy, deleteDoc, onSnapshot } from "firebase/firestore";

export default function ProfessorDashboard() {
  const router = useRouter();
  
  // User Profile
  const [professorName, setProfessorName] = useState("Professor de Estatística");
  const [professorDept, setProfessorDept] = useState("Departamento de Estatística - UFBA");

  // States
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"list" | "create">("list");
  // Removed old form states and handlers (they moved to dedicated pages)
  
  // Data
  const [minhasSalas, setMinhasSalas] = useState<any[]>([]);
  const [debuggerState, setDebuggerState] = useState<{salaId: string, aulaNum: number} | null>(null);
  const [disciplinas, setDisciplinas] = useState<any[]>([]);

  useEffect(() => {
    let unsubscribeSalas: (() => void) | undefined;

    // Se houver usuário autenticado, carregar nome se disponível
    if (auth.currentUser) {
      getDoc(doc(db, "users", auth.currentUser.uid)).then(userDoc => {
        if (userDoc.exists()) {
          setProfessorName(userDoc.data().nome || "Professor de Estatística");
          setProfessorDept(userDoc.data().departamento || "Departamento de Estatística - UFBA");
        }
      }).catch(console.error);
    }

    // Buscar Salas em TEMPO REAL (onSnapshot)
    try {
      const qSalas = query(
        collection(db, "classrooms"), 
        orderBy("createdAt", "desc")
      );
      
      unsubscribeSalas = onSnapshot(qSalas, (snapshot) => {
        const salasList = snapshot.docs.map(d => ({ id: d.id, ...d.data() }));
        setMinhasSalas(salasList);
        setLoading(false);
      }, (error) => {
        console.warn("Aviso: Tentando fallback sem orderBy para salas:", error);
        unsubscribeSalas = onSnapshot(collection(db, "classrooms"), (s) => {
          const list = s.docs.map(d => ({ id: d.id, ...d.data() }));
          list.sort((a: any, b: any) => (b.createdAt?.seconds || 0) - (a.createdAt?.seconds || 0));
          setMinhasSalas(list);
          setLoading(false);
        }, (err2) => {
          console.error("Erro ao carregar salas:", err2);
          setLoading(false);
        });
      });
    } catch (error) {
      console.error("Erro ao inicializar listener de salas:", error);
      setLoading(false);
    }

    // Buscar Disciplinas disponíveis no Banco
    getDocs(collection(db, "disciplinas")).then(discSnapshot => {
      const discList = discSnapshot.docs.map(d => ({ id: d.id, ...(d.data() as any) }));
      setDisciplinas(discList);
    }).catch(error => {
      console.error("Erro ao carregar disciplinas:", error);
    });

    return () => {
      if (unsubscribeSalas) unsubscribeSalas();
    };
  }, []);

  const handleLogout = async () => {
    try {
      await signOut(auth);
    } catch(e) {}
    router.push("/");
  };

  const deleteClassroom = async (salaId: string) => {
    if (confirm("Tem certeza que deseja apagar esta sala?")) {
      try {
        await deleteDoc(doc(db, "classrooms", salaId));
        setMinhasSalas(minhasSalas.filter(s => s.id !== salaId));
      } catch (e) {
        console.error("Erro ao apagar sala:", e);
        alert("Erro ao apagar sala.");
      }
    }
  };

  // Removed createClassroom
  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-slate-500">Carregando painel...</div>;
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      <nav className="bg-blue-900 text-white px-4 sm:px-6 py-3 sm:py-4 flex justify-between items-center shadow-md">
        <div className="truncate pr-2">
          <h1 className="text-lg sm:text-xl font-bold truncate">Painel do Professor</h1>
          <p className="text-[10px] sm:text-xs text-blue-200 truncate">{professorName} | {professorDept}</p>
        </div>
        <button onClick={handleLogout} className="text-xs sm:text-sm bg-blue-800 px-3 py-1.5 sm:px-4 sm:py-2 rounded hover:bg-blue-700 transition shrink-0">Sair</button>
      </nav>

      <main className="max-w-5xl mx-auto mt-4 sm:mt-8 p-4 sm:p-6">
        
        {/* Hub de Navegação */}
        <div className="flex gap-2 sm:gap-4 mb-6 sm:mb-8 overflow-x-auto pb-2">
          <button 
            onClick={() => { setView("list"); }}
            className={`px-4 sm:px-6 py-2 rounded-full text-xs sm:text-sm whitespace-nowrap font-medium transition ${view === "list" ? "bg-blue-600 text-white" : "bg-white text-slate-600 border border-slate-300"}`}
          >
            📚 Minhas Turmas Ativas
          </button>
          <button 
            onClick={() => setView("create")}
            className={`px-4 sm:px-6 py-2 rounded-full text-xs sm:text-sm whitespace-nowrap font-medium transition ${view === "create" ? "bg-blue-600 text-white" : "bg-white text-slate-600 border border-slate-300"}`}
          >
            ✨ Gerar Novo Semestre
          </button>
        </div>

        {/* View: Lista de Turmas */}
        {view === "list" && (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 sm:p-6 md:p-8">
            <h2 className="text-xl sm:text-2xl font-bold text-slate-800 mb-6">Salas e Semestres Gerenciados</h2>
            
            {minhasSalas.length === 0 ? (
              <div className="text-center py-12 bg-slate-50 rounded-lg border border-dashed border-slate-300">
                <p className="text-slate-500 mb-4">Você ainda não gerou nenhuma turma para este semestre.</p>
                <button onClick={() => setView("create")} className="text-blue-600 font-medium hover:underline">
                  Gerar sua primeira turma agora
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {minhasSalas.map(sala => (
                  <div key={sala.id} className="border border-slate-200 rounded-lg p-5 hover:shadow-md transition-shadow bg-white flex flex-col">
                    <div className="flex justify-between items-start mb-2">
                      <span className="bg-blue-100 text-blue-800 text-xs font-bold px-2 py-1 rounded">
                        Código: {sala.code}
                      </span>
                      <span className="text-xs text-slate-400">
                        {sala.createdAt ? new Date(sala.createdAt.toDate()).toLocaleDateString() : 'Recente'}
                      </span>
                    </div>
                    <h3 className="text-lg font-bold text-slate-800 mt-2">{sala.id_disciplina}</h3>
                    <p className="text-sm text-slate-500 flex-1">{sala.nome_disciplina}</p>
                    
                    <div className="mt-4 pt-4 border-t border-slate-100 flex flex-col gap-3">
                      {(sala.status === "gerando_aulas" || sala.status === "fatiando_ementa" || sala.status.startsWith("erro")) && (
                        <div className="flex flex-col gap-2">
                          <div className={`flex justify-between text-xs font-semibold ${sala.status.startsWith("erro") ? 'text-red-600' : 'text-blue-600'}`}>
                            <span>{sala.status === "fatiando_ementa" ? "Planejando Semestre..." : sala.status.startsWith("erro") ? "Erro na Geração" : "Gerando Aulas..."}</span>
                            {sala.status === "gerando_aulas" && <span>{sala.aulas_geradas || 0} / {sala.total_aulas || '?'}</span>}
                          </div>
                          {sala.status === "gerando_aulas" && (
                            <div className="w-full bg-slate-200 rounded-full h-2">
                              <div className="bg-blue-600 h-2 rounded-full transition-all duration-500" style={{ width: `${Math.min(100, ((sala.aulas_geradas || 0) / (sala.total_aulas || 1)) * 100)}%` }}></div>
                            </div>
                          )}
                          
                          </div>
                      )}
                      
                      {sala.status === "pronto" && (
                        <div className="p-2 bg-green-50 border border-green-200 rounded text-green-700 text-xs font-bold text-center">
                          ✅ Aulas criadas com sucesso!
                        </div>
                      )}

                      <div className="flex justify-between gap-2 mt-2">
                        <button 
                          onClick={() => router.push(`/professor/aula/${sala.id}`)}
                          className="flex-1 text-sm bg-slate-100 text-slate-700 py-2 rounded hover:bg-slate-200 transition font-medium"
                        >
                          📊 Acessar Sala
                        </button>
                        <button onClick={() => deleteClassroom(sala.id)} className="text-sm text-red-600 hover:text-red-800 px-2" title="Apagar Turma">
                          🗑️
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* View: Hub de Criação (Navega para Páginas Dedicadas) */}
        {view === "create" && (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8">
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Qual tipo de semestre deseja criar?</h2>
            <p className="text-slate-500 mb-8">Nossa plataforma oferece duas experiências diferentes de acordo com a sua necessidade.</p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Botão A: Inteligente */}
              <div 
                className="border border-slate-200 rounded-xl p-6 hover:border-blue-400 hover:shadow-md transition-all cursor-pointer group bg-slate-50 hover:bg-blue-50/30" 
                onClick={() => router.push("/professor/criar/inteligente")}
              >
                <div className="text-4xl mb-4">✨</div>
                <h3 className="font-bold text-slate-800 text-xl mb-2 group-hover:text-blue-600">Sala Inteligente</h3>
                <p className="text-sm text-slate-600 mb-4">A IA construirá todo o semestre utilizando estritamente a ementa e a bibliografia oficial cadastrada no sistema. Rápido e padronizado.</p>
                <span className="text-blue-600 font-bold text-sm">Criar Sala Inteligente →</span>
              </div>

              {/* Botão B: Personalizado */}
              <div 
                className="border border-slate-200 rounded-xl p-6 hover:border-blue-400 hover:shadow-md transition-all cursor-pointer group bg-slate-50 hover:bg-blue-50/30" 
                onClick={() => router.push("/professor/criar/personalizado")}
              >
                <div className="text-4xl mb-4">✏️</div>
                <h3 className="font-bold text-slate-800 text-xl mb-2 group-hover:text-blue-600">Crie do Seu Jeito</h3>
                <p className="text-sm text-slate-600 mb-4">Faça upload de seus próprios PDFs, escolha a quantidade exata de aulas, modifique o tom e guie a IA bloco a bloco (ou jogue tudo pra ela).</p>
                <span className="text-blue-600 font-bold text-sm">Criar Sala Personalizada →</span>
              </div>
            </div>
          </div>
        )}
      
      
</main>
    </div>
  );
}
