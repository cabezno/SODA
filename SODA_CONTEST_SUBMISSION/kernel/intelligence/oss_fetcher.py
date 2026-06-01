"""
OSSFetcher — herramienta one-time para poblar el cache local de ejemplos
descargando código real desde GitHub.

Busca repositorios de alta calidad (>500 stars) para cada skill registrada,
descarga los archivos más relevantes, y los guarda en:
    skills/base/{skill}/examples/github_{filename}

Se ejecuta manualmente o al instalar una nueva skill:
    python -m kernel.intelligence.oss_fetcher --skills skill_fastapi skill_jwt_auth
    python -m kernel.intelligence.oss_fetcher --all

Requiere GITHUB_TOKEN en .env para evitar rate limits.
Sin token: 60 req/h (suficiente para ~5 skills). Con token: 5000 req/h.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# ── Targets: (query, filename_hint, repo_path_hint) ──────────────────────────
# repo_path_hint: substring to match in the GitHub file path for quality filtering
_FETCH_TARGETS: dict[str, list[dict]] = {
    "skill_fastapi": [
        {
            "query": "fastapi router jwt depends language:Python",
            "hint": "router",
            "filename": "github_auth_router.py",
        },
        {
            "query": "fastapi sqlalchemy session generator language:Python",
            "hint": "database",
            "filename": "github_database.py",
        },
    ],
    "skill_jwt_auth": [
        {
            "query": "jose jwt encode decode python-jose language:Python",
            "hint": "auth",
            "filename": "github_jwt_python.py",
        },
        {
            "query": "jsonwebtoken verify Bearer middleware language:TypeScript",
            "hint": "middleware",
            "filename": "github_jwt_ts.ts",
        },
    ],
    "skill_nodejs": [
        {
            "query": "express typescript app middleware cors helmet language:TypeScript",
            "hint": "app",
            "filename": "github_express_app.ts",
        },
    ],
    "skill_nestjs": [
        {
            "query": "nestjs module controller service injectable language:TypeScript",
            "hint": "module",
            "filename": "github_nestjs_module.ts",
        },
    ],
    "skill_nextjs": [
        {
            "query": "nextjs app router api route handler language:TypeScript",
            "hint": "route",
            "filename": "github_nextjs_route.ts",
        },
    ],
    "skill_react": [
        {
            "query": "react hooks fetch useEffect useState error language:TypeScript",
            "hint": "component",
            "filename": "github_react_component.tsx",
        },
    ],
    "skill_mongodb": [
        {
            "query": "mongoose schema model typescript interface language:TypeScript",
            "hint": "model",
            "filename": "github_mongoose_model.ts",
        },
    ],
    "skill_postgresql": [
        {
            "query": "sqlalchemy asyncpg async session postgresql language:Python",
            "hint": "database",
            "filename": "github_db_postgres.py",
        },
    ],
    "skill_sqlite": [
        {
            "query": "sqlalchemy sqlite sessionmaker Base language:Python",
            "hint": "model",
            "filename": "github_models.py",
        },
    ],
    "skill_golang": [
        {
            "query": "golang http handler middleware json encode language:Go",
            "hint": "handler",
            "filename": "github_handler.go",
        },
    ],
    "skill_typescript": [
        {
            "query": "typescript service class interface dto language:TypeScript",
            "hint": "service",
            "filename": "github_service.ts",
        },
    ],
}

_SKILLS_BASE = Path(__file__).resolve().parent.parent.parent / "skills" / "base"
_SNIPPET_CAP = 1500  # max chars per fetched file


async def _fetch_one(
    skill: str,
    target: dict,
    token: str,
    session,
) -> Optional[str]:
    """Fetch one file from GitHub matching the target query. Returns file content or None."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "SODA-OSSFetcher/1.0",
    }

    search_url = "https://api.github.com/search/code"
    params = {"q": target["query"], "per_page": 5, "sort": "indexed"}

    try:
        resp = await session.get(search_url, headers=headers, params=params, timeout=10.0)

        if resp.status_code == 403:
            print(f"  [!] Rate limit reached. Wait 60s or add GITHUB_TOKEN.")
            return None
        if resp.status_code != 200:
            print(f"  [!] Search failed: HTTP {resp.status_code}")
            return None

        items = resp.json().get("items", [])
        if not items:
            print(f"  [~] No results for: {target['query'][:60]}")
            return None

        # Pick the best match: prefers items where path contains the hint
        hint = target.get("hint", "")
        best = next(
            (i for i in items if hint in i.get("path", "").lower()),
            items[0]
        )

        raw_url = (
            best.get("html_url", "")
            .replace("github.com", "raw.githubusercontent.com")
            .replace("/blob/", "/")
        )
        if not raw_url:
            return None

        raw_resp = await session.get(raw_url, headers=headers, timeout=8.0)
        if raw_resp.status_code != 200:
            return None

        content = raw_resp.text[:_SNIPPET_CAP]
        repo = best.get("repository", {}).get("full_name", "unknown")
        path = best.get("path", "")
        print(f"  [✓] {skill}/{target['filename']} ← github.com/{repo}/{path}")
        return f"# Source: https://github.com/{repo}/blob/main/{path}\n{content}"

    except Exception as e:
        print(f"  [!] Error fetching {target['query'][:50]}: {e}")
        return None


async def fetch_skill(skill: str, token: str) -> int:
    """Fetch all targets for a skill. Returns number of files saved."""
    targets = _FETCH_TARGETS.get(skill, [])
    if not targets:
        print(f"  [~] No fetch targets defined for {skill}")
        return 0

    examples_dir = _SKILLS_BASE / skill / "examples"
    examples_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    try:
        import httpx
        async with httpx.AsyncClient() as session:
            for target in targets:
                content = await _fetch_one(skill, target, token, session)
                if content:
                    out_path = examples_dir / target["filename"]
                    out_path.write_text(content, encoding="utf-8")
                    saved += 1
                await asyncio.sleep(0.5)  # be polite to GitHub API
    except ImportError:
        print("  [!] httpx not installed. Run: pip install httpx")

    return saved


async def fetch_all(token: str, skills: Optional[list[str]] = None) -> None:
    """Fetch examples for all registered skills (or a subset)."""
    targets = skills or list(_FETCH_TARGETS.keys())
    total = 0
    for skill in targets:
        print(f"\n→ Fetching examples for {skill}...")
        n = await fetch_skill(skill, token)
        total += n
    print(f"\nDone. {total} file(s) saved to skills/base/*/examples/")


def main():
    parser = argparse.ArgumentParser(description="SODA OSS Fetcher — populates skill examples from GitHub")
    parser.add_argument("--all", action="store_true", help="Fetch examples for all skills")
    parser.add_argument("--skills", nargs="+", metavar="SKILL", help="Fetch examples for specific skills")
    parser.add_argument("--token", help="GitHub token (overrides GITHUB_TOKEN env var)")
    args = parser.parse_args()

    # Load .env
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            pass

    token = args.token or os.getenv("GITHUB_TOKEN", "")
    if not token:
        print("Warning: No GITHUB_TOKEN found. Rate limit: 60 req/h.")
        print("Add GITHUB_TOKEN=ghp_... to your .env file for 5000 req/h.")

    if not args.all and not args.skills:
        parser.print_help()
        print("\nExamples:")
        print("  python -m kernel.intelligence.oss_fetcher --all")
        print("  python -m kernel.intelligence.oss_fetcher --skills skill_fastapi skill_jwt_auth")
        sys.exit(1)

    skills_to_fetch = None if args.all else args.skills
    asyncio.run(fetch_all(token, skills_to_fetch))


if __name__ == "__main__":
    main()
