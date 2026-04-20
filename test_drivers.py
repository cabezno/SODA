import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from kernel.drivers.claude_driver import ClaudeDriver
from kernel.drivers.gemini_driver import GeminiDriver
from kernel.drivers.ollama_driver import OllamaDriver

SYSTEM = "Eres un agente de SODA. Responde en una sola frase corta."
PROMPT = "Confirma que estás activo y di qué modelo eres."


async def test_claude():
    driver = ClaudeDriver()
    result = await driver.prompt(SYSTEM, PROMPT)
    return ("claude", result)


async def test_ollama():
    driver = OllamaDriver(model_name="qwen2.5-coder:7b")
    result = await driver.prompt(SYSTEM, PROMPT)
    return ("ollama", result)


async def test_gemini():
    driver = GeminiDriver()
    result = await asyncio.to_thread(driver.prompt, SYSTEM, PROMPT)
    return ("gemini", result)


async def main():
    print("=" * 55)
    print("SODA — Test de Drivers (Fase A)")
    print("=" * 55)

    tasks = [test_claude(), test_ollama(), test_gemini()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    ok = 0
    for r in results:
        if isinstance(r, Exception):
            print(f"[✗] ERROR: {r}")
        else:
            driver_name, response = r
            status = "✓" if "Error" not in response else "✗"
            print(f"[{status}] {driver_name.upper()}: {response[:120]}")
            if status == "✓":
                ok += 1

    print("-" * 55)
    print(f"Resultado: {ok}/3 drivers respondieron correctamente.")
    if ok == 3:
        print("Fase A: COMPLETA ✓")
    else:
        print("Fase A: INCOMPLETA — revisar drivers con error.")


if __name__ == "__main__":
    asyncio.run(main())
