import re
from pathlib import Path

f = Path("kernel/orchestrator.py")
content = f.read_text(encoding="utf-8")

# 1. Asegurar la inicialización robusta de blackbox al principio de __init__
# Buscamos el inicio de __init__
init_start = "class SodaOrchestrator:\n    def __init__(self, copilot_temperature: str = \"media\"):"
init_replacement = """class SodaOrchestrator:
    def __init__(self, copilot_temperature: str = "media"):
        from kernel.utils.blackbox_logger import SodaLogger
        self.blackbox = SodaLogger() # Inicialización inmediata
"""

if init_start in content:
    content = content.replace(init_start, init_replacement)

# 2. Limpiar duplicados y proxies mal puestos en el constructor original
# Eliminamos cualquier asignación de self.blackbox posterior en el constructor para evitar re-inicializar sin workspace
content = re.sub(r"\s+self\.blackbox = SodaLogger\(\)", "", content)

# 3. Limpiar las asignaciones de proxies que están rompiendo el __init__
# Eliminamos las líneas que intentan crear proxies antes de que gemini/ollama existan
content = re.sub(r"\s+from kernel\.drivers\.provider_hub import AIProxy\n\s+self\.gemini = AIProxy\(self\.gemini.*?\)\n\s+self\.ollama = AIProxy\(self\.ollama.*?\)\n", "", content)

# 4. Inyectar los proxies DESPUÉS de que los drivers se hayan creado
driver_init = "self.ollama = OllamaDriver()"
driver_replacement = """self.ollama = OllamaDriver()
        from kernel.drivers.provider_hub import AIProxy
        if hasattr(self, 'blackbox'):
            self.gemini = AIProxy(self.gemini, "gemini-2.5-flash", self.blackbox)
            self.ollama = AIProxy(self.ollama, "qwen2.5-coder:14b", self.blackbox)"""

if driver_init in content:
    content = content.replace(driver_init, driver_replacement)

f.write_text(content, encoding="utf-8")
print("Orchestrator: Orden de inicialización sanado estructuralmente.")
