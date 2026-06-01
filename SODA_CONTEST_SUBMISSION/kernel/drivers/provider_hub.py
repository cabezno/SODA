from __future__ import annotations

import asyncio
from typing import Dict, List, Optional


DEFAULT_ROUTES = {
    "claude": ["claude", "gemini", "openai", "ollama"],
    "gemini": ["gemini", "openai", "ollama"],
    "ollama": ["ollama", "gemini", "openai"],
    "openai": ["openai", "gemini", "ollama"],
}


class AIProviderHub:
    """Registry and fallback routing for AI providers."""

    def __init__(self, providers: Optional[Dict[str, object]] = None, routes: Optional[Dict[str, List[str]]] = None):
        self._providers: Dict[str, object] = dict(providers or {})
        self._routes: Dict[str, List[str]] = dict(DEFAULT_ROUTES)
        self.blackbox = None
        if routes:
            for key, chain in routes.items():
                self._routes[key] = list(chain)

    def register(self, name: str, provider: object) -> None:
        self._providers[name] = provider

    def get(self, name: str) -> Optional[object]:
        driver = self._get_raw_driver(name)
        if driver and self.blackbox:
            # FIX: Evitar doble wrapping si el driver ya es un AIProxy
            if isinstance(driver, AIProxy):
                return driver
            # Si el driver es un ModelLockedProxy que envuelve un AIProxy, también lo evitamos.
            if hasattr(driver, '_target') and isinstance(getattr(driver, '_target', None), AIProxy):
                # Ya está envuelto en el interior, no añadir otra capa de AIProxy por fuera.
                return driver
                
            return AIProxy(driver, name, self.blackbox)
        return driver

    def _get_raw_driver(self, name: str) -> Optional[object]:
        if name in self._providers:
            return self._providers[name]

        name_lower = name.lower()

        # Specific model names (e.g. "gemini-3-flash-preview") — return a ModelLockedProxy
        # so the driver is guaranteed to use exactly that model, not its default.
        if "gemini" in name_lower and "gemini" in self._providers:
            base = self._providers["gemini"]
            # Only wrap when the caller asked for a specific model (not just "gemini")
            return ModelLockedProxy(base, name) if name_lower != "gemini" else base
        if "claude" in name_lower and "claude" in self._providers:
            base = self._providers["claude"]
            return ModelLockedProxy(base, name) if name_lower != "claude" else base
        if "deepseek" in name_lower and "deepseek" in self._providers:
            base = self._providers["deepseek"]
            return ModelLockedProxy(base, name) if name_lower != "deepseek" else base
        if ("openai" in name_lower or "gpt-" in name_lower) and "openai" in self._providers:
            base = self._providers["openai"]
            return ModelLockedProxy(base, name) if name_lower not in ("openai",) else base

        # Qwen / Llama / Mistral / cualquier modelo local → OllamaDriver
        if ("qwen" in name_lower or "llama" in name_lower or "mistral" in name_lower or "phi" in name_lower) and "ollama" in self._providers:
            return self._providers["ollama"]

        return None

    async def call_with_fallback(
        self, 
        primary: str, 
        role: str, 
        task: str, 
        project=None,
        **kwargs
    ) -> str:
        route = self.get_chain(primary)
        
        last_error = None
        for provider_name in route:
            try:
                driver = self.get(provider_name)
                if not driver: continue
                
                print(f"  [Hub] Intentando con proveedor: {provider_name} (Rol: {role})")
                
                if hasattr(driver, 'call'):
                    resp = await driver.call(system_prompt=f"Role: {role}. Phase: {kwargs.get('phase', 'unknown')}", user_message=task)
                    content = resp.content if hasattr(resp, 'content') else str(resp)
                else:
                    content = await driver.prompt(system=f"Role: {role}. Phase: {kwargs.get('phase', 'unknown')}", user=task)

                if isinstance(content, str) and content.startswith("ERROR:"):
                    raise ValueError(f"Provider returned error content: {content}")
                return content
            except Exception as e:
                last_error = e
                print(f"  [Hub] FALLO en {provider_name}: {str(e)}")
                if self.blackbox:
                    self.blackbox.log_event(
                        "PROVIDER_FAILOVER", 
                        f"Fallo en {provider_name}, saltando al siguiente...",
                        {"error": str(e), "role": role}
                    )
                continue
                
        print(f"  [Hub] CRÍTICO: Todos los proveedores fallaron para la tarea de {role}.")
        raise last_error or Exception(f"No se pudo completar la tarea con ningún proveedor.")

    def available(self) -> List[str]:
        return sorted(self._providers.keys())

    def get_chain(self, primary: str) -> List[str]:
        configured = self._routes.get(primary) or [primary]
        deduped = []
        seen = set()
        for name in configured:
            if name in self._providers and name not in seen:
                deduped.append(name)
                seen.add(name)

        if primary in self._providers and primary not in seen:
            deduped.insert(0, primary)
            seen.add(primary)

        for name in self.available():
            if name not in seen:
                deduped.append(name)
        return deduped


