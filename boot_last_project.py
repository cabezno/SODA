import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir))

from kernel.orchestrator import SodaOrchestrator

async def boot_last_project():
    project_id = "APLICACION"
    print(f"--- Iniciando arranque forzado del proyecto: {project_id} ---")
    
    orch = SodaOrchestrator()
    
    try:
        # Usamos retry_boot porque incluye la lógica de reparación y el nuevo auto-arranque de Docker
        project = await orch.retry_boot(project_id)
        
        if project and project.state.value == "done":
            print(f"\n[SUCCESS] El proyecto '{project_id}' ha arrancado correctamente.")
        else:
            state = project.state.value if project else "unknown"
            print(f"\n[FAILED] El proyecto quedó en estado: {state}")
            print("Revisá los logs en el workspace del proyecto para más detalles.")
            
    except Exception as e:
        print(f"\n[ERROR] Error durante el proceso de arranque: {e}")

if __name__ == "__main__":
    asyncio.run(boot_last_project())
