import asyncio
import os
from pathlib import Path
from kernel.drivers.gemini_driver import GeminiDriver

async def test_specific_models():
    driver = GeminiDriver()
    models_to_test = [
        "gemini-3.1-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash"
    ]
    
    print("--- PRUEBA DE CONEXIÓN GEMINI NEXT-GEN ---")
    for model in models_to_test:
        print(f"Probando modelo: {model}...")
        try:
            # Forzamos el modelo en la llamada
            resp = await driver.call(
                system_prompt="Eres un tester.",
                user_message="Responde solo con la palabra 'OK' si recibes esto.",
                model=model,
                max_tokens=10
            )
            print(f"  ↳ Resultado: {resp.content}")
        except Exception as e:
            print(f"  ↳ Error: {e}")
    print("------------------------------------------")

if __name__ == "__main__":
    asyncio.run(test_specific_models())
