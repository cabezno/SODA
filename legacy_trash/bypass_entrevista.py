import asyncio
import json
import os
from pathlib import Path
from kernel.orchestrator import SodaOrchestrator, ProjectState

async def auto_bypass():
    print("\n🚀 INICIANDO BYPASS DE ENTREVISTA...")
    project_id = "web_de_prueba"
    pending_file = Path(f"projects/{project_id}/.pending_question")
    metadata_file = Path(f"projects/{project_id}/metadata.json")
    
    # 1. Reset de metadatos forzado
    if metadata_file.exists():
        with open(metadata_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        meta["state"] = "idle"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        print("✅ Estado reseteado a IDLE.")

    # 2. Monitor agresivo de respuesta
    async def injector():
        print("📡 Esperando pregunta para inyectar respuesta...")
        for _ in range(100): # Intentamos durante 200 segundos
            if pending_file.exists():
                print("🤖 Pregunta detectada. Inyectando 'CARTA LIBRE'...")
                resp = {"answer": "PROCEED_CARTA_LIBRE", "timestamp": 0}
                with open(pending_file, "w", encoding="utf-8") as f:
                    json.dump(resp, f)
                print("✅ Inyección completada.")
                break
            await asyncio.sleep(2)

    # 3. Lanzar el orquestador
    orch = SodaOrchestrator()
    task = asyncio.create_task(injector())
    
    try:
        print("⚙️ Ejecutando reanudación de proyecto...")
        # En el orquestador actual, resume() llama a Layer 0 que bloquea esperando respuesta
        await orch.resume(project_id)
        print("✨ PIPELINE FINALIZADO.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(auto_bypass())
