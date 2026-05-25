import re
from pathlib import Path

f = Path("kernel/orchestrator.py")
content = f.read_text(encoding="utf-8")

# Limpiar el bloque fallido
target_fail = """        self.blackbox = SodaLogger()
        from kernel.drivers.provider_hub import AIProxy
        self.gemini = AIProxy(self.gemini, "gemini-2.5-flash", self.blackbox)
        self.ollama = AIProxy(self.ollama, "qwen2.5-coder:14b", self.blackbox)
        self.gemini = GeminiDriver()
        self.ollama = OllamaDriver()"""

replacement_correct = """        self.blackbox = SodaLogger()
        self.gemini = GeminiDriver()
        self.ollama = OllamaDriver()
        from kernel.drivers.provider_hub import AIProxy
        self.gemini = AIProxy(self.gemini, "gemini-2.5-flash", self.blackbox)
        self.ollama = AIProxy(self.ollama, "qwen2.5-coder:14b", self.blackbox)"""

if target_fail in content:
    content = content.replace(target_fail, replacement_correct)
else:
    # Si por alguna razón el target_fail no coincide exactamente, buscamos las líneas sueltas
    content = re.sub(r"self\.gemini = AIProxy.*?\n", "", content)
    content = re.sub(r"self\.ollama = AIProxy.*?\n", "", content)
    content = content.replace("self.ollama = OllamaDriver()", "self.ollama = OllamaDriver()\n        from kernel.drivers.provider_hub import AIProxy\n        self.gemini = AIProxy(self.gemini, 'gemini-2.5-flash', self.blackbox)\n        self.ollama = AIProxy(self.ollama, 'qwen2.5-coder:14b', self.blackbox)")

f.write_text(content, encoding="utf-8")
print("Orchestrator: Orden de inicialización de drivers y proxies corregido.")
