import re
from pathlib import Path

f = Path("kernel/orchestrator.py")
content = f.read_text(encoding="utf-8")

# Corregir la indentación del bloque __init__
# El error es que 'def __init__' tiene 8 espacios en lugar de 4, o el bloque interior tiene 0.
# En el archivo leído se ve:
# class SodaOrchestrator:
#         def __init__(self, ...):
#         self.base_dir = ...

target = """class SodaOrchestrator:
        def __init__(self, copilot_temperature: str = "media"):
        self.base_dir = Path(__file__).resolve().parent.parent"""

# La forma correcta:
replacement = """class SodaOrchestrator:
    def __init__(self, copilot_temperature: str = "media"):
        self.base_dir = Path(__file__).resolve().parent.parent"""

if target in content:
    content = content.replace(target, replacement)
else:
    # Intento más genérico por si fallan los espacios exactos
    content = re.sub(
        r"class SodaOrchestrator:\n\s+def __init__\(self, copilot_temperature: str = \"media\"\):\n\s+self\.base_dir",
        "class SodaOrchestrator:\n    def __init__(self, copilot_temperature: str = \"media\"):\n        self.base_dir",
        content
    )

f.write_text(content, encoding="utf-8")
print("Orchestrator: Error de indentación corregido.")
