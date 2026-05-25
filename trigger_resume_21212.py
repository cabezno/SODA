import asyncio
import os
import sys
from pathlib import Path

# Configurar el path para que encuentre el kernel
root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir))

from kernel.orchestrator import SodaOrchestrator

async def main():
    print("--- Lanzando gatillo de reanudación para 21212 ---")
    orchestrator = SodaOrchestrator()
    # El ID del proyecto proporcionado por el usuario
    project_id = "21212"
    
    try:
        await orchestrator.resume(project_id)
        print(f"✅ Proceso de reanudación para {project_id} enviado al kernel.")
    except Exception as e:
        print(f"❌ Error al intentar reanudar: {e}")

if __name__ == "__main__":
    asyncio.run(main())
