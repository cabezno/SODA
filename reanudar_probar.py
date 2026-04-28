import asyncio
from kernel.orchestrator import SodaOrchestrator

async def main():
    print("Iniciando SODA Orchestrator con los nuevos cambios...")
    orch = SodaOrchestrator()
    
    project_id = "probar"
    print(f"Intentando reanudar el proyecto '{project_id}'...")
    
    try:
        project = await orch.resume(project_id, interactive_mode=False)
        print(f"\n✅ Prueba finalizada. Estado actual del proyecto: {project.state.value}")
    except Exception as e:
        print(f"\n❌ Error durante la ejecución: {e}")

if __name__ == "__main__":
    asyncio.run(main())
