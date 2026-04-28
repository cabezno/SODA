from __future__ import annotations

from typing import Dict, List, Optional


DEFAULT_ROUTES = {
    "claude": ["claude", "gemini", "openai", "ollama"],
    "gemini": ["gemini", "claude", "openai", "ollama"],
    "ollama": ["ollama", "claude", "gemini", "openai"],
    "openai": ["openai", "claude", "gemini", "ollama"],
}


class AIProviderHub:
    """Registry and fallback routing for AI providers.

    It centralizes provider availability and fallback order so the orchestrator
    can add/remove providers without hardcoded chains everywhere.
    """

    def __init__(self, providers: Optional[Dict[str, object]] = None, routes: Optional[Dict[str, List[str]]] = None):
        self._providers: Dict[str, object] = dict(providers or {})
        self._routes: Dict[str, List[str]] = dict(DEFAULT_ROUTES)
        if routes:
            for key, chain in routes.items():
                self._routes[key] = list(chain)

    def register(self, name: str, provider: object) -> None:
        self._providers[name] = provider

    def get(self, name: str) -> Optional[object]:
        return self._providers.get(name)

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
