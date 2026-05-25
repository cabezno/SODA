import re
from pathlib import Path

f = Path("kernel/orchestrator.py")
content = f.read_text(encoding="utf-8")

# Envolver self.gemini y self.ollama en AIProxy inmediatamente después de inicializar blackbox
target = "self.blackbox = SodaLogger()"
replacement = """self.blackbox = SodaLogger()
        from kernel.drivers.provider_hub import AIProxy
        self.gemini = AIProxy(self.gemini, "gemini-2.5-flash", self.blackbox)
        self.ollama = AIProxy(self.ollama, "qwen2.5-coder:14b", self.blackbox)"""

if target in content and "AIProxy(self.gemini" not in content:
    content = content.replace(target, replacement)

f.write_text(content, encoding="utf-8")
print("Orchestrator: Drivers nativos (Gemini/Ollama) ahora están bajo el BlackBox Proxy.")
