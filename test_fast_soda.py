import asyncio
import json
from pathlib import Path
from kernel.orchestrator import SodaOrchestrator

async def run_test():
    print("Iniciando prueba rápida de SODA (Auto-Confirm ON)...")
    
    # Activar auto_confirm temporalmente
    config_file = Path("soda_config.json")
    config_data = json.loads(config_file.read_text(encoding='utf-8'))
    config_data["auto_confirm"] = True
    config_data["tts_enabled"] = False # Desactivar TTS para que sea más rápido
    config_file.write_text(json.dumps(config_data, indent=2), encoding='utf-8')
    
    orchestrator = SodaOrchestrator()
    prompt = "Crea una landing page para un gimnasio en HTML y CSS. Sin backend, todo en una sola página. Importante: Agrega un archivo hero.png como background."
    
    try:
        project = await orchestrator.run(description=prompt, project_name="test_gimnasio_rapido")
        print(f"\n[RESULTADO] Prueba finalizada. Estado: {project.state.value}")
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
