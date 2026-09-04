"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { auth, db } from "@/lib/firebase";
import { signOut, onAuthStateChanged } from "firebase/auth";
import { collection, query, where, getDocs, doc, getDoc, addDoc, serverTimestamp } from "firebase/firestore";

export default function AlunoDashboard() {
  const router = useRouter();
  
  // Perfil
  const [alunoName, setAlunoName] = useState("Aluno(a)");
  const [alunoCurso, setAlunoCurso] = useState("Graduação - UFBA");

  // Views
  const [view, setView] = useState<"turmas" | "entrar" | "fluxograma">("turmas");
  
  // Estado Turmas
  const [minhasTurmas, setMinhasTurmas] = useState<any[]>([]);
  const [loadingTurmas, setLoadingTurmas] = useState(true);

  // Estado Entrar Sala
  const [code, setCode] = useState("");
  const [loadingJoin, setLoadingJoin] = useState(false);
  const [errorJoin, setErrorJoin] = useState("");

  useEffect(() => {
    async function loadData() {
      try {
        if (auth.currentUser) {
          const userDoc = await getDoc(doc(db, "users", auth.currentUser.uid));
          if (userDoc.exists()) {
            setAlunoName(userDoc.data().nome || "Aluno(a)");
            setAlunoCurso(userDoc.data().curso || "Graduação - UFBA");
          }
        }

        // Buscar salas diretamente para livre acesso
        const snapshot = await getDocs(collection(db, "classrooms"));
        const turmas = snapshot.docs.map(d => ({ id: d.id, ...d.data() }));
        setMinhasTurmas(turmas);
      } catch (err) {
        console.error("Erro ao carregar dados do aluno:", err);
      } finally {
        setLoadingTurmas(false);
      }
    }
    loadData();
  }, [view]);

  const handleLogout = async () => {
    try {
      await signOut(auth);
    } catch(e) {}
    router.push("/");
  };

  const joinClass = async (e: React.FormEvent) => {
    e.preventDefault();
    if (code.length !== 4) {
      setErrorJoin("O código deve ter exatamente 4 dígitos.");
      return;
    }
    
    setLoadingJoin(true);
    setErrorJoin("");

    try {
      // 1. Acha a turma
      const q = query(collection(db, "classrooms"), where("code", "==", code));
      const snapshot = await getDocs(q);

      if (snapshot.empty) {
        setErrorJoin("Sala não encontrada. Verifique o código com o professor.");
        setLoadingJoin(false);
        return;
      }

      const classId = snapshot.docs[0].id;

      // 2. Verifica se já está matriculado
      const studentId = auth.currentUser?.uid || "aluno_guest";

      const qCheck = query(
        collection(db, "enrollments"), 
        where("studentId", "==", studentId),
        where("classroomId", "==", classId)
      );
      const checkSnap = await getDocs(qCheck);
      
      if (!checkSnap.empty) {
        alert("Você já está matriculado nesta turma!");
        setView("turmas");
        setCode("");
        return;
      }

      // 3. Cria a matricula
      await addDoc(collection(db, "enrollments"), {
        studentId: studentId,
        classroomId: classId,
        joinedAt: serverTimestamp()
      });

      alert("Matrícula realizada com sucesso!");
      setCode("");
      setView("turmas");

    } catch (err) {
      console.error(err);
      setErrorJoin("Erro ao se conectar com a sala.");
    } finally {
      setLoadingJoin(false);
    }
  };

  if (loadingTurmas) {
    return <div className="min-h-screen flex items-center justify-center text-slate-500">Carregando painel do aluno...</div>;
  }

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      <nav className="bg-blue-900 text-white px-4 sm:px-6 py-3 sm:py-4 flex justify-between items-center shadow-md">
        <div className="truncate pr-2">
          <h1 className="text-lg sm:text-xl font-bold truncate">Portal do Aluno</h1>
          <p className="text-[10px] sm:text-xs text-blue-200 truncate">{alunoName} | {alunoCurso}</p>
        </div>
        <button onClick={handleLogout} className="text-xs sm:text-sm bg-blue-800 px-3 py-1.5 sm:px-4 sm:py-2 rounded hover:bg-blue-700 transition shrink-0">Sair</button>
      </nav>

      <main className="max-w-5xl mx-auto mt-4 sm:mt-8 p-4 sm:p-6">
        {/* Nav Tabs */}
        <div className="flex gap-2 sm:gap-4 mb-6 sm:mb-8 overflow-x-auto pb-2">
          <button 
            onClick={() => setView("turmas")}
            className={`px-4 sm:px-6 py-2 rounded-full text-xs sm:text-sm whitespace-nowrap font-medium transition ${view === "turmas" ? "bg-blue-600 text-white" : "bg-white text-slate-600 border border-slate-300"}`}
          >
            📚 Minhas Turmas
          </button>
          <button 
            onClick={() => setView("entrar")}
            className={`px-4 sm:px-6 py-2 rounded-full text-xs sm:text-sm whitespace-nowrap font-medium transition ${view === "entrar" ? "bg-blue-600 text-white" : "bg-white text-slate-600 border border-slate-300"}`}
          >
            ➕ Entrar em Turma
          </button>
          <button 
            onClick={() => setView("fluxograma")}
            className={`px-4 sm:px-6 py-2 rounded-full text-xs sm:text-sm whitespace-nowrap font-medium transition ${view === "fluxograma" ? "bg-blue-600 text-white" : "bg-white text-slate-600 border border-slate-300"}`}
          >
            🗺️ Fluxograma do Curso
          </button>
        </div>

        {/* View: Minhas Turmas */}
        {view === "turmas" && (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 sm:p-6 md:p-8">
            <h2 className="text-xl sm:text-2xl font-bold text-slate-800 mb-6">Salas Matriculadas</h2>
            
            {minhasTurmas.length === 0 ? (
              <div className="text-center py-12 bg-slate-50 rounded-lg border border-dashed border-slate-300">
                <p className="text-slate-500 mb-4">Você ainda não está em nenhuma turma neste semestre.</p>
                <button onClick={() => setView("entrar")} className="text-blue-600 font-medium hover:underline">
                  Utilizar um código de convite
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {minhasTurmas.map(turma => (
                  <div key={turma.id} className="border border-slate-200 rounded-lg p-5 hover:shadow-md transition-shadow bg-white flex flex-col cursor-pointer" onClick={() => router.push(`/aluno/aula/${turma.id}`)}>
                    <div className="flex justify-between items-start mb-2">
                      <span className="bg-green-100 text-green-800 text-xs font-bold px-2 py-1 rounded">
                        Ativa
                      </span>
                    </div>
                    <h3 className="text-lg font-bold text-slate-800 mt-2">{turma.id_disciplina}</h3>
                    <p className="text-sm text-slate-500 flex-1">{turma.nome_disciplina}</p>
                    
                    <div className="mt-4 pt-4 border-t border-slate-100">
                      <div className="text-sm text-blue-600 font-medium flex items-center justify-center gap-2">
                        Acessar Sala ➔
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* View: Entrar Sala */}
        {view === "entrar" && (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 flex flex-col items-center">
             <div className="text-6xl mb-6 mt-4">🎓</div>
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Código de Convite</h2>
            <p className="text-slate-500 mb-8 text-center max-w-sm">Digite o código de 4 dígitos fornecido pelo seu professor para se matricular na disciplina.</p>

            {errorJoin && <p className="text-red-500 text-sm mb-4 bg-red-50 p-3 rounded w-full max-w-xs text-center">{errorJoin}</p>}

            <form onSubmit={joinClass} className="w-full max-w-xs flex flex-col gap-4">
              <input
                type="text"
                maxLength={4}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                placeholder="0000"
                className="w-full text-center text-5xl font-mono font-bold tracking-[0.3em] py-4 border-2 border-slate-300 rounded-xl focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100 transition-all text-slate-700"
              />
              <button
                type="submit"
                disabled={loadingJoin}
                className="w-full py-4 bg-blue-600 text-white text-lg font-bold rounded-xl hover:bg-blue-700 transition shadow-sm disabled:opacity-50"
              >
                {loadingJoin ? "Validando..." : "Matricular-se"}
              </button>
            </form>
          </div>
        )}

        {/* View: Fluxograma */}
        {view === "fluxograma" && (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8">
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Fluxograma: {alunoCurso}</h2>
            <p className="text-slate-500 mb-8">Visualize sua progressão no curso (Recurso Prototípico).</p>
            
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-10 flex flex-col items-center justify-center text-slate-400">
               <div className="text-5xl mb-4">🗺️</div>
               <p className="max-w-md text-center">Esta área exibirá a árvore de pré-requisitos do seu curso e conectará as matérias com suas respectivas salas na plataforma.</p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
