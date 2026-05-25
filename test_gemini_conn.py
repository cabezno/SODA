import asyncio
import os
from kernel.drivers.gemini_driver import GeminiDriver

async def test_conn():
    print("--- Probando conexión con Gemini ---")
    driver = GeminiDriver()
    if not driver.api_keys:
        print("❌ No se encontraron API Keys en el entorno.")
        return

    try:
        # Dejamos que el driver use su lista por defecto
        print("Intentando llamada general (el driver probará todos sus modelos)...")
        resp = await driver.call(
            system_prompt="Eres un tester.",
            user_message="Hola, ¿estás operativo? Responde solo con 'OPERATIVO'"
        )
        print(f"\n--- REPORTE FINAL ---")
        print(f"Modelo que respondió: {resp.model_used}")
        print(f"Contenido: {resp.content}")
        
        if "OPERATIVO" in resp.content.upper():
            print("✅ Gemini está FUNCIONANDO.")
        else:
            print(f"❌ Fallo en la respuesta. Contenido: {resp.content}")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")

if __name__ == "__main__":
    asyncio.run(test_conn())
