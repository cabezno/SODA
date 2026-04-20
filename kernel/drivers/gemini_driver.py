import os
import requests
import json
from dotenv import load_dotenv
from pathlib import Path

class GeminiDriver:
    def __init__(self):
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        load_dotenv(env_path)
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        # Usamos versiones "frozen" de 2026 y finales de 2025
        # Estos IDs son mucho más estables que los alias dinámicos
        self.candidate_models = [
           
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-3.0-pro",
            "gemini-3.0-flash",
            "gemini-2.0-pro",
            "gemini-2.0-flash"
        ]
        self.active_model = None

    def prompt(self, system: str, user: str):
        if not self.active_model:
            # Intentamos encontrar cuál de los IDs estáticos acepta tu proyecto
            for model in self.candidate_models:
                print(f"[DEBUG] Testeando modelo estático: {model}...")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
                try:
                    res = requests.post(url, json={"contents": [{"parts": [{"text": "hi"}]}]}, timeout=15)
                    if res.status_code == 200:
                        self.active_model = model
                        print(f"[✓] ÉXITO: Usando {model}")
                        break
                except:
                    continue
            
            if not self.active_model:
                return "Error: Ningún modelo estático (002, base) respondió. Revisa permisos de API."

        # Petición real con el modelo encontrado
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.active_model}:generateContent?key={self.api_key}"
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{"parts": [{"text": f"SYSTEM: {system}\n\nUSER: {user}"}]}]
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            res_json = response.json()
            return res_json['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            return f"Error crítico: {str(e)}"