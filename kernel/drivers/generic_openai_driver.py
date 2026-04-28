from __future__ import annotations

import asyncio
from time import perf_counter

import httpx

from kernel.drivers.base import BaseDriver, DriverResponse


class GenericOpenAIDriver(BaseDriver):
    """Driver for any OpenAI-compatible API (Groq, Mistral, DeepSeek, Together, OpenRouter, etc.)."""

    def __init__(self, provider_name: str, api_key: str, base_url: str, model_name: str):
        self.provider = provider_name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        super().__init__(model_name)
        self._http: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
        return self._http

    async def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        response_format: str = "text",
        images: list | None = None,
        metadata: dict | None = None,
    ) -> DriverResponse:
        t0 = perf_counter()

        if not self._api_key:
            return self._build_response(
                content=f"ERROR:AUTH: {self.provider} — API key no configurada",
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=self.model,
                metadata=metadata,
            )

        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        client = self._get_client()
        try:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            if response.status_code != 200:
                if response.status_code in (401, 403):
                    content = f"ERROR:AUTH: {self.provider} — clave API inválida o sin permisos"
                elif response.status_code == 429:
                    content = f"ERROR:RATE_LIMIT: {self.provider} — cuota agotada o límite de velocidad"
                elif response.status_code in (500, 502, 503, 504):
                    content = f"ERROR:OVERLOADED: {self.provider} — servicio temporalmente no disponible"
                else:
                    content = f"ERROR:API: {self.provider} — HTTP {response.status_code}: {response.text[:120]}"
                return self._build_response(
                    content=content,
                    system_prompt=system_prompt,
                    user_message=user_message,
                    latency_start=t0,
                    model_used=self.model,
                    metadata=metadata,
                )

            body = response.json()
            content = body["choices"][0]["message"]["content"]
            usage = body.get("usage", {})
            return self._build_response(
                content=content,
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=self.model,
                tokens_input=usage.get("prompt_tokens"),
                tokens_output=usage.get("completion_tokens"),
                metadata=metadata,
            )

        except httpx.ConnectError:
            return self._build_response(
                content=f"ERROR:CONNECTION: {self.provider} — sin conexión o URL incorrecta",
                system_prompt=system_prompt, user_message=user_message,
                latency_start=t0, model_used=self.model, metadata=metadata,
            )
        except httpx.TimeoutException:
            return self._build_response(
                content=f"ERROR:TIMEOUT: {self.provider} — tiempo de espera agotado",
                system_prompt=system_prompt, user_message=user_message,
                latency_start=t0, model_used=self.model, metadata=metadata,
            )
        except Exception as e:
            return self._build_response(
                content=f"ERROR:UNKNOWN: {self.provider} — {e}",
                system_prompt=system_prompt, user_message=user_message,
                latency_start=t0, model_used=self.model, metadata=metadata,
            )

    def prompt(self, system: str, user: str) -> str:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    return ex.submit(asyncio.run, self.call(system, user)).result().content
            return loop.run_until_complete(self.call(system, user)).content
        except RuntimeError:
            return asyncio.run(self.call(system, user)).content
