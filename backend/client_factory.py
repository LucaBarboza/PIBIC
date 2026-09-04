import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def get_genai_client() -> genai.Client:
    api_key = os.environ.get('GEMINI_API_KEY')
    if api_key and api_key.strip():
        return genai.Client(api_key=api_key.strip())
    
    cred_file = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'vertex-key.json')
    if os.path.exists(cred_file):
        return genai.Client(vertexai=True, location='us-central1')
        
    return genai.Client()
