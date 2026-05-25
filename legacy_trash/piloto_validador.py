import asyncio
import json
import os
import sys
from pathlib import Path
from kernel.orchestrator import SodaOrchestrator, ProjectState

async def autonomous_validation():
    print("\n🚀 INICIANDO AUTOPILOTO DE VALIDACIÓN SODA...")
    orch = SodaOrchestrator()
    project_id = "web_de_prueba"
    
    # Aseguramos un entorno limpio para el test
    print("🧹 Limpiando residuos de intentos previos...")
    pending_file = Path(f"projects/{project_id}/.pending_question")
    if pending_file.exists(): pending_file.unlink()
    
    # Cargamos el proyecto
    print(f"📂 Cargando proyecto '{project_id}'...")
    project = await orch.resume(project_id)
    
    # Simulamos la interacción del usuario para saltar la entrevista si está bloqueada
    # En SODA V2, si el WisdomAgent pregunta, respondemos con 'Carta Libre'
    async def auto_respond():
        while project.state != ProjectState.DONE:
            if pending_file.exists():
                print("🤖 Intervención: Detectada pregunta de la IA. Respondiendo con 'CARTA LIBRE'...")
                try:
                    with open(pending_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    # Sobrescribimos con la respuesta para que el Gateway la capture
                    response_data = {"answer": "SODA tiene CARTA LIBRE total. Define todos los detalles técnicos y de negocio según tu criterio profesional. Procede al desarrollo inmediato.", "timestamp": 0}
                    with open(pending_file, "w", encoding="utf-8") as f:
                        json.dump(response_data, f)
                    print("✅ Respuesta inyectada.")
                except Exception as e:
                    print(f"⚠️ Error inyectando respuesta: {e}")
            await asyncio.sleep(2)

    # Lanzamos el monitor de respuestas en segundo plano
    responder_task = asyncio.create_task(auto_respond())
    
    print("⚙️ Ejecutando Pipeline recursivo...")
    try:
        # Forzamos la ejecución
        await orch.resume(project_id)
        print(f"\n✨ PROYECTO FINALIZADO CON ÉXITO. Estado: {project.state}")
    except Exception as e:
        print(f"\n❌ FALLO EN EL PIPELINE: {e}")
    finally:
        responder_task.cancel()

if __name__ == "__main__":
    asyncio.run(autonomous_validation())
