import re
from pathlib import Path

f = Path("kernel/orchestrator.py")
content = f.read_text(encoding="utf-8")

# Inyectar log_event en notify_wrapper dentro de run() y resume()
target = """        def notify_wrapper(event_type: str, message: str, data: dict = None):
            # Estandarizado V2: recibimos (event_type, message, data)
            # El método interno _notify espera (message, event_type, data)
            self._notify(message, event_type, {**(data or {}), "project_id": project.id})"""

replacement = """        def notify_wrapper(event_type: str, message: str, data: dict = None):
            # Estandarizado V2: recibimos (event_type, message, data)
            # El método interno _notify espera (message, event_type, data)
            if hasattr(self, 'blackbox') and self.blackbox:
                self.blackbox.log_event(event_type, message, data)
            self._notify(message, event_type, {**(data or {}), "project_id": project.id})"""

content = content.replace(target, replacement)

f.write_text(content, encoding="utf-8")
print("Orchestrator: notify_wrapper ahora escribe en el BlackBox.")
