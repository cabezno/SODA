import re

with open("kernel/drivers/gemini_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

signature_patch = """    async def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        top_p: float = 0.8,
        top_k: int = 40,
        response_format: str = "text",
        response_schema: dict | None = None,
        model: str | None = None,
        images: list | None = None,
        metadata: dict | None = None,
    ) -> DriverResponse:"""

content = re.sub(
    r'    async def call\(\n\s*self,\n\s*system_prompt: str,\n\s*user_message: str,\n\s*max_tokens: int = 4096,\n\s*temperature: float = 0\.7,\n\s*response_format: str = "text",\n\s*response_schema: dict \| None = None,\n\s*model: str \| None = None,\n\s*images: list \| None = None,\n\s*metadata: dict \| None = None,\n\s*\) -> DriverResponse:',
    signature_patch,
    content
)

config_patch = """        effective_max = _resolve_gemini_max_tokens(model or self.active_model, max_tokens)
        gen_config: dict = {
            "maxOutputTokens": effective_max, 
            "temperature": temperature,
            "topP": top_p,
            "topK": top_k
        }"""

content = re.sub(
    r'        effective_max = _resolve_gemini_max_tokens\(model or self\.active_model, max_tokens\)\n        gen_config: dict = \{"maxOutputTokens": effective_max, "temperature": temperature\}',
    config_patch,
    content
)

with open("kernel/drivers/gemini_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
