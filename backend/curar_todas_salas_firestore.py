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

            res_antes = compilar_katex_real(aula_data)
            erros_antes = res_antes.get("total_erros", 0)

            if erros_antes > 0:
                print(f"\n[SALA COM FALHAS] {sala_id} - Aula {num_aula} ({nome_disc}): {erros_antes} falhas KaTeX")
                aula_curada = validar_e_corrigir_aula_completa(aula_data)
                res_depois = compilar_katex_real(aula_curada)
                erros_depois = res_depois.get("total_erros", 0)

                print(f"   -> Resultado da Auto-Cura: {erros_antes} erros -> {erros_depois} erros.")

                # Atualiza no Firestore e local
                db.collection("classrooms").document(sala_id).collection("aulas").document(str(num_aula)).set(aula_curada)
                storage.save_aula(sala_id, int(num_aula) if num_aula.isdigit() else 1, aula_curada)
                print(f"   [OK] Sala {sala_id} atualizada com sucesso no Firestore e Local!")

                total_curadas += 1
                total_erros_resolvidos += (erros_antes - erros_depois)
            else:
                print(f"[OK - JA APROVADA] {sala_id} - Aula {num_aula} ({nome_disc}): 100% válida ({res_antes.get('total_formulas', 0)} fórmulas)")

    print(f"\n=== PROCESSO CONCLUÍDO ===")
    print(f"Total de aulas curadas: {total_curadas}")
    print(f"Total de anomalias eliminadas: {total_erros_resolvidos}")

if __name__ == "__main__":
    curar_todas_as_salas()
