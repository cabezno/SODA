import asyncio
import sys
from pathlib import Path
from kernel.orchestrator import SodaOrchestrator

async def main():
    if len(sys.argv) < 2:
        print("Uso: python reanudar.py <ID_DEL_PROYECTO>")
        return
        
    project_id = sys.argv[1]
    print(f"Iniciando SODA Orchestrator. Reanudando proyecto '{project_id}'...")
    
    orch = SodaOrchestrator()
    try:
        project = await orch.resume(project_id)
        print(f"\n✅ Pipeline finalizado. Estado final: {project.state.value}")
    except Exception as e:
        print(f"\n❌ Error fatal al reanudar: {e}")

if __name__ == "__main__":
    asyncio.run(main())
