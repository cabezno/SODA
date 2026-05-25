import asyncio
import os
import sys
from pathlib import Path
from kernel.orchestrator import SodaOrchestrator

async def main():
    print("🚀 SODA AUTONOMOUS STRESS TEST STARTING...")
    
    # We use a prompt that triggers 'Auto-Decision' to avoid blocking questions
    desc = (
        "PROYECTO DE PRUEBA AUTÓNOMA: Sistema de Gestión de Tareas (Task Manager) por CLI.\n"
        "REQUERIMIENTOS:\n"
        "1. Usar SQLite para persistencia local.\n"
        "2. Interfaz de comandos simple (add, list, delete).\n"
        "3. Lógica de 'Priorización Inteligente' que asigne prioridad basada en la fecha de vencimiento.\n"
        "4. Un módulo separado para el acceso a datos (Repository Pattern).\n"
        "REGLA: SODA DECIDE todos los detalles técnicos. Avanza inmediatamente sin preguntar."
    )
    
    project_id = "STRESS-TEST-AUTO"
    orch = SodaOrchestrator()
    
    # Clean previous test if exists
    proj_path = Path("projects") / project_id
    if proj_path.exists():
        import shutil
        print(f"Cleaning previous project {project_id}...")
        shutil.rmtree(proj_path)

    print(f"Running pipeline for {project_id}...")
    try:
        project = await orch.run(desc, project_name=project_id)
        
        print("\n" + "="*50)
        print(f"TEST RESULTS FOR {project_id}")
        print(f"Final State: {project.state.value}")
        
        source_dir = project.workspace / "source"
        files = list(source_dir.rglob("*.py"))
        print(f"Files Generated: {len(files)}")
        for f in files:
            print(f"  - {f.relative_to(source_dir)}")
            
        boot_report_path = project.workspace / "boot_report.json"
        if boot_report_path.exists():
            import json
            report = json.loads(boot_report_path.read_text(encoding="utf-8"))
            print(f"Boot Status: {'✅ OK' if report.get('final_ok') else '❌ FAILED'}")
            if not report.get('final_ok'):
                print(f"Reason: {report.get('reason')}")
        else:
            print("Boot Status: ⚠️ No report found.")
        
        print("="*50)
        
    except Exception as e:
        print(f"CRITICAL SYSTEM FAILURE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
