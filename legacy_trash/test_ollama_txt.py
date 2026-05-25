import requests
import json
import re

def test_ollama_txt_download():
    url = "http://localhost:11434/api/chat"
    
    # Prompt del usuario: Archivo de texto + Extractor
    system_prompt = "Eres un programador experto."
    user_prompt = "Escribe una clase en Python para calcular el área y perímetro de un rectángulo. Explica brevemente cómo usarla. ¿Me puedes poner el código que te pedí dentro de un archivo .txt para descargar?"
    
    payload = {
        "model": "qwen2.5-coder:7b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False
    }
    
    print(f"Enviando solicitud a Ollama (qwen2.5-coder:7b)...")
    try:
        response = requests.post(url, json=payload, timeout=180)
        if response.status_code == 200:
            content = response.json().get("message", {}).get("content", "")
            print("\n--- RESPUESTA CRUDA DE QWEN 7B ---")
            print(content)
            
            print("\n--- SIMULACIÓN DE EXTRACCIÓN SODA (Extractor Python) ---")
            # En base a las pruebas anteriores, cuando le pedimos un archivo, Qwen usa Markdown. 
            # Así que el script Python buscará el bloque de código más grande.
            blocks = re.findall(r'```[a-zA-Z0-9\+\-]*\s*\n?(.*?)```', content, re.DOTALL | re.IGNORECASE)
            
            if blocks:
                extracted_code = max(blocks, key=len).strip()
                print("¡EXTRACCIÓN EXITOSA! El código limpio es:")
                print("------------------------------------------")
                print(extracted_code)
                print("------------------------------------------")
            else:
                print("FALLO: No se encontraron bloques de código para extraer.")
        else:
            print(f"Error de Ollama: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error de conexión: {e}")

if __name__ == "__main__":
    test_ollama_txt_download()
