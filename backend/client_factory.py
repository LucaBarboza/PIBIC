import os
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()

class ModelsProxy:
    def __init__(self, manager):
        self._manager = manager

    def generate_content(self, *args, **kwargs):
        client = self._manager.get_active_client()
        return client.models.generate_content(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._manager.get_active_client().models, name)

class MultiKeyClient:
    def __init__(self):
        load_dotenv()
        self.free_key = (os.environ.get("GEMINI_FREE_API_KEY") or "").strip()
        self.paid_key = (os.environ.get("GEMINI_PAID_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
        
        self.client_free = genai.Client(api_key=self.free_key) if self.free_key else None
        self.client_paid = genai.Client(api_key=self.paid_key) if self.paid_key else None
        
        # Fallback para Vertex se não houver chaves de API
        if not self.client_free and not self.client_paid:
            cred_file = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'vertex-key.json')
            if os.path.exists(cred_file):
                self.client_paid = genai.Client(vertexai=True, location='us-central1')

        self.active_tier = "free" if self.client_free else "paid"
        self.consecutive_503_count = 0
        self.free_exhausted_until = 0.0
        self.models = ModelsProxy(self)
        
        print(f"[MultiKeyClient] Inicializado com Sucesso. Tier Inicial: {self.active_tier.upper()} (Free Key: {'Configurada' if self.client_free else 'Ausente'} | Paid Key: {'Configurada' if self.client_paid else 'Ausente'})")

    def get_active_tier(self) -> str:
        if self.active_tier == "free" and time.time() < self.free_exhausted_until:
            return "paid" if self.client_paid else "free"
        return self.active_tier

    def get_active_client(self) -> genai.Client:
        tier = self.get_active_tier()
        if tier == "free" and self.client_free:
            return self.client_free
        if self.client_paid:
            return self.client_paid
        if self.client_free:
            return self.client_free
        return genai.Client()

    def is_paid_available(self) -> bool:
        return self.client_paid is not None

    def is_free_available(self) -> bool:
        return self.client_free is not None

    def switch_to_paid(self, reason: str = ""):
        if self.client_paid:
            print(f"[MultiKeyClient -> FAILOVER] Chaveando para CHAVE PAGA (Fallback). Motivo: {reason}")
            self.active_tier = "paid"
            self.consecutive_503_count = 0
        else:
            print(f"[MultiKeyClient -> AVISO] Falha ao chavear: GEMINI_PAID_API_KEY nao configurada!")

    def mark_free_exhausted(self, duration_seconds: float = 3600, reason: str = ""):
        print(f"[MultiKeyClient -> COTA] Chave Gratuita em pausa por {int(duration_seconds)}s. Motivo: {reason}")
        self.free_exhausted_until = time.time() + duration_seconds
        self.switch_to_paid(reason)

    def reset_to_free(self):
        if self.client_free:
            print("[MultiKeyClient] Resetando tier ativo para CHAVE GRATUITA.")
            self.active_tier = "free"
            self.free_exhausted_until = 0.0
            self.consecutive_503_count = 0

    def __getattr__(self, name):
        return getattr(self.get_active_client(), name)

_singleton_client = None

def get_genai_client() -> MultiKeyClient:
    global _singleton_client
    if _singleton_client is None:
        _singleton_client = MultiKeyClient()
    return _singleton_client

