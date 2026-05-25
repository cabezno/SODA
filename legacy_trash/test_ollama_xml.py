import requests
import json
import re

def test_ollama_xml_tag():
    url = "http://localhost:11434/api/chat"
    
    # Prompt estricto de ingeniería (Etiquetas XML)
    system_prompt = """Eres la Capa 4 de SODA: Un Programador Experto.
REGLA CRÍTICA:
Puedes pensar y razonar paso a paso tu solución en texto normal.
Sin embargo, el código final que implementes DEBE estar encapsulado EXCLUSIVAMENTE dentro de las etiquetas <CODE> y </CODE>.
NO utilices bloques de código Markdown (```python). Utiliza únicamente las etiquetas XML.
Ejemplo de salida correcta:
Mi razonamiento aquí...
<CODE>
print("hola")
</CODE>
Espero te sirva.
"""
    user_prompt = "Escribe una función en Python que conecte a una base de datos SQLite y cree una tabla 'usuarios'. Explícame por qué eliges ciertos tipos de datos."
    
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
            print("\n--- 1. RESPUESTA CRUDA DE QWEN ---")
            print(content)
            
            print("\n--- 2. SIMULACIÓN DE EXTRACCIÓN SODA (Python) ---")
            # Extraer el contenido entre las etiquetas <CODE>
            match = re.search(r'<CODE>(.*?)</CODE>', content, re.DOTALL | re.IGNORECASE)
            if match:
                extracted_code = match.group(1).strip()
                print("¡EXTRACCIÓN EXITOSA! El código limpio es:")
                print("------------------------------------------")
                print(extracted_code)
                print("------------------------------------------")
            else:
                print("FALLO: No se encontraron las etiquetas <CODE>.")
        else:
            print(f"Error de Ollama: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error de conexión: {e}")

if __name__ == "__main__":
    test_ollama_xml_tag()
