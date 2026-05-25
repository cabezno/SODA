import re
from pathlib import Path

f = Path("kernel/orchestrator.py")
content = f.read_text(encoding="utf-8")

# Función para refrescar el logger en todos los componentes
refresh_logic = """        # Refrescar visibilidad (BlackBox)
        self.blackbox = SodaLogger(project.workspace)
        self.ai_hub.blackbox = self.blackbox
        from kernel.drivers.provider_hub import AIProxy
        # Desenvolver si ya eran proxies para no crear capas infinitas
        raw_gemini = self.gemini._target if isinstance(self.gemini, AIProxy) else self.gemini
        raw_ollama = self.ollama._target if isinstance(self.ollama, AIProxy) else self.ollama
        self.gemini = AIProxy(raw_gemini, "gemini-2.5-flash", self.blackbox)
        self.ollama = AIProxy(raw_ollama, "qwen2.5-coder:14b", self.blackbox)"""

# Insertar en resume()
content = content.replace(
    "self.blackbox = SodaLogger(project.workspace)",
    refresh_logic
)

# Insertar en run()
content = content.replace(
    "self.blackbox = SodaLogger(project.workspace)",
    refresh_logic
)

f.write_text(content, encoding="utf-8")
print("Orchestrator: Refresco de BlackBox inyectado en run() y resume().")
