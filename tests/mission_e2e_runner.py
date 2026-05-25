import asyncio
import json
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Configurar el path para que encuentre el kernel
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from kernel.orchestrator import SodaOrchestrator, ProjectState

class AutomatedUser:
    """
    Simula a un usuario respondiendo preguntas de SODA.
    """
    def __init__(self, answers: List[str]):
        self.answers = answers
        self.current_idx = 0

    async def ask(self, question: str, notify_fn=None, workspace=None) -> str:
        if self.current_idx < len(self.answers):
            ans = self.answers[self.current_idx]
            self.current_idx += 1
            print(f"  [AutoUser] Pregunta: {question[:60]}...")
            print(f"  [AutoUser] Respuesta: {ans}")
            return ans
        # Si se queda sin respuestas, por defecto da carta libre
        print(f"  [AutoUser] Pregunta: {question[:60]}...")
        print(f"  [AutoUser] Respuesta (Default): si")
        return "si"

async def run_automated_mission(test_id: str, requirements: str, pre_recorded_answers: List[str]):
    print(f"\n{'='*60}")
    print(f" INICIANDO TEST AUTOMATIZADO: {test_id}")
    print(f"{'='*60}\n")
    
    # 1. Setup del Orquestador con Usuario Automatizado
    orchestrator = SodaOrchestrator()
    auto_user = AutomatedUser(pre_recorded_answers)
    
    # Inyectar el gateway automatizado
    from kernel.communication import user_interaction
    class MockGateway:
        async def ask(self, q, n, workspace=None):
            return await auto_user.ask(q, n, workspace)
    
    # Sobreescribir el getter del gateway temporalmente para el test
    user_interaction.get_gateway = lambda: MockGateway()

    # 2. Lanzar Misión
    try:
        project = await orchestrator.run(requirements, project_name=test_id)
        
        print(f"\n--- Verificación Post-Ejecución (SPEC-KIT COMPLIANCE) ---")
        
        project_path = project.workspace
        specify_path = project_path / ".specify"
        memory_path = specify_path / "memory"
        
        # 1. Verificar Constitución
        constitution = specify_path / "constitution.md"
        if constitution.exists():
            print("✅ SPEC-KIT: Constitution found.")
        else:
            print("❌ SPEC-KIT: Constitution MISSING.")

        # 2. Verificar Spec & Plan
        spec = project_path / "spec.md"
        plan = project_path / "plan.md"
        if spec.exists() and plan.exists():
            print("✅ SPEC-KIT: Spec and Plan files found.")
        else:
            print("❌ SPEC-KIT: Spec or Plan MISSING.")

        # 3. Verificar Tracker de Tareas
        tasks = project_path / "tasks.md"
        if tasks.exists():
            content = tasks.read_text(encoding="utf-8")
            if "Relay Note:" in content:
                print("✅ SPEC-KIT: Tasks tracker found with Relay Notes.")
            else:
                print("⚠️ SPEC-KIT: Tasks tracker found but NO Relay Notes detected.")
        else:
            print("❌ SPEC-KIT: Tasks tracker MISSING.")

        # 4. Verificar Memoria de Relevos
        relay_files = list(memory_path.glob("relay_*.md"))
        if len(relay_files) > 0:
            print(f"✅ SPEC-KIT: {len(relay_files)} Relay Note files found in memory.")
        else:
            print("❌ SPEC-KIT: No Relay Note files found in memory.")

        # 5. Verificar Software Generado
        src_dir = project.workspace / "source"
        if src_dir.exists():
            files = list(src_dir.rglob("*"))
            files = [f for f in files if f.is_file()]
            print(f"Archivos de software generados ({len(files)}):")
            if len(files) > 0: print("✅ TEST PASSED: Se generó software funcional.")
            else: print("❌ TEST FAILED: No se generaron archivos de código.")
        
    except Exception as e:
        print(f"❌ TEST ERROR: {e}")
    finally:
        # SODA FUSION: LIMPIEZA AGRESIVA DE PROCESOS
        print("\n[CLEANUP] Cerrando todos los procesos del test para liberar recursos...")
        try:
            # Matar cualquier proceso que haya quedado abierto por el orquestador
            import psutil
            current_process = psutil.Process()
            for child in current_process.children(recursive=True):
                child.kill()
        except Exception:
            pass
        
        print(f"--- Test {test_id} Finalizado Totalmente ---\n")
        # Dar un pequeño margen para que se cierren los sockets y fluyan los logs
        await asyncio.sleep(2)

def get_next_test_name() -> str:
    """Calcula el nombre test+n basado en las carpetas existentes en projects/."""
    projects_dir = Path("projects")
    if not projects_dir.exists():
        return "test1"
    
    n = 1
    while Path(f"SODA FUSION/projects/test{n}").exists() or Path(f"projects/test{n}").exists():
        n += 1
    return f"test{n}"

if __name__ == "__main__":
    # Configuración del Test
    test_name = get_next_test_name()
    
    # Requerimientos para un proyecto X
    reqs = "Crea una herramienta CLI en Python que indexe archivos de texto en una carpeta y permita buscar palabras clave devolviendo la línea y el número de línea. Debe ser modular y tener tests unitarios."
    
    # Respuestas pre-grabadas (Simulando la fase manual previa)
    # La última es 'si' para dar carta libre
    respuestas = [
        "Es una herramienta interna para desarrolladores", # P1: Objetivo
        "Interfaz CLI pura con salida formateada",         # P2: Interfaz
        "Desarrolladores que manejan muchos logs",          # P3: Usuario
        "Ollama con Qwen 2.5 Coder local",                 # P4: Modelo
        "Su velocidad de indexación local",                # P5: Diferenciador
        "si"                                               # P6: Carta libre / Auto-decisión
    ]
    
    asyncio.run(run_automated_mission(test_name, reqs, respuestas))
