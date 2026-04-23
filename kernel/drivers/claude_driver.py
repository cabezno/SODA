import base64
import os
from pathlib import Path
from time import perf_counter

import anthropic

from kernel.drivers.base import BaseDriver, DriverResponse


def _build_user_content(user_message: str, images: list | None) -> list | str:
    """Build message content, adding base64-encoded images when provided."""
    if not images:
        return user_message
    content: list = [{"type": "text", "text": user_message}]
    for img_path in images:
        try:
            img_bytes = Path(img_path).read_bytes()
            data = base64.standard_b64encode(img_bytes).decode("utf-8")
            suffix = Path(img_path).suffix.lower().lstrip(".")
            media_type = f"image/{'jpeg' if suffix in ('jpg', 'jpeg') else suffix or 'png'}"
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            })
        except Exception:
            pass
    return content


class ClaudeDriver(BaseDriver):
    MODEL = "claude-sonnet-4-6"
    provider = "claude"

    def __init__(self):
        super().__init__(self.MODEL)

    async def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        response_format: str = "text",
        images: list | None = None,
        metadata: dict | None = None,
        model: str | None = None,
    ) -> DriverResponse:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        client = anthropic.AsyncAnthropic(api_key=api_key)
        t0 = perf_counter()
        effective_model = model if model is not None else self.model
        system_param = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
        ]
        try:
            message = await client.messages.create(
                model=effective_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_param,
                messages=[{"role": "user", "content": _build_user_content(user_message, images)}],
            )
            content = message.content[0].text
            usage = getattr(message, "usage", None)
            in_tokens = getattr(usage, "input_tokens", None)
            out_tokens = getattr(usage, "output_tokens", None)
            return self._build_response(
                content=content,
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=effective_model,
                tokens_input=in_tokens,
                tokens_output=out_tokens,
                metadata=metadata,
            )
        except anthropic.AuthenticationError:
            return self._build_response(
                content="ERROR:AUTH: Claude — clave API inválida o no configurada (ANTHROPIC_API_KEY)",
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=effective_model,
                metadata=metadata,
            )
        except anthropic.RateLimitError:
            return self._build_response(
                content="ERROR:RATE_LIMIT: Claude — cuota agotada o límite de velocidad superado",
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=effective_model,
                metadata=metadata,
            )
        except anthropic.APIStatusError as e:
            code = e.status_code
            if code == 529:
                msg = "ERROR:OVERLOADED: Claude — servidor sobrecargado, reintentá en unos minutos"
            else:
                msg = f"ERROR:API: Claude — HTTP {code}: {e.message}"
            return self._build_response(
                content=msg,
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=effective_model,
                metadata=metadata,
            )
        except anthropic.APIConnectionError:
            return self._build_response(
                content="ERROR:CONNECTION: Claude — no se pudo conectar con la API de Anthropic",
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=effective_model,
                metadata=metadata,
            )
        except Exception as e:
            return self._build_response(
                content=f"ERROR:UNKNOWN: Claude — {str(e)}",
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=effective_model,
                metadata=metadata,
            )

    async def prompt(self, system: str, user: str) -> str:
        return (await self.call(system, user)).content
