import os
import asyncio
import httpx
from time import perf_counter
from dotenv import load_dotenv
from kernel.drivers.base import BaseDriver, DriverResponse

class DeepSeekDriver(BaseDriver):
    """
    Driver para DeepSeek API. 
    Especializado en Deep Thinking (R1) y Auditoría (V3).
    """
    provider = "deepseek"

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com"
        self._http = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=15.0))
        return self._http

    async def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        model: str = "deepseek-reasoner", # R1 por defecto para razonamiento superior
        **kwargs
    ) -> DriverResponse:
        t0 = perf_counter()
        client = self._get_client()
        
        # DeepSeek usa formato OpenAI
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            print(f"  [DeepSeek] Llamando a {model}...")
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )

            if response.status_code == 200:
                res_json = response.json()
                content = res_json["choices"][0]["message"]["content"]
                usage = res_json.get("usage", {})
                
                t1 = perf_counter()
                latency_ms = int((t1 - t0) * 1000)
                
                # Costos aproximados V3/R1
                cost = (usage.get("prompt_tokens", 0) * 0.00000014) + \
                       (usage.get("completion_tokens", 0) * 0.00000028)

                return DriverResponse(
                    content=content,
                    tokens_input=usage.get("prompt_tokens", 0),
                    tokens_output=usage.get("completion_tokens", 0),
                    latency_ms=latency_ms,
                    model_used=model,
                    cost_usd=cost
                )
            else:
                print(f"  [DeepSeek] ERROR {response.status_code}: {response.text[:200]}")
                return DriverResponse(content=f"ERROR:DEEPSEEK:{response.status_code}", model_used=model)

        except Exception as e:
            print(f"  [DeepSeek] Excepción: {e}")
            return DriverResponse(content=f"ERROR:EXCEPTION:{str(e)}", model_used=model)

    async def prompt(self, system: str, user: str, **kwargs) -> str:
        resp = await self.call(system, user, **kwargs)
        return resp.content
