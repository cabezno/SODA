import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess

class ClaudeAuditorHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        
        print(f"🔍 SODA Auditor: Detectado cambio de Claude en {event.src_path}")
        self.audit_code(event.src_path)

    def audit_code(self, file_path):
        # 1. Validación de Sintaxis Rápida
        if file_path.endswith('.py'):
            res = subprocess.run(['python', '-m', 'py_compile', file_path], capture_output=True)
        elif file_path.endswith('.go'):
            res = subprocess.run(['go', 'vet', file_path], capture_output=True)
        else:
            return

        if res.returncode != 0:
            print(f"❌ ERROR DE AUDITORÍA: Claude ha introducido un error de sintaxis en {file_path}")
            print(f"Detalle: {res.stderr.decode()}")
        else:
            print(f"✅ AUDITORÍA PASADA: {file_path} es estructuralmente correcto.")
            # Aquí dispararíamos la consulta a Qwen 2.5 para lógica profunda
            self.deep_heuristic_review(file_path)

    def deep_heuristic_review(self, file_path):
        print(f"🧠 SODA: Solicitando revisión lógica a Qwen 2.5 para {file_path}...")
        # Lógica para enviar el contenido del archivo a la API de Ollama/Qwen

if __name__ == "__main__":
    path = "./workspace" # La carpeta donde Claude está editando
    event_handler = ClaudeAuditorHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    print(f"🛡️ Vigía SODA activo. Auditando el trabajo de Claude en {path}...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()