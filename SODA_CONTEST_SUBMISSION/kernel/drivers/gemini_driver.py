from __future__ import annotations

import asyncio
import os
import re
import json
from pathlib import Path
from time import perf_counter

import httpx
from dotenv import load_dotenv

from kernel.drivers.base import BaseDriver, DriverResponse

# Maximum output tokens per Gemini model variant
_GEMINI_MODEL_MAX_TOKENS: dict[str, int] = {
    "gemini-3.5-flash": 16384,
    "gemini-3.1-pro-preview": 8192,
    "gemini-3-flash-preview": 8192,
    "gemini-3.1-flash-lite-preview": 8192,
    "gemini-2.5-pro": 8192,
    "gemini-2.5-flash": 8192,
    "gemini-1.5-pro": 8192,
    "gemini-1.5-flash": 8192,
}
_GEMINI_FALLBACK_MAX = 8192


def _resolve_gemini_max_tokens(model: str | None, requested: int) -> int:
    """Upgrade driver default (4096) to model-appropriate limit; preserve explicit small values."""
    model_limit = _GEMINI_MODEL_MAX_TOKENS.get(model or "", _GEMINI_FALLBACK_MAX)
    if requested <= 4096:
        return model_limit
    return min(requested, model_limit)


class GeminiDriver(BaseDriver):
    provider = "gemini"

    # All available Gemini models - Verified for 2026 environment
    ALL_MODELS = [
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ]

    def __init__(self):
        load_dotenv()
        self.api_keys = [
            os.getenv("GEMINI_API_KEY"),
            os.getenv("GEMINI_API_KEY_2"),
            os.getenv("GEMINI-2.5-FLASH_API_KEY"),
        ]
        self.api_keys = [k for k in self.api_keys if k]
        self.current_key_index = 0
        self.active_model = None
        self._http = None
        self._probe_lock = asyncio.Lock()
        
        # We start with all models as candidates
        self.candidate_models = list(self.ALL_MODELS)

    def _rotate_key(self):
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        print(f"  [Gemini] Rotando a API Key index: {self.current_key_index}")

    def _url(self, model: str) -> str:
        key = self.api_keys[self.current_key_index]
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

    def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(240.0, connect=15.0))
        return self._http

    async def call(
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
    ) -> DriverResponse:
        t0 = perf_counter()

        # --- ESTRATEGIA CERO FALLOS CON TELEMETRÍA ---
        models_to_try = [model] if (model and model in self.ALL_MODELS) else self.candidate_models
        
        for target_model in models_to_try:
            for key_attempt in range(len(self.api_keys)):
                effective_max = _resolve_gemini_max_tokens(target_model, max_tokens)
                gen_config: dict = {
                    "maxOutputTokens": effective_max, 
                    "temperature": temperature,
                    "topP": top_p,
                    "topK": top_k
                }
                if response_format == "json":
                    gen_config["responseMimeType"] = "application/json"
                    if response_schema is not None:
                        gen_config["responseSchema"] = response_schema
                
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"},
                ]
                
                payload = {
                    "contents": [{"parts": [{"text": user_message}]}],
                    "generationConfig": gen_config,
                    "safetySettings": safety_settings,
                }
                if system_prompt:
                    payload["system_instruction"] = {"parts": [{"text": system_prompt}]}
                
                client = self._get_client()

                try:
                    print(f"  [Gemini] Intentando {target_model} (Key {self.current_key_index})...")
                    response = await client.post(
                        self._url(target_model),
                        headers={"Content-Type": "application/json"},
                        json=payload,
                    )
                    
                    if response.status_code == 200:
                        print(f"  [Gemini] OK: {target_model} respondió correctamente.")
                        self.active_model = target_model
                        res_json = response.json()
                        candidates = res_json.get("candidates", [])
                        if not candidates:
                            print(f"  [Gemini] WARN: Respuesta vacía de {target_model}")
                            continue

                        candidate = candidates[0]
                        content_block = candidate.get("content", {})
                        parts = content_block.get("parts", [])
                        texts = [p.get("text", "") for p in parts if not p.get("thought")]
                        content = "".join(texts).strip()
                        
                        usage = res_json.get("usageMetadata", {})
                        return self._build_response(
                            content=content,
                            system_prompt=system_prompt,
                            user_message=user_message,
                            latency_start=t0,
                            model_used=target_model,
                            tokens_input=usage.get("promptTokenCount"),
                            tokens_output=usage.get("candidatesTokenCount"),
                            metadata=metadata,
                        )
                    
                    # Log de error visible
                    print(f"  [Gemini] ERROR {response.status_code} en {target_model}")
                    print(f"  ↳ Detalle: {response.text[:200]}...")
                    
                    # Freno de seguridad obligatorio
                    await asyncio.sleep(2)

                    if response.status_code in (429, 503):
                        self._rotate_key()
                        continue
                    
                    # Para otros errores (400, etc), pasamos al siguiente modelo
                    break 

                except Exception as e:
                    print(f"  [Gemini] Excepción: {str(e)}")
                    await asyncio.sleep(2)
                    self._rotate_key()
                    continue

        return self._build_response(
            content=f"ERROR:EXHAUSTED: Se agotaron todos los modelos ({len(models_to_try)}) y llaves.",
            system_prompt=system_prompt,
            user_message=user_message,
            latency_start=t0,
            model_used=models_to_try[0],
            metadata=metadata
        )

    def _build_response(self, **kwargs) -> DriverResponse:
        t1 = perf_counter()
        latency_seconds = t1 - kwargs.get("latency_start", t1)
        
        # Calcular costo estimado (heurística rápida si no hay tracker)
        tokens_in = kwargs.get("tokens_input") or 0
        tokens_out = kwargs.get("tokens_output") or 0
        cost = (tokens_in * 0.00000015) + (tokens_out * 0.0000006)
        
        return DriverResponse(
            content=kwargs.get("content", ""),
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            latency_ms=int(latency_seconds * 1000),
            model_used=kwargs.get("model_used", "unknown"),
            cost_usd=cost,
            error_code=None if "ERROR:" not in kwargs.get("content", "") else kwargs.get("content", "").split(":")[1],
            metadata=kwargs.get("metadata", {})
        )

    async def prompt(self, system: str, user: str, **kwargs) -> str:
        response = await self.call(system, user, **kwargs)
        return response.content
