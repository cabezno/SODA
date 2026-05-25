import asyncio
from kernel.orchestrator import SodaOrchestrator

async def main():
    print("Iniciando SODA Orchestrator con BlackBox activo...")
    orch = SodaOrchestrator()
    
    # Apuntamos al proyecto que reportaste con errores
    project_id = "APLICACION"
    print(f"Intentando reanudar el proyecto '{project_id}' con vigilancia forense...")
    
    try:
        project = await orch.resume(project_id)
        print(f"\n✅ Pipeline finalizado. Estado final: {project.state.value}")
    except Exception as e:
        print(f"\n❌ Error fatal detectado por el orquestador: {e}")

if __name__ == "__main__":
    asyncio.run(main())
