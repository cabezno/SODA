import asyncio
from kernel.orchestrator import SodaOrchestrator

async def run_test():
    print("Iniciando prueba End-to-End de SODA...")
    orchestrator = SodaOrchestrator()
    prompt = "Crea una página web estática (landing page) muy simple para una cafetería llamada 'El Grano Dorado'. Solo incluye index.html, styles.css y un app.js para un alert de bienvenida. Sin backend, diseño moderno, usa placeholders para imagenes."
    
    try:
        project = await orchestrator.run(description=prompt, project_name="test_cafeteria_web")
        print(f"\n[RESULTADO] Prueba finalizada. Estado: {project.state.value}")
    except Exception as e:
        print(f"\n[ERROR E2E] {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
