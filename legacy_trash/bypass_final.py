import asyncio
import json
from pathlib import Path
from kernel.orchestrator import SodaOrchestrator, ProjectState

async def auto_bypass():
    print("\n🚀 EJECUTANDO BYPASS DEFINITIVO...")
    project_id = "web_de_prueba"
    pending_file = Path(f"projects/{project_id}/.pending_question")
    
    # Pre-creamos el archivo de respuesta ANTES de que el orquestador lo pida
    print("🤖 Pre-inyectando respuesta CARTA LIBRE...")
    resp = {"answer": "PROCEED_CARTA_LIBRE", "timestamp": 0}
    with open(pending_file, "w", encoding="utf-8") as f:
        json.dump(resp, f)

    orch = SodaOrchestrator()
    
    try:
        print("⚙️ Lanzando Pipeline (Sin bloqueos)...")
        # resume() debería encontrar el archivo .pending_question ya respondido
        await orch.resume(project_id)
        print("\n✨ PIPELINE COMPLETADO EXITOSAMENTE.")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")

if __name__ == "__main__":
    asyncio.run(auto_bypass())
