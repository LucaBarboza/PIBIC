import os
import json
import glob
from firebase_admin import firestore

class StorageManager:
    """
    Gerenciador híbrido de persistência local (JSON) e remota (Firebase Cloud Firestore).
    Recua automaticamente para armazenamento local em `data_local/` quando o Firestore estiver desabilitado ou indisponível.
    """
    def __init__(self, db=None, base_dir="data_local"):
        self.db = db
        self.base_dir = base_dir
        self.salas_dir = os.path.join(base_dir, "classrooms")
        os.makedirs(self.salas_dir, exist_ok=True)

    def _get_sala_file(self, sala_id: str) -> str:
        return os.path.join(self.salas_dir, f"{sala_id}.json")

    def _get_aulas_dir(self, sala_id: str) -> str:
        d = os.path.join(self.salas_dir, sala_id, "aulas")
        os.makedirs(d, exist_ok=True)
        return d

    def get_classroom(self, sala_id: str) -> dict:
        # Tenta Firebase se disponível
        if self.db:
            try:
                doc = self.db.collection("classrooms").document(sala_id).get()
                if doc.exists:
                    return doc.to_dict()
            except Exception as e:
                print(f"[STORAGE WARNING] Erro ao ler sala no Firebase ({e}), tentando armazenamento local...")

        # Fallback para armazenamento local em JSON
        fpath = self._get_sala_file(sala_id)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[STORAGE ERROR] Falha ao ler arquivo local da sala {sala_id}: {e}")
        return None

    def update_classroom(self, sala_id: str, data_update: dict) -> bool:
        # Tenta Firebase primeiro
        if self.db:
            try:
                self.db.collection("classrooms").document(sala_id).update(data_update)
            except Exception as e:
                print(f"[STORAGE WARNING] Erro ao atualizar sala no Firebase: {e}")

        # Atualiza localmente
        fpath = self._get_sala_file(sala_id)
        current = self.get_classroom(sala_id) or {"id": sala_id, "status": "criado"}
        current.update(data_update)
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[STORAGE ERROR] Falha ao salvar sala localmente: {e}")
            return False

    def save_aula(self, sala_id: str, numero_aula: int, aula_data: dict) -> bool:
        # Tenta Firebase
        if self.db:
            try:
                self.db.collection("classrooms").document(sala_id).collection("aulas").document(str(numero_aula)).set(aula_data)
                self.db.collection("classrooms").document(sala_id).update({
                    "aulas_geradas": firestore.Increment(1),
                    "status": "pronto",
                    "detalhe_progresso": "Aula concluída com sucesso!"
                })
            except Exception as e:
                print(f"[STORAGE WARNING] Erro ao salvar aula no Firebase: {e}")

        # Salva em arquivo local
        aulas_dir = self._get_aulas_dir(sala_id)
        fpath = os.path.join(aulas_dir, f"{numero_aula}.json")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(aula_data, f, ensure_ascii=False, indent=2)
            
            # Atualiza resumo das aulas geradas também na exportação local
            export_dir = os.path.join(self.base_dir, "aulas_geradas")
            os.makedirs(export_dir, exist_ok=True)
            export_file = os.path.join(export_dir, f"aula_{numero_aula}_{sala_id}.json")
            with open(export_file, "w", encoding="utf-8") as f:
                json.dump(aula_data, f, ensure_ascii=False, indent=2)
                
            print(f"[STORAGE LOCAL] Aula {numero_aula} salva e exportada com SUCESSO em: {export_file}")
            return True
        except Exception as e:
            print(f"[STORAGE ERROR] Falha ao salvar arquivo local da aula: {e}")
            return False

    def get_aulas(self, sala_id: str) -> list:
        # Tenta Firebase
        if self.db:
            try:
                docs = self.db.collection("classrooms").document(sala_id).collection("aulas").stream()
                aulas = [d.to_dict() for d in docs]
                if aulas:
                    return aulas
            except Exception as e:
                print(f"[STORAGE WARNING] Erro ao buscar aulas no Firebase: {e}")

        # Fallback local
        aulas_dir = self._get_aulas_dir(sala_id)
        aulas = []
        if os.path.exists(aulas_dir):
            for fpath in glob.glob(os.path.join(aulas_dir, "*.json")):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        aulas.append(json.load(f))
                except Exception:
                    pass
        return sorted(aulas, key=lambda x: x.get("numero_aula", 0))

    def get_disciplina(self, id_disciplina: str) -> dict:
        if self.db:
            try:
                doc = self.db.collection("disciplinas").document(id_disciplina).get()
                if doc.exists:
                    d = doc.to_dict()
                    if d.get("ementa_texto"):
                        return d
            except Exception as e:
                print(f"[STORAGE WARNING] Erro ao ler disciplina no Firebase: {e}")
        
        # Fallback local ementa TXT ou PDF
        base_ementa_dir = os.path.join(os.path.dirname(__file__), "ementas")
        txt_path = os.path.join(base_ementa_dir, f"{id_disciplina.lower()}.txt")
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                return {"id": id_disciplina, "nome": id_disciplina, "ementa_texto": f.read()}
                
        # Procurar PDF correspondente com IA multimodal
        if os.path.exists(base_ementa_dir):
            for fname in os.listdir(base_ementa_dir):
                if fname.lower().startswith(id_disciplina.lower()) and fname.endswith(".pdf"):
                    try:
                        import agente_extrator
                        pdf_path = os.path.join(base_ementa_dir, fname)
                        texto = agente_extrator.extrair_texto_base_pdf(pdf_path, tema_aula=f"Ementa {id_disciplina}")
                        if texto and texto.strip():
                            return {"id": id_disciplina, "nome": f"Disciplina {id_disciplina}", "ementa_texto": texto}
                    except Exception as e:
                        print(f"[STORAGE WARNING] Erro ao extrair PDF ementa com IA {fname}: {e}")
                        
        # Fallback padrao
        return {
            "id": id_disciplina,
            "nome": f"Disciplina {id_disciplina}",
            "ementa_texto": f"Ementa padrão da disciplina {id_disciplina}: Conceitos fundamentais, teoria geral, propriedades e aplicações práticas no ensino superior."
        }

storage_manager = StorageManager()
