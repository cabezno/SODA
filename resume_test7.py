import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir))

from kernel.orchestrator import SodaOrchestrator

async def boot_test7():
    project_id = "test7"
    print(f"--- Intentando reanudar el proyecto: {project_id} ---")

    orch = SodaOrchestrator()

    try:
        # Intentamos reanudar
        await orch.resume(project_id)

    except Exception as e:
        print(f"\n[ERROR] Error durante el proceso: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(boot_test7())
