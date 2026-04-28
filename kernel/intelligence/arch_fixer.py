"""arch_fixer — deterministic post-processor for Gemini-generated architecture.

Fixes common structural mistakes that Gemini makes without requiring a re-call:
- Frontend modules missing dependency on backend API modules.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

_FRONTEND_EXTENSIONS = {".tsx", ".jsx", ".vue", ".svelte"}

_FRONTEND_KEYWORDS = {
    "frontend", "ui", "react", "vue", "angular", "svelte",
    "client", "webapp", "interfaz", "interface", "spa",
}

_BACKEND_API_KEYWORDS = {
    "api", "backend", "routes", "router", "server", "endpoint",
    "servidor", "route", "rest", "graphql", "handlers",
}


def _is_frontend(module: dict) -> bool:
    files = module.get("archivos_principales", [])
    nombre = module.get("nombre", "").lower()
    resp = module.get("responsabilidad", "").lower()
    if any(Path(f).suffix.lower() in _FRONTEND_EXTENSIONS for f in files):
        return True
    return any(kw in nombre or kw in resp for kw in _FRONTEND_KEYWORDS)


def _is_backend_api(module: dict) -> bool:
    if module.get("endpoints"):
        return True
    nombre = module.get("nombre", "").lower()
    resp = module.get("responsabilidad", "").lower()
    return any(kw in nombre or kw in resp for kw in _BACKEND_API_KEYWORDS)


def fix_frontend_backend_deps(architecture: dict) -> dict:
    """Ensure every frontend module declares a dependency on each backend API module.

    Gemini sometimes omits this, causing frontend and backend to land on the
    same DAG level and be generated in parallel — the frontend then has no
    real API paths or schemas to work with.

    This function is deterministic (pure Python, no AI) and runs after Gemini
    returns the architecture JSON, before DependencyGraph consumes it.
    """
    modulos = architecture.get("modulos", [])
    if not modulos:
        return architecture

    valid_names = {m["nombre"] for m in modulos}

    frontend_mods = [m for m in modulos if _is_frontend(m)]
    backend_api_names = [
        m["nombre"] for m in modulos
        if _is_backend_api(m) and not _is_frontend(m) and m["nombre"] in valid_names
    ]

    if not frontend_mods or not backend_api_names:
        return architecture

    fixed_count = 0
    for m in frontend_mods:
        existing = set(m.get("dependencias", []))
        to_add = [b for b in backend_api_names if b not in existing and b != m["nombre"]]
        if to_add:
            m["dependencias"] = sorted(existing | set(to_add))
            fixed_count += len(to_add)
            print(
                f"  [arch_fixer] '{m['nombre']}' deps añadidas: {to_add}"
            )

    if fixed_count:
        print(
            f"  [arch_fixer] {fixed_count} dep(s) frontend->backend corregidas"
        )

    return architecture
