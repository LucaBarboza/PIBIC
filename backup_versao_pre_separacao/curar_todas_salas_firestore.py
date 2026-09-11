import os
import sys
import json
import time

sys.stdout.reconfigure(encoding='utf-8')

from main import db
from agente_validador_latex import validar_e_corrigir_aula_completa, compilar_katex_real
from storage import StorageManager

storage = StorageManager(db=db, base_dir="data_local")

def curar_todas_as_salas():
    if not db:
        print("[ERRO] Firebase DB não disponível.")
        return

    print("=== INICIANDO VARREDURA E AUTOCURA DE SALAS NO FIRESTORE ===")
    docs = list(db.collection("classrooms").stream())
    print(f"Total de salas encontradas: {len(docs)}")

    total_curadas = 0
    total_erros_resolvidos = 0

    for d in docs:
        sala_id = d.id
        nome_disc = d.to_dict().get("nome_disciplina", "Sem Nome")
        aulas_ref = list(db.collection("classrooms").document(sala_id).collection("aulas").stream())

        for a in aulas_ref:
            num_aula = a.id
            aula_data = a.to_dict()

            # Sempre aplica sanitização determinística nos simuladores (< 1ms)
            alterado = False
            sims = aula_data.get("simuladores_da_aula")
            if sims is None and "conteudo_json" in aula_data:
                sims = aula_data["conteudo_json"].get("simuladores_da_aula")
            if isinstance(sims, list):
                from agente_validador_latex import sanitizar_layout_e_renderizacao_simulador
                for s in sims:
                    if isinstance(s, dict) and "codigo_html_gerado" in s:
                        html_antigo = s["codigo_html_gerado"]
                        html_novo = sanitizar_layout_e_renderizacao_simulador(html_antigo)
                        if html_antigo != html_novo:
                            s["codigo_html_gerado"] = html_novo
                            alterado = True

            res_antes = compilar_katex_real(aula_data)
            erros_antes = res_antes.get("total_erros", 0)

            if erros_antes > 0 or alterado:
                print(f"\n[ATUALIZANDO SALA] {sala_id} - Aula {num_aula} ({nome_disc}): {erros_antes} falhas KaTeX, alterado={alterado}")
                aula_curada = validar_e_corrigir_aula_completa(aula_data)
                res_depois = compilar_katex_real(aula_curada)
                erros_depois = res_depois.get("total_erros", 0)

                print(f"   -> Resultado da Auto-Cura: {erros_antes} erros -> {erros_depois} erros.")

                # Atualiza no Firestore e local
                db.collection("classrooms").document(sala_id).collection("aulas").document(str(num_aula)).set(aula_curada)
                storage.save_aula(sala_id, int(num_aula) if num_aula.isdigit() else 1, aula_curada)
                print(f"   [OK] Sala {sala_id} atualizada com sucesso no Firestore e Local!")

                total_curadas += 1
                total_erros_resolvidos += max(0, erros_antes - erros_depois)
            else:
                print(f"[OK - JA APROVADA] {sala_id} - Aula {num_aula} ({nome_disc}): 100% válida ({res_antes.get('total_formulas', 0)} fórmulas)")

    print(f"\n=== PROCESSO CONCLUÍDO ===")
    print(f"Total de aulas curadas: {total_curadas}")
    print(f"Total de anomalias eliminadas: {total_erros_resolvidos}")

if __name__ == "__main__":
    curar_todas_as_salas()
