"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { auth, db } from "@/lib/firebase";
import { signInWithEmailAndPassword, createUserWithEmailAndPassword, onAuthStateChanged } from "firebase/auth";
import { doc, setDoc, getDoc } from "firebase/firestore";

export default function LoginPage() {
  const router = useRouter();
  const [statusMsg, setStatusMsg] = useState("Entrando automaticamente como Professor Teste...");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);

  const executarLogin = async () => {
    setErrorMsg(null);
    setStatusMsg("Conectando ao Firebase Auth...");
    try {
      await signInWithEmailAndPassword(auth, "professor@teste.com", "teste123");
      setStatusMsg("Autenticado! Redirecionando para o painel...");
    } catch (err: any) {
      console.warn("Aviso login inicial:", err.code, err.message);
      
      if (
        err.code === "auth/user-not-found" || 
        err.code === "auth/invalid-credential" || 
        err.code === "auth/invalid-login-credentials"
      ) {
        try {
          setStatusMsg("Criando conta de professor no Firebase...");
          const userCred = await createUserWithEmailAndPassword(auth, "professor@teste.com", "teste123");
          await setDoc(doc(db, "users", userCred.user.uid), {
            nome: "Professor Teste",
            email: "professor@teste.com",
            role: "professor",
            departamento: "Departamento de Estatística"
          });
          setStatusMsg("Conta criada! Redirecionando...");
        } catch (createErr: any) {
          console.error("Erro ao criar conta:", createErr);
          if (createErr.code === "auth/operation-not-allowed") {
            setErrorMsg("O provedor de 'E-mail/senha' ainda não foi ativado no Firebase Console.");
          } else {
            setErrorMsg(`Erro ao criar conta: ${createErr.message || createErr.code}`);
          }
        }
      } else if (err.code === "auth/operation-not-allowed") {
        setErrorMsg("O provedor de 'E-mail/senha' ainda não foi ativado no Firebase Console.");
      } else {
        setErrorMsg(`Erro de autenticação: ${err.message || err.code}`);
      }
    }
  };

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (user) {
        setStatusMsg("Carregando perfil do usuário...");
        try {
          const userDoc = await getDoc(doc(db, "users", user.uid));
          if (userDoc.exists() && userDoc.data().role === "aluno") {
            router.push("/aluno/dashboard");
          } else {
            router.push("/professor/dashboard");
          }
        } catch (docErr) {
          // Se falhar ao ler doc de user, redireciona para professor direto
          router.push("/professor/dashboard");
        }
      } else {
        executarLogin();
      }
    });

    return () => unsubscribe();
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 py-12 px-4 sm:px-6 lg:px-8 font-sans">
      <div className="max-w-md w-full p-8 bg-white rounded-2xl shadow-xl border border-slate-200 text-center">
        <div className="w-16 h-16 bg-blue-100 text-blue-700 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-4 font-black">
          UFBA
        </div>
        <h2 className="text-2xl font-black text-slate-900 mb-1">
          Plataforma de Aulas
        </h2>
        <p className="text-xs text-slate-500 mb-6">Ambiente de Ensino do Departamento de Estatística</p>

        {errorMsg ? (
          <div className="bg-red-50 border border-red-200 p-5 rounded-xl text-left mb-6">
            <div className="flex items-center gap-2 text-red-700 font-bold mb-2">
              <span>⚠️</span>
              <span>Atenção: Autenticação Pendente</span>
            </div>
            <p className="text-xs text-red-600 mb-3 leading-relaxed">
              {errorMsg}
            </p>
            {errorMsg.includes("E-mail/senha") && (
              <div className="bg-white p-3 rounded-lg border border-red-100 text-[11px] text-slate-700 space-y-1 mb-3">
                <p className="font-bold text-slate-800">Como resolver no Firebase Console (1 minuto):</p>
                <p>1. Vá em <strong>Authentication</strong> ➔ aba <strong>Sign-in method</strong></p>
                <p>2. Clique em <strong>E-mail/senha</strong> e marque <strong>Ativar (Enable)</strong></p>
                <p>3. Clique em <strong>Salvar</strong> e clique no botão abaixo para tentar novamente.</p>
              </div>
            )}
            <button
              onClick={() => {
                setIsRetrying(true);
                executarLogin().finally(() => setIsRetrying(false));
              }}
              disabled={isRetrying}
              className="w-full bg-red-600 hover:bg-red-700 text-white font-bold py-2.5 px-4 rounded-lg text-xs shadow transition"
            >
              {isRetrying ? "Tentando novamente..." : "🔄 Tentar Entrar Novamente"}
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center py-6">
            <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mb-4"></div>
            <p className="text-slate-700 font-bold text-sm">
              {statusMsg}
            </p>
            <p className="text-slate-400 text-xs mt-1">Conectando ao Firebase...</p>
          </div>
        )}
      </div>
    </div>
  );
}