class ModelLockedProxy:
    """
    Guarantees that a driver uses exactly the requested model.
    Solves the 'routing illusion' where hub.get('gemini-3.1-pro-preview')
    returned a GeminiDriver that silently used its default model instead.
    """

    def __init__(self, target, model_name: str):
        self._target = target
        self._model_name = model_name

    async def call(self, **kwargs) -> object:
        kwargs["model"] = self._model_name  # enforced — always
        return await self._target.call(**kwargs)

    async def prompt(self, system: str, user: str) -> str:
        if hasattr(self._target, "prompt"):
            # Re-route through call so the model is locked
            resp = await self.call(system_prompt=system, user_message=user)
            return resp.content if hasattr(resp, "content") else str(resp)
        resp = await self.call(system_prompt=system, user_message=user)
        return resp.content if hasattr(resp, "content") else str(resp)

    def __getattr__(self, name: str):
        return getattr(self._target, name)


class AIProxy:
    """Proxy que intercepta llamadas al driver para loguear comunicación profunda."""
    MAX_RETRIES = 5
    BASE_BACKOFF = 2.0  # segundos

    def __init__(self, target, model_name, logger):
        self._target = target
        self._model_name = model_name
        self._logger = logger

    async def _call_with_retry(self, **kwargs):
        """Ejecuta call() con retry exponencial ante rate limits o errores transitorios."""
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                return await self._target.call(**kwargs)
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                is_retryable = (
                    "429" in err_str
                    or "rate" in err_str
                    or "timeout" in err_str
                    or "too many" in err_str
                    or "service unavailable" in err_str
                    or "503" in err_str
                    or "502" in err_str
                    or "connection" in err_str
                    or "reset" in err_str
                )
                if not is_retryable or attempt == self.MAX_RETRIES - 1:
                    raise
                wait = self.BASE_BACKOFF * (2 ** attempt)
                if self._logger:
                    self._logger.log(
                        f"[AIProxy] Rate limit/error en {self._model_name} "
                        f"(intento {attempt+1}/{self.MAX_RETRIES}). "
                        f"Esperando {wait:.0f}s... Error: {e}"
                    )
                await asyncio.sleep(wait)
        # Shouldn't reach here, but just in case
        raise last_error or RuntimeError(f"All {self.MAX_RETRIES} retries failed")

    async def call(self, **kwargs):
        provider = type(self._target).__name__
        prompt = kwargs.get("user_message", "")
        system = kwargs.get("system_prompt", "")
        full_prompt = f"SYSTEM: {system}\nUSER: {prompt}"
        
        try:
            response = await self._call_with_retry(**kwargs)
            if self._logger:
                meta = kwargs.get("metadata", {}).copy()
                if hasattr(response, "tokens_input"):
                    meta["tokens_input"] = response.tokens_input
                    meta["tokens_output"] = response.tokens_output
                    meta["latency_ms"] = getattr(response, "latency_ms", 0)
                
                self._logger.log_ai_communication(
                    provider=provider,
                    model=self._model_name,
                    prompt=full_prompt,
                    response=response.content if hasattr(response, "content") else str(response),
                    metadata=meta
                )
            return response
        except Exception as e:
            if self._logger:
                self._logger.log_ai_communication(
                    provider=provider,
                    model=self._model_name,
                    prompt=full_prompt,
                    response=f"ERROR: {str(e)}",
                    metadata=kwargs.get("metadata", {})
                )
            raise e

    async def prompt(self, system: str, user: str, **kwargs) -> str:
        # SODA FUSION: Ensure consistent logging for both 'call' and 'prompt' routes
        try:
            if hasattr(self._target, "prompt"):
                # Pass kwargs down to the target prompt if it supports them
                content = await self._target.prompt(system, user, **kwargs)
            else:
                # Fallback to call
                resp = await self.call(system_prompt=system, user_message=user, **kwargs)
                content = resp.content if hasattr(resp, "content") else str(resp)

            if self._logger:
                self._logger.log_ai_communication(
                    provider=type(self._target).__name__,
                    model=self._model_name,
                    prompt=f"SYSTEM: {system}\nUSER: {user}",
                    response=content,
                    metadata=kwargs.get("metadata", {})
                )
            return content
        except Exception as e:
            if self._logger:
                 self._logger.log_ai_communication(
                    provider=type(self._target).__name__,
                    model=self._model_name,
                    prompt=f"SYSTEM: {system}\nUSER: {user}",
                    response=f"ERROR: {str(e)}",
                    metadata=kwargs.get("metadata", {})
                )
            raise e

    def __getattr__(self, name):
        return getattr(self._target, name)
