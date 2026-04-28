from __future__ import annotations

import os
from time import perf_counter

import httpx

from kernel.drivers.base import BaseDriver, DriverResponse


class OpenAIDriver(BaseDriver):
    provider = "openai"

    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
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

        if not self.api_key:
            return self._build_response(
                content="ERROR:AUTH: OpenAI — OPENAI_API_KEY no configurada",
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=self.model,
                metadata=metadata,
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        client = self._get_client()
        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            if response.status_code != 200:
                if response.status_code in (401, 403):
                    content = "ERROR:AUTH: OpenAI — clave API inválida o sin permisos"
                elif response.status_code == 429:
                    content = "ERROR:RATE_LIMIT: OpenAI — cuota agotada o límite de velocidad superado"
                elif response.status_code in (500, 502, 503, 504):
                    content = "ERROR:OVERLOADED: OpenAI — servicio temporalmente no disponible"
                else:
                    content = f"ERROR:API: OpenAI — HTTP {response.status_code}: {response.text[:120]}"

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
            in_tokens = usage.get("prompt_tokens")
            out_tokens = usage.get("completion_tokens")

            return self._build_response(
                content=content,
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=self.model,
                tokens_input=in_tokens,
                tokens_output=out_tokens,
                metadata=metadata,
            )
        except httpx.ConnectError:
            return self._build_response(
                content="ERROR:CONNECTION: OpenAI — sin conexión a internet",
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=self.model,
                metadata=metadata,
            )
        except httpx.TimeoutException:
            return self._build_response(
                content="ERROR:TIMEOUT: OpenAI — tiempo de espera agotado (>120s)",
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=self.model,
                metadata=metadata,
            )
        except Exception as e:
            return self._build_response(
                content=f"ERROR:UNKNOWN: OpenAI — {str(e)}",
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=self.model,
                metadata=metadata,
            )

    async def prompt(self, system: str, user: str) -> str:
        return (await self.call(system, user)).content
