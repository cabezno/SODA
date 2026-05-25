import asyncio
import json
from kernel.orchestrator import SodaOrchestrator

async def test_v2_flow():
    orch = SodaOrchestrator()
    print("Iniciando test de flujo V2...")
    try:
        project = await orch.run("Crea una landing page simple para un restaurante con menu y contacto", interactive_mode=False)
        print(f"Test finalizado. Estado del proyecto: {project.state.value}")
    except Exception as e:
        print(f"Error en el test: {e}")

if __name__ == "__main__":
    asyncio.run(test_v2_flow())
