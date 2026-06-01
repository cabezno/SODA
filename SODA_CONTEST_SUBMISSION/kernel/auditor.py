import time
import sys
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess

class GeminiAuditorHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        
        print(f"🔍 SODA Auditor: Detectado cambio de Gemini en {event.src_path}")
        self.audit_code(event.src_path)

    def audit_code(self, file_path):
        # 1. Validación de Sintaxis Rápida
        if file_path.endswith('.py'):
            res = subprocess.run([sys.executable, '-m', 'py_compile', file_path], capture_output=True)
        elif file_path.endswith('.go'):
            res = subprocess.run(['go', 'vet', file_path], capture_output=True)
        else:
            return

        if res.returncode != 0:
            print(f"❌ ERROR DE AUDITORÍA: Gemini ha introducido un error de sintaxis en {file_path}")
            print(f"Detalle: {res.stderr.decode()}")
        else:
            print(f"✅ AUDITORÍA PASADA: {file_path} es estructuralmente correcto.")
            # Aquí dispararíamos la consulta a Qwen 2.5 para lógica profunda
            self.deep_heuristic_review(file_path)

    def deep_heuristic_review(self, file_path):
        """
        [Falla 5] Implementación real de la revisión heurística profunda.
        Analiza el código en busca de fallas lógicas e integridad de paradigmas.
        """
        print(f"🧠 SODA: Solicitando revisión lógica a Qwen 2.5 para {file_path}...")

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code_content = f.read()

            # 1. Auditoría estática rápida de aislamiento de paradigmas (IMP-035)
            forbidden_imports = ["flask", "fastapi", "django", "http.server", "servlet"]
            # Si el archivo está en una ruta CLI, bloqueamos imports web
            if "cli" in file_path.lower() or "terminal" in file_path.lower():
                for imp in forbidden_imports:
                    if f"import {imp}" in code_content or f"from {imp}" in code_content:
                        print(f"🚨 VIOLACIÓN DE PARADIGMA (IMP-035): Importación web '{imp}' detectada en CLI ({file_path})")
                        # TODO: Disparar evento de auto-corrección quirúrgica

            # 2. Auditoría profunda vía API local de Ollama (Qwen)
            import requests
            payload = {
                "model": "qwen2.5-coder:14b",
                "messages": [
                    {"role": "system", "content": "Eres el Auditor Forense de SODA. Analiza el código en busca de fallas lógicas, variables indefinidas o malas prácticas. Responde de forma extremadamente concisa."},
                    {"role": "user", "content": f"Analiza este archivo:\n\n{code_content[:4000]}"}
                ],
                "stream": False
            }
            # Timeout corto para no bloquear el watchdog
            response = requests.post("http://localhost:11434/api/chat", json=payload, timeout=15)
            if response.status_code == 200:
                review = response.json().get("message", {}).get("content", "")
                print(f"📋 REVISIÓN LÓGICA DE QWEN PARA {Path(file_path).name}:\n{review}")

        except Exception as e:
            print(f"⚠️ No se pudo completar la revisión heurística profunda: {e}")

if __name__ == "__main__":
    path = "./workspace" # La carpeta donde Gemini está editando
    event_handler = GeminiAuditorHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    print(f"🛡️ Vigía SODA activo. Auditando el trabajo de Gemini en {path}...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()