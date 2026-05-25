import re
from pathlib import Path

f = Path("kernel/orchestrator.py")
content = f.read_text(encoding="utf-8")

# 1. Encontrar la definición de SodaLogger e inicializarla antes del Hub
if "self.blackbox = SodaLogger()" in content:
    # Eliminar la inicialización tardía
    content = content.replace("\n        self.blackbox = SodaLogger()", "")
    
# 2. Insertar la inicialización de blackbox justo antes del AIProviderHub
init_target = "self.builder = ContextBuilder()"
init_replacement = "self.builder = ContextBuilder()\n        from kernel.utils.blackbox_logger import SodaLogger\n        self.blackbox = SodaLogger()"

if init_target in content:
    content = content.replace(init_target, init_replacement)

f.write_text(content, encoding="utf-8")
print("Orden de inicialización del BlackBox corregido.")
