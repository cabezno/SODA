import asyncio
import os
import sys
from pathlib import Path

# Asegurar que el root del proyecto esté en el path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kernel.orchestrator import SodaOrchestrator

async def main():
    print("=== SODA: TRACKING DE REANUDACIÓN ===")
    orch = SodaOrchestrator()
    
    # Apuntamos al proyecto actual
    project_id = "prueba_1_v22"
    print(f"[*] Iniciando reanudación de '{project_id}'...")
    
    try:
        # El método resume ahora incluye el parche del BootAgent
        project = await orch.resume(project_id)
        
        print("\n=== RESULTADO FINAL ===")
        print(f"ID Proyecto: {project.id}")
        print(f"Estado Final: {project.state.value}")
        
        if project.state.value == "done":
            print("✅ ¡ÉXITO! El proyecto ha sido reparado, instalado y arrancado.")
        else:
            print("❌ El proyecto falló. Revisando reporte de boot...")
            report_path = project.workspace / "boot_report.json"
            if report_path.exists():
                import json
                report = json.loads(report_path.read_text(encoding="utf-8"))
                print(f"Razón del fallo: {report.get('reason')}")
                print(f"Últimos errores: {report.get('last_errors')}")

    except Exception as e:
        import traceback
        print(f"\n[!] Error crítico durante el tracking: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
