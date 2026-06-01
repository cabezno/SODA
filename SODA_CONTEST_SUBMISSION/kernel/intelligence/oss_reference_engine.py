"""
OSSReferenceEngine — provee snippets de código real de proyectos open source
como referencia para el L4 Coder.

Dos fuentes de referencia:
  1. Cache local curada: skills/base/{skill}/examples/*.py|ts|go
     Pre-poblada con ejemplos reales de repos con >500 stars.
     Sin latencia, sin internet requerido.

  2. GitHub API (opcional): búsqueda dinámica en runtime.
     Requiere GITHUB_TOKEN en .env para 5000 req/h (sin token: 60 req/h).
     Resultados cacheados en workspace/.oss_cache/ para evitar re-búsquedas.
     Fallback silencioso a cache local si falla o hay rate limit.

El snippet más relevante para el módulo actual se inyecta en el prompt L4
como "REFERENCE IMPLEMENTATION" — le da al modelo un ejemplo concreto de
cómo implementar el patrón, en lugar de que interpole desde entrenamiento.

Uso:
    engine = OSSReferenceEngine(notify_fn, github_token)
    snippet = await engine.get_reference(contract, lang, workspace)
    # Retorna string con el snippet de referencia formateado para el prompt
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Optional

# ── Curated examples registry ─────────────────────────────────────────────────
# Maps skill_name → list of (description, relative_path_in_examples_dir)
# These are stored in skills/base/{skill}/examples/
_SKILL_EXAMPLES_REGISTRY: dict[str, list[dict]] = {
    "skill_fastapi": [
        {"desc": "FastAPI router with JWT auth dependency", "file": "auth_router.py"},
        {"desc": "FastAPI SQLAlchemy models and session", "file": "db_session.py"},
        {"desc": "FastAPI Pydantic schemas", "file": "schemas.py"},
    ],
    "skill_jwt_auth": [
        {"desc": "JWT creation and verification (python-jose)", "file": "jwt_handler.py"},
        {"desc": "FastAPI auth dependency (Bearer token)", "file": "auth_dependency.py"},
        {"desc": "JWT middleware Express/Node", "file": "jwt_middleware.ts"},
    ],
    "skill_sqlite": [
        {"desc": "SQLAlchemy models with SQLite", "file": "models_sqlite.py"},
        {"desc": "Alembic migration setup", "file": "alembic_env.py"},
    ],
    "skill_postgresql": [
        {"desc": "SQLAlchemy async engine + session (PostgreSQL)", "file": "db_postgres.py"},
        {"desc": "TypeORM entity + repository pattern", "file": "typeorm_entity.ts"},
    ],
    "skill_mongodb": [
        {"desc": "Mongoose schema + model (TypeScript)", "file": "mongoose_model.ts"},
        {"desc": "Motor async MongoDB (Python)", "file": "motor_client.py"},
    ],
    "skill_rest_api": [
        {"desc": "Express.js REST router with error handling", "file": "express_router.ts"},
        {"desc": "FastAPI CRUD endpoints", "file": "fastapi_crud.py"},
    ],
    "skill_nodejs": [
        {"desc": "Express app entry point with middleware", "file": "express_app.ts"},
        {"desc": "Express error handler middleware", "file": "error_handler.ts"},
    ],
    "skill_nestjs": [
        {"desc": "NestJS module + controller + service", "file": "nestjs_module.ts"},
        {"desc": "NestJS JWT guard", "file": "nestjs_jwt_guard.ts"},
    ],
    "skill_nextjs": [
        {"desc": "Next.js API route handler", "file": "nextjs_api_route.ts"},
        {"desc": "Next.js middleware auth check", "file": "nextjs_middleware.ts"},
        {"desc": "Next.js App Router layout with sidebar + responsive mobile drawer", "file": "app_layout.tsx"},
    ],
    "skill_react": [
        {"desc": "React component with API fetch + error handling", "file": "react_fetch_component.tsx"},
        {"desc": "React context + custom hook", "file": "react_context_hook.tsx"},
        {"desc": "Production dashboard: KPI cards, sortable data table, sidebar nav, top bar", "file": "dashboard_components.tsx"},
        {"desc": "Landing page: hero + features grid + testimonials + pricing + CTA", "file": "landing_hero.tsx"},
    ],
    "skill_docker": [
        {"desc": "Dockerfile for Node.js app", "file": "dockerfile_node"},
        {"desc": "Dockerfile for Python FastAPI", "file": "dockerfile_python"},
    ],
    "skill_golang": [
        {"desc": "Go HTTP handler with middleware", "file": "go_handler.go"},
        {"desc": "Go database/sql pattern", "file": "go_db.go"},
    ],
    "skill_typescript": [
        {"desc": "TypeScript service class pattern", "file": "ts_service.ts"},
        {"desc": "TypeScript DTO validation", "file": "ts_dto.ts"},
    ],
    "skill_vue": [
        {"desc": "Vue 3 Composition API component", "file": "vue_component.vue"},
        {"desc": "Production Vue 3 dashboard: KPI cards, data table, sidebar nav, pagination", "file": "vue_dashboard.vue"},
    ],
    "skill_react_native": [
        {"desc": "React Native screen with navigation", "file": "rn_screen.tsx"},
    ],
    "skill_cpp_cmake": [
        {"desc": "REST API server with cpp-httplib, JSON responses, CORS, error handling", "file": "http_handler.cpp"},
        {"desc": "Modern C++20 domain model: RAII, smart pointers, repository pattern, validation", "file": "data_model.hpp"},
        {"desc": "Win32 desktop window with message loop, WM_PAINT, button handler", "file": "win32_app.cpp"},
    ],
}

# ── GitHub search queries per skill ───────────────────────────────────────────
_SKILL_GITHUB_QUERIES: dict[str, str] = {
    "skill_fastapi":    "fastapi jwt authentication router language:Python stars:>500",
    "skill_jwt_auth":   "jwt authentication middleware language:TypeScript stars:>500",
    "skill_sqlite":     "sqlalchemy sqlite models fastapi language:Python stars:>200",
    "skill_postgresql": "sqlalchemy postgresql async session language:Python stars:>200",
    "skill_mongodb":    "mongoose typescript model schema language:TypeScript stars:>500",
    "skill_rest_api":   "express rest api router middleware language:TypeScript stars:>500",
    "skill_nodejs":     "express typescript app middleware language:TypeScript stars:>500",
    "skill_nestjs":     "nestjs module controller service language:TypeScript stars:>500",
    "skill_nextjs":     "nextjs api route authentication language:TypeScript stars:>500",
    "skill_react":      "react hooks context api fetch language:TypeScript stars:>500",
    "skill_golang":     "golang http handler middleware language:Go stars:>500",
    "skill_typescript": "typescript service class dependency injection language:TypeScript stars:>500",
}


class OSSReferenceEngine:
    """
    Provides real open-source code snippets as reference for L4 code generation.
    Uses local curated cache first, falls back to GitHub API if available.
    """

    # Cap snippet size for injection into L4 prompt
    _SNIPPET_CAP_SMALL = 400   # chars for Qwen/small models
    _SNIPPET_CAP_LARGE = 1200  # chars for Claude/Gemini

    def __init__(
        self,
        notify_fn: Optional[Callable] = None,
        github_token: Optional[str] = None,
        skills_base_dir: Optional[Path] = None,
    ):
        self.notify = notify_fn or (lambda msg, lvl="LOG", *a, **kw: None)
        self.github_token = github_token
        self._skills_base = skills_base_dir or (
            Path(__file__).resolve().parent.parent.parent / "skills" / "base"
        )

    def _notify(self, msg: str, level: str = "LOG") -> None:
        try:
            self.notify(level, msg)
        except Exception:
            pass

    # ── Local cache ───────────────────────────────────────────────────────────

    def _get_local_snippet(self, skill: str, contract_description: str) -> Optional[str]:
        """
        Find the most relevant local example for a skill.
        Returns the file content capped to _SNIPPET_CAP_LARGE chars.
        """
        examples_dir = self._skills_base / skill / "examples"
        if not examples_dir.exists():
            return None

        registry_entries = _SKILL_EXAMPLES_REGISTRY.get(skill, [])
        if not registry_entries:
            # No registry — just return the first .py/.ts file found
            for f in sorted(examples_dir.iterdir()):
                if f.is_file() and f.suffix in {".py", ".ts", ".tsx", ".go", ".vue", ""}:
                    try:
                        return f.read_text(encoding="utf-8", errors="ignore")[:self._SNIPPET_CAP_LARGE]
                    except Exception:
                        pass
            return None

        # Find best matching example by description similarity
        desc_lower = contract_description.lower()
        best: Optional[Path] = None
        best_score = -1

        for entry in registry_entries:
            fpath = examples_dir / entry["file"]
            if not fpath.exists():
                continue
            # Simple keyword overlap score
            keywords = set(re.findall(r'\w+', entry["desc"].lower()))
            score = sum(1 for kw in keywords if kw in desc_lower)
            if score > best_score:
                best_score = score
                best = fpath

        # Fallback: just use the first available file
        if best is None:
            for entry in registry_entries:
                fpath = examples_dir / entry["file"]
                if fpath.exists():
                    best = fpath
                    break

        if best is None:
            return None

        try:
            content = best.read_text(encoding="utf-8", errors="ignore")
            return f"# Source: {best.name} (curated example)\n{content}"
        except Exception:
            return None

    # ── GitHub API ────────────────────────────────────────────────────────────

    async def _github_search(
        self,
        skill: str,
        description: str,
        workspace: Optional[Path],
    ) -> Optional[str]:
        """
        Search GitHub for a relevant file and return its content.
        Results are cached in workspace/.oss_cache/ to avoid repeat calls.
        """
        if not self.github_token:
            return None

        query = _SKILL_GITHUB_QUERIES.get(skill)
        if not query:
            return None

        # Check cache
        cache_key = hashlib.md5(f"{skill}:{description[:50]}".encode()).hexdigest()[:12]
        if workspace:
            cache_dir = workspace / ".oss_cache"
            cache_dir.mkdir(exist_ok=True)
            cache_file = cache_dir / f"{cache_key}.txt"
            if cache_file.exists():
                try:
                    return cache_file.read_text(encoding="utf-8")
                except Exception:
                    pass

        try:
            import httpx
        except ImportError:
            try:
                import urllib.request as _urllib
            except Exception:
                return None
            # Fallback to urllib if httpx not available
            return await self._github_search_urllib(skill, query, cache_key, workspace)

        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "SODA-OSSReference/1.0",
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                # Search for repos
                search_url = "https://api.github.com/search/code"
                params = {"q": query, "per_page": 3, "sort": "indexed"}
                resp = await client.get(search_url, headers=headers, params=params)

                if resp.status_code == 403:
                    self._notify("[OSSRef] GitHub rate limit reached — usando cache local.", "WARNING")
                    return None
                if resp.status_code != 200:
                    return None

                items = resp.json().get("items", [])
                if not items:
                    return None

                # Fetch first file's raw content
                raw_url = items[0].get("html_url", "").replace(
                    "github.com", "raw.githubusercontent.com"
                ).replace("/blob/", "/")
                if not raw_url:
                    return None

                raw_resp = await client.get(raw_url, headers=headers, timeout=6.0)
                if raw_resp.status_code != 200:
                    return None

                content = raw_resp.text[:self._SNIPPET_CAP_LARGE]
                repo_name = items[0].get("repository", {}).get("full_name", "unknown")
                result = f"# Source: github.com/{repo_name}\n{content}"

                # Save to cache
                if workspace:
                    try:
                        cache_file.write_text(result, encoding="utf-8")
                    except Exception:
                        pass

                return result

        except Exception as e:
            self._notify(f"[OSSRef] GitHub search failed: {e}", "WARNING")
            return None

    async def _github_search_urllib(
        self,
        skill: str,
        query: str,
        cache_key: str,
        workspace: Optional[Path],
    ) -> Optional[str]:
        """Fallback GitHub search using urllib (no httpx dependency)."""
        import urllib.request
        import urllib.parse
        import urllib.error

        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "SODA-OSSReference/1.0",
        }

        try:
            params = urllib.parse.urlencode({"q": query, "per_page": 3})
            url = f"https://api.github.com/search/code?{params}"
            req = urllib.request.Request(url, headers=headers)

            def _fetch():
                with urllib.request.urlopen(req, timeout=8) as r:
                    return json.loads(r.read().decode())

            data = await asyncio.get_event_loop().run_in_executor(None, _fetch)
            items = data.get("items", [])
            if not items:
                return None

            raw_url = items[0].get("html_url", "").replace(
                "github.com", "raw.githubusercontent.com"
            ).replace("/blob/", "/")
            if not raw_url:
                return None

            raw_req = urllib.request.Request(raw_url, headers=headers)
            def _fetch_raw():
                with urllib.request.urlopen(raw_req, timeout=6) as r:
                    return r.read().decode("utf-8", errors="ignore")

            content = await asyncio.get_event_loop().run_in_executor(None, _fetch_raw)
            content = content[:self._SNIPPET_CAP_LARGE]
            repo_name = items[0].get("repository", {}).get("full_name", "unknown")
            result = f"# Source: github.com/{repo_name}\n{content}"

            if workspace:
                try:
                    cache_dir = workspace / ".oss_cache"
                    cache_dir.mkdir(exist_ok=True)
                    (cache_dir / f"{cache_key}.txt").write_text(result, encoding="utf-8")
                except Exception:
                    pass

            return result

        except Exception:
            return None

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_reference(
        self,
        contract: Any,
        lang: str,
        workspace: Optional[Path] = None,
        is_small_model: bool = False,
    ) -> str:
        """
        Retorna un snippet de referencia formateado para inyectar en el prompt L4.
        Prioridad: cache local → GitHub API → ""

        El snippet se capea según el modelo:
          - small models (Qwen): 400 chars
          - cloud models (Claude/Gemini): 1200 chars
        """
        cap = self._SNIPPET_CAP_SMALL if is_small_model else self._SNIPPET_CAP_LARGE

        contract_skills = list(
            getattr(getattr(contract, "dynamic_persona", None), "required_skills", None) or []
        )
        description = str(getattr(contract, "description", "") or "")
        title = str(getattr(contract, "title", "") or "")
        combined_desc = f"{title} {description}".strip()

        snippet: Optional[str] = None
        source_skill: Optional[str] = None

        # Try each skill in order until we find a snippet
        for skill in contract_skills:
            local = self._get_local_snippet(skill, combined_desc)
            if local:
                snippet = local
                source_skill = skill
                break

        # If no local snippet, try GitHub API (async, non-blocking)
        if not snippet and self.github_token:
            for skill in contract_skills:
                if skill in _SKILL_GITHUB_QUERIES:
                    gh = await self._github_search(skill, combined_desc, workspace)
                    if gh:
                        snippet = gh
                        source_skill = skill
                        break

        if not snippet:
            return ""

        # Cap to size limit
        if len(snippet) > cap:
            snippet = snippet[:cap] + "\n... (truncated)"

        return (
            f"## REFERENCE IMPLEMENTATION — follow this pattern\n"
            f"# Skill: {source_skill} | Language: {lang}\n"
            f"# Use this as a structural reference. Adapt imports to the project structure above.\n\n"
            f"{snippet}\n"
        )


# ── Singleton factory ─────────────────────────────────────────────────────────

_engine_instance: Optional[OSSReferenceEngine] = None


def get_oss_engine(
    notify_fn: Optional[Callable] = None,
    github_token: Optional[str] = None,
    skills_base_dir: Optional[Path] = None,
) -> OSSReferenceEngine:
    """
    Returns a shared OSSReferenceEngine instance.
    Call once with token; subsequent calls reuse the instance.
    """
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = OSSReferenceEngine(
            notify_fn=notify_fn,
            github_token=github_token,
            skills_base_dir=skills_base_dir,
        )
    return _engine_instance
