"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Search, Check, BookOpen } from "lucide-react";

interface Disciplina {
  id_disciplina: string;
  nome: string;
  [key: string]: any;
}

interface DisciplinaSelectProps {
  disciplinas: Disciplina[];
  value: string;
  onChange: (id: string) => void;
  label?: string;
}

export default function DisciplinaSelect({
  disciplinas,
  value,
  onChange,
  label = "Disciplina da Grade Oficial"
}: DisciplinaSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const selected = disciplinas.find((d) => d.id_disciplina === value);

  const filteredDisciplinas = disciplinas.filter((d) => {
    const term = searchTerm.toLowerCase().trim();
    if (!term) return true;
    return (
      d.id_disciplina?.toLowerCase().includes(term) ||
      d.nome?.toLowerCase().includes(term)
    );
  });

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      searchInputRef.current.focus();
    } else {
      setSearchTerm("");
    }
  }, [isOpen]);

  const handleSelect = (id: string) => {
    onChange(id);
    setIsOpen(false);
  };

  return (
    <div className="relative mb-8" ref={containerRef}>
      {label && (
        <label className="block text-sm font-bold text-slate-700 mb-2">
          {label}
        </label>
      )}

      {/* Botão Gatilho do Dropdown */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full p-4 border rounded-xl bg-slate-50 flex items-center justify-between text-left transition-all shadow-sm ${
          isOpen
            ? "border-blue-500 ring-2 ring-blue-500/20 bg-white"
            : "border-slate-300 hover:border-slate-400"
        }`}
      >
        <div className="flex items-center gap-3 truncate">
          <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
            <BookOpen size={16} />
          </div>
          {selected ? (
            <div className="truncate">
              <span className="font-bold text-blue-900 mr-2 bg-blue-50 px-2 py-0.5 rounded border border-blue-200 text-xs">
                {selected.id_disciplina}
              </span>
              <span className="font-semibold text-slate-800 text-sm sm:text-base">
                {selected.nome}
              </span>
            </div>
          ) : (
            <span className="text-slate-400">Selecione uma disciplina...</span>
          )}
        </div>
        <ChevronDown
          size={20}
          className={`text-slate-500 transition-transform duration-200 shrink-0 ${
            isOpen ? "rotate-180 text-blue-600" : ""
          }`}
        />
      </button>

      {/* Menu Dropdown - SEMPRE ABERTO PARA BAIXO */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-slate-200 rounded-xl shadow-2xl z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150">
          {/* Barra de Pesquisa */}
          <div className="p-3 border-b border-slate-100 bg-slate-50/70 flex items-center gap-2">
            <Search size={16} className="text-slate-400 shrink-0 ml-1" />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Pesquisar por código (ex: MATD44) ou nome..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-transparent border-none outline-none text-sm text-slate-800 placeholder-slate-400 py-1"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm("")}
                className="text-xs text-slate-400 hover:text-slate-600 px-1.5 py-0.5 rounded bg-slate-200"
              >
                Limpar
              </button>
            )}
          </div>

          {/* Lista de Opções */}
          <div className="max-h-64 overflow-y-auto divide-y divide-slate-100">
            {filteredDisciplinas.length === 0 ? (
              <div className="p-6 text-center text-slate-400 text-sm">
                Nenhuma disciplina encontrada com "{searchTerm}".
              </div>
            ) : (
              filteredDisciplinas.map((d) => {
                const isSelected = d.id_disciplina === value;
                return (
                  <button
                    key={d.id_disciplina}
                    type="button"
                    onClick={() => handleSelect(d.id_disciplina)}
                    className={`w-full px-4 py-3 text-left flex items-center justify-between transition-colors ${
                      isSelected
                        ? "bg-blue-50/80 text-blue-900"
                        : "hover:bg-slate-50 text-slate-700"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 shrink-0">
                        {d.id_disciplina}
                      </span>
                      <span className={`text-sm truncate ${isSelected ? "font-bold text-blue-900" : "font-medium"}`}>
                        {d.nome}
                      </span>
                    </div>
                    {isSelected && (
                      <Check size={16} className="text-blue-600 shrink-0 ml-2" />
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
