import re
from pathlib import Path

f = Path("kernel/drivers/provider_hub.py")
content = f.read_text(encoding="utf-8")

# 1. Inyectar logger en __init__
if "self.blackbox = None" not in content:
    content = content.replace(
        "self._routes: Dict[str, List[str]] = dict(DEFAULT_ROUTES)",
        "self._routes: Dict[str, List[str]] = dict(DEFAULT_ROUTES)\n        self.blackbox = None"
    )

# 2. Modificar el método get() para envolver el driver
old_get = """    def get(self, name: str) -> Optional[object]:
        # 1. Match exacto (ej: 'gemini' o 'claude-3-5-sonnet')
        if name in self._providers:
            return self._providers[name]"""

new_get = """    def get(self, name: str) -> Optional[object]:
        driver = self._get_raw_driver(name)
        if driver and self.blackbox:
            return AIProxy(driver, name, self.blackbox)
        return driver

    def _get_raw_driver(self, name: str) -> Optional[object]:
        # 1. Match exacto (ej: 'gemini' o 'claude-3-5-sonnet')
        if name in self._providers:
            return self._providers[name]"""

if old_get in content:
    content = content.replace(old_get, new_get)

# 3. Añadir la clase AIProxy al final del archivo
proxy_class = """

class AIProxy:
    \"\"\"Proxy que intercepta llamadas al driver para loguear comunicación profunda.\"\"\"
    def __init__(self, target, model_name, logger):
        self._target = target
        self._model_name = model_name
        self._logger = logger

    async def call(self, **kwargs):
        provider = type(self._target).__name__
        prompt = kwargs.get("user_message", "")
        system = kwargs.get("system_prompt", "")
        full_prompt = f"SYSTEM: {system}\\nUSER: {prompt}"
        
        try:
            response = await self._target.call(**kwargs)
            self._logger.log_ai_communication(
                provider=provider,
                model=self._model_name,
                prompt=full_prompt,
                response=response.content if hasattr(response, "content") else str(response),
                metadata=kwargs.get("metadata", {})
            )
            return response
        except Exception as e:
            self._logger.log_ai_communication(
                provider=provider,
                model=self._model_name,
                prompt=full_prompt,
                response=f"ERROR: {str(e)}",
                metadata=kwargs.get("metadata", {})
            )
            raise e

    def __getattr__(self, name):
        return getattr(self._target, name)
"""

if "class AIProxy" not in content:
    content += proxy_class

f.write_text(content, encoding="utf-8")
print("ProviderHub actualizado con AIProxy y BlackBox.")
