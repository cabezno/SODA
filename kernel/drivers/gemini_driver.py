from __future__ import annotations

import asyncio
import os
from pathlib import Path
from time import perf_counter

import httpx
from dotenv import load_dotenv

from kernel.drivers.base import BaseDriver, DriverResponse


# Maximum output tokens per Gemini model variant
_GEMINI_MODEL_MAX_TOKENS: dict[str, int] = {
    "gemini-2.5-pro":   65_536,
    "gemini-2.5-flash": 65_536,
    "gemini-2.0-flash": 8_192,
    "gemini-2.0-pro":   8_192,
    "gemini-1.5-pro":   8_192,
    "gemini-1.5-flash": 8_192,
}
_GEMINI_FALLBACK_MAX = 65_536


def _resolve_gemini_max_tokens(model: str | None, requested: int) -> int:
    """Upgrade driver default (4096) to model-appropriate limit; preserve explicit small values."""
    model_limit = _GEMINI_MODEL_MAX_TOKENS.get(model or "", _GEMINI_FALLBACK_MAX)
    if requested <= 4096:
        return model_limit
    return min(requested, model_limit)


class GeminiDriver(BaseDriver):
    provider = "gemini"

    # All available Gemini models ordered by capability (free-tier capable ones marked)
    ALL_MODELS = [
        "gemini-2.5-pro",          # paid/pro
        "gemini-2.5-flash",        # free tier available
        "gemini-2.0-flash",        # free tier available
        "gemini-2.0-pro",
        "gemini-1.5-pro",
        "gemini-1.5-flash",        # free tier available
    ]

    def __init__(self):
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        load_dotenv(env_path)
        self.api_key = os.getenv("GEMINI_API_KEY")
        # Respect user-configured preferred model from env or soda_config.json
        preferred = os.getenv("GEMINI_MODEL") or self._read_config_model()
        if preferred and preferred in self.ALL_MODELS:
            # Put the preferred model first in the probe order
            self.candidate_models = [preferred] + [m for m in self.ALL_MODELS if m != preferred]
        else:
            self.candidate_models = list(self.ALL_MODELS)
        self.active_model: str | None = None
        self._http: httpx.AsyncClient | None = None
        self._probe_lock: asyncio.Lock = asyncio.Lock()
        super().__init__(self.candidate_models[0])

    @staticmethod
    def _read_config_model() -> str:
        """Read gemini_model preference from soda_config.json if present."""
        try:
            cfg_path = Path(__file__).resolve().parent.parent.parent / "soda_config.json"
            if cfg_path.exists():
                import json as _json
                data = _json.loads(cfg_path.read_text(encoding="utf-8"))
                return data.get("gemini_model", "")
        except Exception:
            pass
        return ""

    def _url(self, model: str) -> str:
        return (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={self.api_key}"
        )

    def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
        return self._http

    def _classify_http_error(self, status: int, body: str) -> str:
        if status == 400:
            return "ERROR:BAD_REQUEST: Gemini — petición inválida"
        if status in (401, 403):
            return "ERROR:AUTH: Gemini — clave API inválida o sin permisos (GEMINI_API_KEY)"
        if status == 429:
            return "ERROR:RATE_LIMIT: Gemini — cuota agotada o demasiadas solicitudes"
        if status == 503:
            return "ERROR:OVERLOADED: Gemini — servicio temporalmente no disponible"
        return f"ERROR:API: Gemini — HTTP {status}: {body[:120]}"

    async def _probe_models(self, t0: float, system_prompt: str, user_message: str, metadata: dict | None) -> DriverResponse | None:
        """Try each candidate model until one responds 200. Returns error DriverResponse on hard failure."""
        client = self._get_client()
        probe_payload = {"contents": [{"parts": [{"text": "hi"}]}]}
        for model in self.candidate_models:
            try:
                res = await client.post(self._url(model), json=probe_payload, timeout=15.0)
                if res.status_code == 200:
                    self.active_model = model
                    self.model = model
                    print(f"  [Gemini] Modelo activo: {model}")
                    return None  # success — caller proceeds
                if res.status_code in (401, 403):
                    return self._build_response(
                        content="ERROR:AUTH: Gemini — clave API inválida o sin permisos (GEMINI_API_KEY)",
                        system_prompt=system_prompt,
                        user_message=user_message,
                        latency_start=t0,
                        model_used=model,
                        metadata=metadata,
                    )
                if res.status_code == 429:
                    return self._build_response(
                        content="ERROR:RATE_LIMIT: Gemini — cuota agotada al intentar conectar",
                        system_prompt=system_prompt,
                        user_message=user_message,
                        latency_start=t0,
                        model_used=model,
                        metadata=metadata,
                    )
            except (httpx.ConnectError, httpx.TimeoutException):
                continue
            except Exception:
                continue

        return self._build_response(
            content="ERROR:CONNECTION: Gemini — ningún modelo respondió. Verificá la API key y conexión",
            system_prompt=system_prompt,
            user_message=user_message,
            latency_start=t0,
            model_used=self.candidate_models[0],
            metadata=metadata,
        )

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
                content="ERROR:AUTH: Gemini — GEMINI_API_KEY no configurada",
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=self.active_model or self.candidate_models[0],
                metadata=metadata,
            )

        if not self.active_model:
            async with self._probe_lock:
                if not self.active_model:  # re-check inside lock (another coroutine may have probed)
                    err = await self._probe_models(t0, system_prompt, user_message, metadata)
                    if err is not None:
                        return err

        effective_max = _resolve_gemini_max_tokens(self.active_model, max_tokens)
        gen_config: dict = {"maxOutputTokens": effective_max, "temperature": temperature}
        if response_format == "json":
            gen_config["responseMimeType"] = "application/json"
            # gemini-2.5-flash supports thinkingBudget=0 (disables thinking).
            # gemini-2.5-pro does NOT accept thinkingBudget=0 → 400 BAD_REQUEST.
            # For pro the parts[] parser already skips thought=True parts, so no config needed.
            if "2.5-flash" in (self.active_model or ""):
                gen_config["thinkingConfig"] = {"thinkingBudget": 0}
        # BLOCK_ONLY_HIGH for DANGEROUS_CONTENT: allows legitimate security-related code
        # (JWT blacklists, rate limiting, session invalidation, auth flows) which Gemini's
        # default threshold falsely flags as dangerous content in code-generation contexts.
        # Other categories stay at BLOCK_MEDIUM_AND_ABOVE (default) — no change there.
        safety_settings = [
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
        ]
        payload = {
            "contents": [{"parts": [{"text": f"SYSTEM: {system_prompt}\n\nUSER: {user_message}"}]}],
            "generationConfig": gen_config,
            "safetySettings": safety_settings,
        }
        client = self._get_client()
        try:
            response = await client.post(
                self._url(self.active_model),
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            if response.status_code != 200:
                print(f"  [Gemini] HTTP {response.status_code} — modelo={self.active_model} — body: {response.text[:400]}")
                content = self._classify_http_error(response.status_code, response.text)
                return self._build_response(
                    content=content,
                    system_prompt=system_prompt,
                    user_message=user_message,
                    latency_start=t0,
                    model_used=self.active_model,
                    metadata=metadata,
                )
            res_json = response.json()

            # Check prompt-level block (entire request rejected before generation)
            prompt_feedback = res_json.get("promptFeedback", {})
            if prompt_feedback.get("blockReason"):
                block_reason = prompt_feedback["blockReason"]
                ratings = prompt_feedback.get("safetyRatings", [])
                triggered = [r["category"] for r in ratings if r.get("blocked")]
                detail = f" ({', '.join(triggered)})" if triggered else ""
                return self._build_response(
                    content=f"ERROR:SAFETY_BLOCK: Gemini bloqueó el prompt por política de seguridad — {block_reason}{detail}",
                    system_prompt=system_prompt,
                    user_message=user_message,
                    latency_start=t0,
                    model_used=self.active_model,
                    metadata=metadata,
                )

            candidates = res_json.get("candidates", [])
            if not candidates:
                return self._build_response(
                    content="ERROR:EMPTY_RESPONSE: Gemini devolvió respuesta sin candidatos",
                    system_prompt=system_prompt,
                    user_message=user_message,
                    latency_start=t0,
                    model_used=self.active_model,
                    metadata=metadata,
                )

            candidate = candidates[0]
            finish_reason = candidate.get("finishReason", "")
            if finish_reason in ("SAFETY", "RECITATION", "PROHIBITED_CONTENT", "SPII"):
                ratings = candidate.get("safetyRatings", [])
                triggered = [r["category"] for r in ratings if r.get("blocked")]
                detail = f" ({', '.join(triggered)})" if triggered else ""
                return self._build_response(
                    content=f"ERROR:SAFETY_BLOCK: Gemini bloqueó la respuesta — finishReason={finish_reason}{detail}",
                    system_prompt=system_prompt,
                    user_message=user_message,
                    latency_start=t0,
                    model_used=self.active_model,
                    metadata=metadata,
                )
            if finish_reason == "MAX_TOKENS":
                print(f"  [Gemini] WARN: respuesta cortada por MAX_TOKENS (maxOutputTokens={max_tokens})")

            # Gemini 2.5 Pro (thinking model) returns multiple parts:
            # parts with "thought": true are internal reasoning — skip them.
            # The actual answer is in the first part WITHOUT "thought": true.
            content_block = candidate.get("content", {})
            parts = content_block.get("parts")
            if not parts:
                return self._build_response(
                    content=f"ERROR:EMPTY_RESPONSE: Gemini devolvió candidato sin 'parts' (finishReason={finish_reason or 'unknown'})",
                    system_prompt=system_prompt,
                    user_message=user_message,
                    latency_start=t0,
                    model_used=self.active_model,
                    metadata=metadata,
                )
            content = next(
                (p.get("text", "") for p in parts if not p.get("thought")),
                parts[0].get("text", ""),
            )
            usage = res_json.get("usageMetadata", {})
            in_tokens = usage.get("promptTokenCount")
            out_tokens = usage.get("candidatesTokenCount")
            return self._build_response(
                content=content,
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=self.active_model,
                tokens_input=in_tokens,
                tokens_output=out_tokens,
                metadata=metadata,
            )
        except httpx.ConnectError:
            return self._build_response(
                content="ERROR:CONNECTION: Gemini — sin conexión a internet",
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=self.active_model,
                metadata=metadata,
            )
        except httpx.TimeoutException:
            return self._build_response(
                content="ERROR:TIMEOUT: Gemini — tiempo de espera agotado (>120s)",
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=self.active_model,
                metadata=metadata,
            )
        except Exception as e:
            return self._build_response(
                content=f"ERROR:UNKNOWN: Gemini — {str(e)}",
                system_prompt=system_prompt,
                user_message=user_message,
                latency_start=t0,
                model_used=self.active_model,
                metadata=metadata,
            )

    def prompt(self, system: str, user: str) -> str:
        """Sync wrapper — runs the async call in a new event loop."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already inside an event loop (e.g. FastAPI) — use thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    future = ex.submit(asyncio.run, self.call(system, user))
                    return future.result().content
            return loop.run_until_complete(self.call(system, user)).content
        except RuntimeError:
            return asyncio.run(self.call(system, user)).content
