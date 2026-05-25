import asyncio
import ollama
import os
from time import perf_counter

from kernel.drivers.base import BaseDriver, DriverResponse

PREFERRED_MODELS = ["qwen2.5-coder:14b", "qwen2.5-coder:7b"]
CHAT_TIMEOUT = 180  # seconds — Qwen 7B typically 15-25s; 180 gives generous headroom


import psutil
def _resolve_model_sync(host: str, preferred: list[str]) -> str:
    """Return 14b if RAM is sufficient, else fallback to 7b."""
    try:
        import ollama
        client = ollama.Client(host=host)
        available = {m["name"] for m in client.list().get("models", [])}
        
        # Hardware Check
        ram = psutil.virtual_memory()
        free_ram_gb = ram.available / (1024 ** 3)
        
        # 14b usually needs at least ~10GB of free RAM/VRAM combined to run decently
        # If we have less than 8GB of system RAM free, we aggressively fallback to 7b.
        if "qwen2.5-coder:14b" in available and free_ram_gb >= 8.0:
            return "qwen2.5-coder:14b"
        elif "qwen2.5-coder:7b" in available:
            if free_ram_gb < 8.0:
                print(f"  [Ollama] RAM crítica detectada ({free_ram_gb:.1f}GB libres). Activando fallback a Qwen 7B.")
            return "qwen2.5-coder:7b"
            
        # Standard fallback if neither specific logic hits
        for candidate in preferred:
            if candidate in available:
                return candidate
    except Exception:
        pass
    return preferred[-1]


class OllamaDriver(BaseDriver):
    provider = "ollama"

    def __init__(self, model_name: str | None = None):
        self.host = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self._model_override = model_name or os.getenv("OLLAMA_MODEL")
        self._resolved_model: str | None = self._model_override
        # Use the last fallback as placeholder — actual resolution happens lazily
        super().__init__(self._model_override or PREFERRED_MODELS[-1])

    async def _get_model(self) -> str:
        """Resolve model name lazily (async-safe — runs sync list() in thread)."""
        if self._resolved_model:
            return self._resolved_model
        self._resolved_model = await asyncio.to_thread(
            _resolve_model_sync, self.host, PREFERRED_MODELS
        )
        self.model = self._resolved_model
        return self._resolved_model

    async def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        response_format: str = "text",
        model: str | None = None,
        images: list | None = None,
        metadata: dict | None = None,
        **kwargs,
    ) -> DriverResponse:
        # Honour explicit model request (e.g. from ModelLockedProxy or FinopsRouter).
        # Fall back to lazy hardware-aware resolution only when no model specified.
        if model:
            resolved_model = model
        else:
            resolved_model = await self._get_model()
        model = resolved_model
        client = ollama.AsyncClient(host=self.host)
        t0 = perf_counter()
        try:
            response = await asyncio.wait_for(
                client.chat(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                ),
                timeout=CHAT_TIMEOUT,
            )
            content = response["message"]["content"]
            prompt_eval_count = response.get("prompt_eval_count")
            eval_count = response.get("eval_count")
            return self._build_response(
                content=content,
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=model,
                tokens_input=prompt_eval_count,
                tokens_output=eval_count,
                metadata=metadata,
            )
        except asyncio.TimeoutError:
            msg = f"ERROR:TIMEOUT: Qwen — sin respuesta tras {CHAT_TIMEOUT}s (modelo: {model})"
            return self._build_response(
                content=msg,
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=model,
                metadata=metadata,
            )
        except ollama.ResponseError as e:
            if "model" in str(e).lower() and "not found" in str(e).lower():
                msg = f"ERROR:MODEL_NOT_FOUND: Qwen — modelo '{model}' no encontrado en Ollama. Ejecutá: ollama pull {model}"
            else:
                msg = f"ERROR:RESPONSE: Qwen — {str(e)}"
            return self._build_response(
                content=msg,
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=model,
                metadata=metadata,
            )
        except Exception as e:
            msg = str(e)
            if "connection" in msg.lower() or "refused" in msg.lower() or "connect" in msg.lower():
                msg = f"ERROR:CONNECTION: Qwen — Ollama no está corriendo en {self.host}. Iniciá Ollama."
            else:
                msg = f"ERROR:UNKNOWN: Qwen — {msg}"
            return self._build_response(
                content=msg,
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=model,
                metadata=metadata,
            )

    async def warmup(self) -> None:
        """Pre-load model into VRAM with a trivial request. Fire-and-forget at pipeline start."""
        try:
            model = await self._get_model()
            client = ollama.AsyncClient(host=self.host)
            await asyncio.wait_for(
                client.chat(
                    model=model,
                    messages=[{"role": "user", "content": "ping"}],
                    options={"num_predict": 1},
                ),
                timeout=30,
            )
        except Exception:
            pass  # warmup is best-effort, never blocks the pipeline

    async def prompt(self, system: str, user: str) -> str:
        return (await self.call(system, user)).content
