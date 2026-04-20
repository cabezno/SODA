import ollama # La librería de python que instalaste
import os
import asyncio

class OllamaDriver:
    def __init__(self, model_name="qwen2.5-coder:14b"): 
        # Usamos la IP local directamente para saltar problemas de PATH
        self.host = "http://127.0.0.1:11434"
        self.model = model_name

    async def prompt(self, system: str, user: str):
        client = ollama.AsyncClient(host=self.host)
        try:
            response = await client.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user},
                ]
            )
            return response['message']['content']
        except Exception as e:
            return f"Error: No se pudo conectar con Ollama en {self.host}. {str(e)}"

# Script de prueba rápida
async def test():
    driver = OllamaDriver()
    print("--- Testeando Qwen via Kernel Driver ---")
    res = await driver.prompt("Eres SODA v3", "Hola, confirma que estás activo.")
    print(res)

if __name__ == "__main__":
    asyncio.run(test())