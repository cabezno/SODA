import asyncio
import sys
import json
from pathlib import Path
from kernel.orchestrator import SodaOrchestrator

# Forzar auto_confirm solo para la prueba (modificando el JSON, no el código)
config_path = Path("soda_config.json")
config_data = json.loads(config_path.read_text(encoding="utf-8"))
original_auto_confirm = config_data.get("auto_confirm")
config_data["auto_confirm"] = True
config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

async def test_soda_empirical():
    print(">>> INICIANDO TEST EMPIRICO DE SODA <<<")
    orchestrator = SodaOrchestrator()
    try:
        project = await orchestrator.run("Crea un script en Python que calcule el Indice de Masa Corporal (IMC). No uses librerias externas, solo pide peso y altura por consola y devuelve el resultado.", project_name="test_empirico_imc")
        print(f"\n>>> TEST FINALIZADO. ESTADO: {project.state.value} <<<")
    finally:
        # Restaurar config
        config_data["auto_confirm"] = original_auto_confirm
        config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

if __name__ == "__main__":
    asyncio.run(test_soda_empirical())
