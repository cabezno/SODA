import re
from pathlib import Path

f = Path("kernel/orchestrator.py")
content = f.read_text(encoding="utf-8")

# Bloque limpio y ordenado para el __init__
clean_init = """    def __init__(self, copilot_temperature: str = "media"):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.projects_dir = self.base_dir / "projects"
        self.projects_dir.mkdir(exist_ok=True)

        self._copilot_temperature = copilot_temperature
        self._copilot_max_passes = 3
        self._copilot_phase_regen = 1

        # 1. Logger BlackBox (Debe ser lo primero)
        from kernel.utils.blackbox_logger import SodaLogger
        self.blackbox = SodaLogger()

        # 2. Infraestructura básica
        self.builder = ContextBuilder()
        self.gemini = GeminiDriver()
        self.ollama = OllamaDriver()

        # 3. Proxies de IA (Envuelven a los drivers usando el blackbox)
        from kernel.drivers.provider_hub import AIProxy
        self.gemini = AIProxy(self.gemini, "gemini-2.5-flash", self.blackbox)
        self.ollama = AIProxy(self.ollama, "qwen2.5-coder:14b", self.blackbox)
        
        # 4. Hub de Proveedores (Usa los drivers ya envueltos)
        self.ai_hub = AIProviderHub(
            providers={
                "gemini": self.gemini,
                "ollama": self.ollama,
                "claude": ClaudeDriver(model_name="claude-3-5-sonnet-latest"),
                "deepseek": build_driver("deepseek", "sk-bce5166e987d41a4b22d8f4180642f35", "deepseek-chat", "https://api.deepseek.com/v1", "openai_compat")
            },
            routes=self._load_ai_routing(),
        )
        self.ai_hub.blackbox = self.blackbox
"""

# Sustitución masiva del bloque de inicialización corrupto
content = re.sub(
    r"def __init__\(self, copilot_temperature: str = \"media\"\):[\s\S]+?self\.ai_hub\.blackbox = self\.blackbox",
    clean_init,
    content
)

f.write_text(content, encoding="utf-8")
print("Orchestrator: Constructor reconstruido con orden lógico y robusto.")
