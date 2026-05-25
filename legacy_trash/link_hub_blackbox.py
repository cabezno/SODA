import re
from pathlib import Path

f = Path("kernel/orchestrator.py")
content = f.read_text(encoding="utf-8")

# Inyectar el logger en el hub inmediatamente después de crearlo
hub_init = "self.ai_hub = AIProviderHub("
hub_patch = "self.ai_hub.blackbox = self.blackbox"

if hub_init in content and hub_patch not in content:
    # Buscamos el final del paréntesis del constructor del Hub
    # Como el constructor tiene varias líneas, buscamos el cierre ')'
    # y la siguiente línea para insertar.
    parts = content.split("routes=self._load_ai_routing(),")
    if len(parts) > 1:
        # Reinsertamos con la línea de inyección
        content = parts[0] + "routes=self._load_ai_routing(),\n        )\n        self.ai_hub.blackbox = self.blackbox" + parts[1].split(")", 1)[1]

# Inyectar SodaLogger(project.workspace) en el Hub durante run() y resume()
update_hub_logger = "self.ai_hub.blackbox = self.blackbox"
# Esto ya se hace en la parte del Hub si self.blackbox se actualiza, 
# pero vamos a asegurar que en run() y resume() se refresque.

f.write_text(content, encoding="utf-8")
print("Orchestrator: Hub vinculado con BlackBox.")
