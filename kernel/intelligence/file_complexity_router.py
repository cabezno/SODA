"""FileComplexityRouter — C: Dynamic Model Router.

Classifies each file BEFORE generation to determine the optimal starting
model. Complex files skip Qwen's 3 retry rounds entirely and go directly
to a cloud model, saving tokens and latency on predictably hard files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

Complexity = Literal["simple", "medium", "complex"]

# Keywords in filepath or module name that signal complexity
_COMPLEX_KEYWORDS: frozenset[str] = frozenset({
    "auth", "jwt", "oauth", "token", "session", "permission", "rbac",
    "crypto", "encrypt", "hash", "sign",
    "payment", "stripe", "billing", "invoice", "subscription",
    "webhook", "socket", "websocket", "realtime", "pubsub",
    "migration", "schema", "seed", "transaction",
    "middleware", "gateway", "proxy", "interceptor",
    "provider", "factory", "registry",
    "orchestrat", "pipeline", "workflow",
})

_MEDIUM_KEYWORDS: frozenset[str] = frozenset({
    "service", "controller", "router", "repository", "store",
    "model", "entity", "dao", "api", "endpoint",
    "config", "settings", "env",
    "cache", "queue", "worker", "task",
    "validator", "serializer", "transformer",
    "context", "reducer", "action",
})

# Extensions that are inherently complex
_COMPLEX_EXTENSIONS: frozenset[str] = frozenset({".sql"})
_MEDIUM_EXTENSIONS: frozenset[str] = frozenset({".ts", ".tsx", ".go", ".rs"})

# Module names that are always complex regardless of file
_COMPLEX_MODULE_NAMES: frozenset[str] = frozenset({
    "autenticación", "authentication", "seguridad", "security",
    "pagos", "payments", "facturación",
    "api de transporte", "api gateway",
})


class FileComplexityRouter:
    """Pure-Python classifier — zero API calls.

    Returns a Complexity level for each file. The orchestrator uses this
    to skip Qwen for complex files and start directly with a cloud model.
    """

    def classify(self, filepath: str, module: dict) -> Complexity:
        path_lower = filepath.lower()
        stem_lower = Path(filepath).stem.lower()
        module_name = (module.get("nombre") or module.get("name") or "").lower()
        responsibility = (module.get("responsabilidad") or "").lower()

        # Fast path: module name is an exact complex match
        for name in _COMPLEX_MODULE_NAMES:
            if name in module_name:
                return "complex"

        # Score based on keyword matches
        combined = f"{path_lower} {stem_lower} {module_name} {responsibility}"
        complex_hits = sum(1 for kw in _COMPLEX_KEYWORDS if kw in combined)
        medium_hits  = sum(1 for kw in _MEDIUM_KEYWORDS  if kw in combined)

        ext = Path(filepath).suffix.lower()

        if ext in _COMPLEX_EXTENSIONS or complex_hits >= 2:
            return "complex"
        if complex_hits == 1 or medium_hits >= 2 or ext in _MEDIUM_EXTENSIONS:
            return "medium"
        return "simple"

    def effective_levels(self, complexity: Complexity, base_levels: list[str]) -> list[str]:
        """Return the escalation level list adjusted for the file's complexity.

        - simple:  use the base list as-is (starts with Qwen)
        - medium:  skip Qwen, start from Gemini
        - complex: skip Qwen + Gemini, start directly from Gemini
        """
        if complexity == "simple":
            return base_levels
        if complexity == "medium":
            return [l for l in base_levels if l != "qwen"]
        # complex: Gemini only
        return [l for l in base_levels if l == "gemini"]
