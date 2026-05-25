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
        model: Optional[str] = None, # Permitimos sobrescribir el modelo
        images: list | None = None,
        metadata: dict | None = None,
        **kwargs # Capturamos argumentos extra (como response_schema) para no crashear
    ) -> DriverResponse:
        t0 = perf_counter()
        target_model = model or self.model

        if not self._api_key:
            return self._build_response(
                content=f"ERROR:AUTH: {self.provider} — API key no configurada",
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=target_model,
                metadata=metadata,
            )

        payload: dict = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format == "json":
            # DeepSeek y otros compatibles suelen preferir refuerzo en el prompt 
            # ya que json_object a veces no es soportado nativamente por todos los endpoints
            payload["response_format"] = {"type": "json_object"}
            user_message += "\n\nIMPORTANTE: Responde únicamente con un objeto JSON válido."

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
            message_obj = body["choices"][0]["message"]
            content = message_obj.get("content", "")
            reasoning = message_obj.get("reasoning_content") or message_obj.get("reasoning") # Algunos proveedores usan 'reasoning'
            
            usage = body.get("usage", {})
            return self._build_response(
                content=content,
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=self.model,
                tokens_input=usage.get("prompt_tokens"),
                tokens_output=usage.get("completion_tokens"),
                reasoning_content=reasoning,
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

    async def prompt(self, system: str, user: str) -> str:
        response = await self.call(system, user)
        return response.content
