import asyncio
import unittest
import os
import shutil
import json
from pathlib import Path
from kernel.execution.boot_agent import BootAgent
from kernel.execution.project_runner import ProjectRunner

class TestBootLaunchIntegrity(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = Path("temp_test_project").resolve()
        self.test_dir.mkdir(exist_ok=True)
        self.source_dir = self.test_dir / "source"
        self.source_dir.mkdir(exist_ok=True)
        
        # Crear un script de prueba funcional
        self.main_file = self.source_dir / "main.py"
        self.main_file.write_text("print('HELLO SODA WORKED')", encoding="utf-8")
        
        self.runner = ProjectRunner()
        # Ajustado a la firma real de __init__
        self.boot_agent = BootAgent(
            notify_fn=lambda m, e="LOG": print(f"[{e}] {m}")
        )

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    async def test_manual_launch_capture(self):
        """Intenta lanzar el proceso manualmente y capturar por qué el BootAgent dice 'Unknown'."""
        print("\n--- INICIANDO DIAGNÓSTICO DE LANZAMIENTO ---")
        
        cwd = self.source_dir
        print(f"CWD: {cwd}")
        
        import subprocess
        try:
            # SODA usa shell=True en Windows para pipes
            proc = subprocess.Popen(
                ["python", "main.py"],
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8"
            )
            stdout, stderr = proc.communicate(timeout=10)
            
            print(f"STDOUT: {stdout.strip()}")
            print(f"STDERR: {stderr.strip()}")
            print(f"Exit Code: {proc.returncode}")
            
            self.assertEqual(stdout.strip(), "HELLO SODA WORKED")
            self.assertEqual(proc.returncode, 0)
            print("✅ El lanzamiento básico de Python funciona.")
            
        except Exception as e:
            print(f"❌ Error capturado en el lanzamiento: {e}")
            raise e

    async def test_boot_agent_full_cycle(self):
        """Ejecuta el ciclo completo del BootAgent para ver dónde se pierde el error."""
        # Configurar blueprint mínimo
        blueprint = {
            "comando_ejecucion": "python main.py",
            "comando_instalacion": "echo 'No dependencies'"
        }
        architecture = {
            "modulos": []
        }
        
        print("\n--- TESTEANDO CICLO COMPLETO DE BOOTAGENT ---")
        # El método real es run()
        report = await self.boot_agent.run(self.source_dir, architecture, blueprint)
        
        print(f"Estado Final del Boot (final_ok): {report.final_ok}")
        if not report.final_ok:
            print(f"Razón del fallo en reporte: {report.reason}")
            if report.attempts:
                last = report.attempts[-1]
                print(f"Último output de boot: {last.boot_output}")

if __name__ == "__main__":
    unittest.main()
