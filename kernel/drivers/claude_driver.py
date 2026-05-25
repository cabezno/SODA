from __future__ import annotations

import asyncio
import os
from pathlib import Path
from time import perf_counter
from typing import Optional

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None

from kernel.drivers.base import BaseDriver, DriverResponse


class ClaudeDriver(BaseDriver):
    """
    Anthropic Claude Driver.
    Requires 'anthropic' library installed.
    """
    provider: str = "claude"

    def __init__(self, model_name: str = "claude-3-5-sonnet-latest"):
        super().__init__(model_name)
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self._client = None

    def _get_client(self) -> AsyncAnthropic:
        if not AsyncAnthropic:
            raise ImportError("La librería 'anthropic' no está instalada. Ejecutá: pip install anthropic")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY no configurada en el entorno.")
        
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        response_format: str = "text",
        model: Optional[str] = None,
        images: Optional[list] = None,
        metadata: Optional[dict] = None,
        **kwargs
    ) -> DriverResponse:
        start_time = perf_counter()
        # FIX: Ensure we use 'claude-3-5-sonnet-latest' if 'claude' is passed or if the name is truncated
        target_model = model or self.model
        if target_model == "claude":
            target_model = "claude-3-5-sonnet-latest"
        
        try:
            client = self._get_client()
            
            # Si se pide JSON pero Claude no soporta schema nativo vía API estándar, 
            # reforzamos el prompt internamente.
            if response_format == "json":
                user_message += "\n\nIMPORTANTE: Responde ÚNICAMENTE con el objeto JSON solicitado."

            # Format message for Anthropic API
            messages = [{"role": "user", "content": user_message}]
            
            # Claude prefers system prompt as a top-level parameter
            response = await client.messages.create(
                model=target_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=[{
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"} # Cachear el system prompt
                }],
                messages=messages
            )
            
            content = response.content[0].text
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens
            
            # Registro de uso de cache si está disponible
            cache_creation = getattr(response.usage, "cache_creation_input_tokens", 0)
            cache_read = getattr(response.usage, "cache_read_input_tokens", 0)
            
            return self._build_response(
                content=content,
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=start_time,
                model_used=target_model,
                tokens_input=tokens_in + cache_read,
                tokens_output=tokens_out,
                metadata={**(metadata or {}), "cache_read": cache_read, "cache_creation": cache_creation}
            )

        except Exception as e:
            error_content = f"ERROR:CONNECTION: Claude falló — {str(e)}"
            return self._build_response(
                content=error_content,
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=start_time,
                metadata=metadata
            )

    async def prompt(self, system: str, user: str) -> str:
        """Async helper that returns only the text content."""
        response = await self.call(system, user)
        return response.content
