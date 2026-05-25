import requests
import json

def test_ollama_txt_output():
    url = "http://localhost:11434/api/chat"
    
    # Prompt sugerido por el usuario
    system_prompt = "Eres un programador senior. Responde de forma analítica."
    user_prompt = "Escribe una función en Python para calcular el área de un círculo. ¿Me puedes poner el código que te pedí dentro de un archivo .txt?"
    
    payload = {
        "model": "qwen2.5-coder:14b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False
    }
    
    print(f"Enviando solicitud a Ollama (qwen2.5-coder:14b)...")
    try:
        response = requests.post(url, json=payload, timeout=180)
        if response.status_code == 200:
            content = response.json().get("message", {}).get("content", "")
            print("\n--- RESPUESTA CRUDA DE OLLAMA ---")
            print(content)
            print("--- FIN DE RESPUESTA ---")
        else:
            print(f"Error de Ollama: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error de conexión: {e}")

if __name__ == "__main__":
    test_ollama_txt_output()
