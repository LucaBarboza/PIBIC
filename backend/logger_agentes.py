from firebase_admin import firestore
import datetime

class AgentLogger:
    def __init__(self, db, sala_id, numero_aula):
        self.db = db
        self.sala_id = sala_id
        self.numero_aula = numero_aula
        self.doc_ref = None
        
        if self.db:
            try:
                self.doc_ref = self.db.collection("classrooms").document(self.sala_id).collection("aulas_debug").document(str(self.numero_aula))
                self.doc_ref.set({
                    "logs": [],
                    "agentes": {
                        "gerador_bruto": {"status": "esperando", "prompt": "", "resposta": ""},
                        "orquestrador": {"status": "esperando", "prompt": "", "resposta": "", "loops": []},
                        "revisor": {"status": "esperando", "prompt_base": "", "loops": []},
                        "exercicios": {"status": "esperando", "prompt": "", "resposta": ""},
                        "simulador": {"status": "esperando", "prompt": "", "resposta": ""},
                        "validador_latex": {"status": "esperando", "prompt": "", "resposta": ""}
                    }
                })
            except Exception as e:
                print(f"[LOGGER WARNING] Falha ao inicializar logger no Firestore: {e}")
                self.doc_ref = None

    def init_subtopics(self, count):
        if not self.doc_ref:
            return
        try:
            updates = {"num_subtopics": count}
            for i in range(1, count + 1):
                updates[f"agentes.gerador_bruto_{i}"] = {"status": "esperando", "prompt": "", "resposta": ""}
                updates[f"agentes.revisor_{i}"] = {"status": "esperando", "prompt": "", "resposta": ""}
            self.doc_ref.update(updates)
        except Exception as e:
            print(f"[LOGGER WARNING] Falha em init_subtopics: {e}")

    def log(self, message, msg_type="info"):
        """Adiciona um log na lista de logs da interface do debugger."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{msg_type.upper()}] {message}")
        
        if self.doc_ref:
            try:
                self.doc_ref.update({
                    "logs": firestore.ArrayUnion([{
                        "time": timestamp,
                        "msg": message,
                        "type": msg_type
                    }])
                })
            except Exception:
                pass

    def update_agent(self, agent_name, status, prompt=None, resposta=None, loop_data=None):
        """
        Atualiza o estado de um agente.
        status: "esperando", "rodando", "concluido", "erro"
        """
        if not self.doc_ref:
            return
        try:
            updates = {
                f"agentes.{agent_name}.status": status
            }
            if prompt is not None:
                updates[f"agentes.{agent_name}.prompt"] = prompt
            if resposta is not None:
                updates[f"agentes.{agent_name}.resposta"] = resposta
                
            self.doc_ref.update(updates)
            
            if loop_data is not None:
                self.doc_ref.update({
                    f"agentes.{agent_name}.loops": firestore.ArrayUnion([loop_data])
                })
        except Exception:
            pass
