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


# Maximum output tokens per model — used to avoid under-provisioning max_tokens
_CLAUDE_MODEL_MAX_TOKENS: dict[str, int] = {
    "claude-haiku-4-5-20251001": 8_192,
    "claude-haiku-4-5":          8_192,
    "claude-sonnet-4-6":         64_000,
    "claude-sonnet-4-5":         64_000,
    "claude-opus-4-7":           32_000,
    "claude-opus-4-5":           32_000,
}
_CLAUDE_FALLBACK_MAX = 64_000  # safe default for unknown Claude models


def _resolve_claude_max_tokens(model: str, requested: int) -> int:
    """Return the effective max_tokens for a Claude call.

    If the caller passes the driver default (4096), we upgrade to the model's
    actual output limit so JSON responses are never cut mid-structure.
    Explicit small values (e.g. 512 for copilot eval) are preserved as-is.
    """
    model_limit = _CLAUDE_MODEL_MAX_TOKENS.get(model, _CLAUDE_FALLBACK_MAX)
    # Driver default (4096) is the sentinel for "caller didn't specify" → use model limit
    if requested <= 4096:
        return model_limit
    return min(requested, model_limit)


class ClaudeDriver(BaseDriver):
    MODEL = "claude-sonnet-4-6"
    provider = "claude"

    def __init__(self):
        super().__init__(self.MODEL)
        self._client: anthropic.AsyncAnthropic | None = None

    def _get_client(self) -> anthropic.AsyncAnthropic:
        """Return a cached AsyncAnthropic client, creating it once per driver instance."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=api_key)
        return self._client

    _CONTINUATION_MSG = (
        "Continuá exactamente el JSON desde donde fue cortado. "
        "Respondé SOLO con la continuación del JSON sin ningún texto adicional, "
        "sin repetir contenido anterior. El JSON debe terminar en '}'."
    )

    async def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,  # kept for API compat; Claude 4.x ignores it
        response_format: str = "text",
        images: list | None = None,
        metadata: dict | None = None,
        model: str | None = None,
        cached_context: str | None = None,
        max_continuations: int = 0,
    ) -> DriverResponse:
        """Call Claude using streaming.

        Streaming is used unconditionally — it is required by the Anthropic API
        for large max_tokens values and is otherwise equivalent to non-streaming
        for callers (the full response is collected before returning).

        cached_context: large static block (skills, blueprint, architecture summary)
        sent as a cached content block BEFORE user_message. Hits Anthropic's
        prompt cache on repeated calls with the same context, cutting input
        token cost by up to 90% and latency by ~40% for cache hits.

        Note: temperature is accepted for backward compatibility but is NOT sent
        to the API — Claude 4.x models deprecated it and return HTTP 400 if present.
        """
        client = self._get_client()
        t0 = perf_counter()
        effective_model = model if model is not None else self.model
        max_tokens = _resolve_claude_max_tokens(effective_model, max_tokens)
        system_param = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
        ]

        # Build user content: if a cached_context is provided, split the message
        # into a cached prefix (static) + uncached suffix (variable per call).
        if cached_context:
            user_content = [
                {
                    "type": "text",
                    "text": cached_context,
                    "cache_control": {"type": "ephemeral"},
                },
                {"type": "text", "text": user_message},
            ]
        else:
            user_content = _build_user_content(user_message, images)

        try:
            async with client.messages.stream(
                model=effective_model,
                max_tokens=max_tokens,
                system=system_param,
                messages=[{"role": "user", "content": user_content}],
            ) as stream:
                final_message = await stream.get_final_message()

            # Find first text block — Opus 4.7 may prepend thinking/redacted_thinking blocks
            content = ""
            for block in final_message.content:
                if getattr(block, "type", None) == "text":
                    content = block.text or ""
                    break
            stop_reason = getattr(final_message, "stop_reason", None)
            usage = getattr(final_message, "usage", None)
            in_tokens = getattr(usage, "input_tokens", 0) or 0
            out_tokens = getattr(usage, "output_tokens", 0) or 0

            # Continuation loop — if truncated and caller allows it, keep going
            if stop_reason == "max_tokens" and max_continuations > 0:
                accumulated = content
                orig_user_content = user_content  # keep for conversation history
                for cont_idx in range(max_continuations):
                    if stop_reason != "max_tokens":
                        break
                    cont_messages = [
                        {"role": "user", "content": orig_user_content},
                        {"role": "assistant", "content": accumulated},
                        {"role": "user", "content": self._CONTINUATION_MSG},
                    ]
                    async with client.messages.stream(
                        model=effective_model,
                        max_tokens=max_tokens,
                        system=system_param,
                        messages=cont_messages,
                    ) as cont_stream:
                        cont_msg = await cont_stream.get_final_message()
                    cont_text = ""
                    for blk in cont_msg.content:
                        if getattr(blk, "type", None) == "text":
                            cont_text = blk.text or ""
                            break
                    accumulated += cont_text
                    stop_reason = getattr(cont_msg, "stop_reason", None)
                    cu = getattr(cont_msg, "usage", None)
                    in_tokens += getattr(cu, "input_tokens", 0) or 0
                    out_tokens += getattr(cu, "output_tokens", 0) or 0
                content = accumulated

            # If still truncated after all continuations, flag it
            if stop_reason == "max_tokens" and not content.rstrip().endswith("}"):
                content = (
                    f"ERROR:TRUNCATED: Claude — respuesta cortada por max_tokens ({max_tokens}) "
                    f"tras {max_continuations} continuación(es). El JSON está incompleto."
                )

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

    async def chat(self, system: str, messages: list[dict], max_tokens: int = 1024) -> str:
        """Multi-turn conversation. messages = [{"role": "user"|"assistant", "content": str}, ...]"""
        client = self._get_client()
        system_param = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        try:
            async with client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system_param,
                messages=messages,
            ) as stream:
                final = await stream.get_final_message()
            for block in final.content:
                if getattr(block, "type", None) == "text":
                    return block.text or ""
            return ""
        except Exception as e:
            raise RuntimeError(f"Claude chat failed: {e}") from e
