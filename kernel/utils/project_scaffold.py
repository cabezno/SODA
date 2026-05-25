"""
ProjectScaffold — genera los archivos de manifiesto que hacen ejecutable
un proyecto SODA generado.

Se llama después de que todos los módulos fuente fueron escritos a disco.
Nunca sobreescribe archivos que ya existan.

Genera:
  package.json    — Node/TypeScript: dependencias extraídas de imports reales
  tsconfig.json   — TypeScript: template estándar
  next.config.mjs — Next.js: configuración mínima
  requirements.txt — Python: dependencias extraídas de imports reales
  .env.example    — todos los stacks: variables de entorno referenciadas en código
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

# ── Tabla de versiones npm conocidas ──────────────────────────────────────────
_NPM_VERSIONS: Dict[str, str] = {
    "express":                    "^4.18.2",
    "better-sqlite3":             "^9.4.3",
    "sqlite3":                    "^5.1.7",
    "next":                       "^14.2.3",
    "react":                      "^18.3.1",
    "react-dom":                  "^18.3.1",
    "stripe":                     "^14.25.0",
    "axios":                      "^1.7.2",
    "cors":                       "^2.8.5",
    "helmet":                     "^7.1.0",
    "jsonwebtoken":               "^9.0.2",
    "bcryptjs":                   "^2.4.3",
    "dotenv":                     "^16.4.5",
    "uuid":                       "^9.0.1",
    "zod":                        "^3.23.8",
    "prisma":                     "^5.15.0",
    "@prisma/client":             "^5.15.0",
    "mongoose":                   "^8.4.4",
    "pg":                         "^8.12.0",
    "mysql2":                     "^3.10.0",
    "redis":                      "^4.6.15",
    "ioredis":                    "^5.4.1",
    "ws":                         "^8.17.1",
    "socket.io":                  "^4.7.5",
    "multer":                     "^1.4.5",
    "sharp":                      "^0.33.4",
    "nodemailer":                 "^6.9.14",
    "joi":                        "^17.13.1",
    "lodash":                     "^4.17.21",
    "date-fns":                   "^3.6.0",
    "dayjs":                      "^1.11.11",
    "winston":                    "^3.13.0",
    "pino":                       "^9.2.0",
    "tailwindcss":                "^3.4.4",
    "framer-motion":              "^11.2.12",
    "clsx":                       "^2.1.1",
    "class-variance-authority":   "^0.7.0",
    "lucide-react":               "^0.395.0",
    "@radix-ui/react-dialog":     "^1.0.5",
    "@radix-ui/react-slot":       "^1.0.2",
    "cookie-parser":              "^1.4.6",
    "morgan":                     "^1.10.0",
    "compression":                "^1.7.4",
    "body-parser":                "^1.20.2",
    "passport":                   "^0.7.0",
    "passport-jwt":               "^4.0.1",
    "passport-local":             "^1.0.0",
    "sequelize":                  "^6.37.3",
    "typeorm":                    "^0.3.20",
    "knex":                       "^3.1.0",
    "graphql":                    "^16.9.0",
    "@apollo/server":             "^4.10.4",
    "nestjs":                     "^10.0.0",
    "@nestjs/core":               "^10.0.0",
    "@nestjs/common":             "^10.0.0",
    "@nestjs/platform-express":   "^10.0.0",
    "reflect-metadata":           "^0.2.0",
    "rxjs":                       "^7.8.1",
}

# Paquetes @types que acompañan al runtime package
_NPM_TYPES: Dict[str, str] = {
    "express":       "@types/express",
    "better-sqlite3":"@types/better-sqlite3",
    "cors":          "@types/cors",
    "bcryptjs":      "@types/bcryptjs",
    "jsonwebtoken":  "@types/jsonwebtoken",
    "nodemailer":    "@types/nodemailer",
    "multer":        "@types/multer",
    "lodash":        "@types/lodash",
    "ws":            "@types/ws",
    "pg":            "@types/pg",
    "uuid":          "@types/uuid",
    "morgan":        "@types/morgan",
    "cookie-parser": "@types/cookie-parser",
    "compression":   "@types/compression",
    "passport":      "@types/passport",
    "passport-jwt":  "@types/passport-jwt",
    "passport-local":"@types/passport-local",
}

# Tabla de paquetes pip (nombre de import → spec pip)
_PIP_PACKAGES: Dict[str, str] = {
    "fastapi":      "fastapi>=0.109.0",
    "uvicorn":      "uvicorn[standard]>=0.27.0",
    "sqlalchemy":   "sqlalchemy>=2.0.0",
    "pydantic":     "pydantic>=2.0.0",
    "anthropic":    "anthropic>=0.28.0",
    "openai":       "openai>=1.30.0",
    "requests":     "requests>=2.32.0",
    "httpx":        "httpx>=0.27.0",
    "aiohttp":      "aiohttp>=3.9.5",
    "celery":       "celery>=5.4.0",
    "redis":        "redis>=5.0.6",
    "boto3":        "boto3>=1.34.0",
    "PIL":          "pillow>=10.3.0",
    "pandas":       "pandas>=2.2.2",
    "numpy":        "numpy>=1.26.4",
    "sklearn":      "scikit-learn>=1.5.0",
    "torch":        "torch>=2.3.0",
    "jwt":          "pyjwt>=2.8.0",
    "bcrypt":       "bcrypt>=4.1.3",
    "cryptography": "cryptography>=42.0.8",
    "alembic":      "alembic>=1.13.1",
    "stripe":       "stripe>=9.9.0",
    "telegram":     "python-telegram-bot>=21.3",
    "flask":        "flask>=3.0.3",
    "django":       "django>=5.0.6",
    "dotenv":       "python-dotenv>=1.0.1",
    "yaml":         "pyyaml>=6.0.1",
    "click":        "click>=8.1.7",
    "typer":        "typer>=0.12.3",
    "rich":         "rich>=13.7.1",
    "loguru":       "loguru>=0.7.2",
    "aiofiles":     "aiofiles>=23.2.1",
    "websockets":   "websockets>=12.0",
    "motor":        "motor>=3.4.0",
    "pymongo":      "pymongo>=4.7.3",
    "psycopg2":     "psycopg2-binary>=2.9.9",
}

_NODE_BUILTINS: frozenset = frozenset({
    "fs", "fs/promises", "path", "os", "crypto", "stream", "util",
    "http", "https", "net", "events", "buffer", "child_process", "url",
    "querystring", "readline", "assert", "module", "process", "v8",
    "vm", "cluster", "worker_threads", "perf_hooks", "timers",
})

_PYTHON_STDLIB: frozenset = frozenset({
    "os", "sys", "re", "json", "time", "datetime", "pathlib", "typing",
    "collections", "functools", "itertools", "io", "abc", "copy",
    "math", "random", "uuid", "hashlib", "hmac", "base64", "struct",
    "logging", "threading", "asyncio", "concurrent", "subprocess",
    "shutil", "tempfile", "glob", "fnmatch", "stat", "enum", "dataclasses",
    "contextlib", "weakref", "gc", "inspect", "importlib", "pkgutil",
    "traceback", "warnings", "unittest", "http", "urllib", "email",
    "html", "xml", "csv", "configparser", "argparse", "textwrap",
    "string", "pprint", "decimal", "fractions", "statistics",
    "socket", "ssl", "select", "queue", "multiprocessing", "ctypes",
    "array", "bisect", "heapq", "queue", "weakref",
})


# ── Punto de entrada público ───────────────────────────────────────────────────

def scaffold_project(
    source_dir: Path,
    all_skills: List[str],
    notify_fn: Optional[Callable] = None,
) -> None:
    """
    Genera todos los archivos de manifiesto faltantes en source_dir.
    Nunca sobreescribe archivos existentes.
    """
    _log = notify_fn or (lambda msg, *_: None)

    if not source_dir.exists():
        _log("WARNING", "  [Scaffold] source_dir no existe — omitiendo.")
        return

    is_ts     = _detect_typescript(source_dir, all_skills)
    is_nextjs = any("nextjs" in s.lower() for s in all_skills)
    is_nestjs = any("nestjs" in s.lower() for s in all_skills)

    generated: List[str] = []

    if is_ts:
        if _ensure_tsconfig(source_dir):
            generated.append("tsconfig.json")
        if _ensure_package_json(source_dir, all_skills, is_nextjs, is_nestjs):
            generated.append("package.json")
        if is_nextjs and _ensure_next_config(source_dir):
            generated.append("next.config.mjs")
    else:
        if _ensure_requirements_txt(source_dir):
            generated.append("requirements.txt")

    if _ensure_env_example(source_dir):
        generated.append(".env.example")

    if generated:
        _log("LOG", f"  [Scaffold] Archivos generados: {', '.join(generated)}")
    else:
        _log("LOG", "  [Scaffold] Manifiestos ya existentes — sin cambios.")


# ── Detección de stack ─────────────────────────────────────────────────────────

def _detect_typescript(source_dir: Path, skills: List[str]) -> bool:
    ts_skills = {
        "skill_typescript", "skill_nextjs", "skill_nodejs",
        "skill_react", "skill_vue", "skill_svelte", "skill_nestjs",
    }
    if ts_skills & set(skills):
        return True
    # Fallback: archivos .ts/.tsx en disco
    return bool(
        list(source_dir.glob("*.ts"))
        + list(source_dir.glob("*.tsx"))
        + list(source_dir.glob("**/*.ts"))
    )


# ── TypeScript ────────────────────────────────────────────────────────────────

def _ensure_tsconfig(source_dir: Path) -> bool:
    target = source_dir / "tsconfig.json"
    if target.exists():
        return False
    config = {
        "compilerOptions": {
            "target":                          "ES2020",
            "lib":                             ["ES2020", "DOM"],
            "module":                          "commonjs",
            "moduleResolution":                "node",
            "outDir":                          "./dist",
            "rootDir":                         "./",
            "strict":                          False,
            "esModuleInterop":                 True,
            "allowSyntheticDefaultImports":    True,
            "skipLibCheck":                    True,
            "resolveJsonModule":               True,
            "declaration":                     True,
            "sourceMap":                       True,
            "forceConsistentCasingInFileNames": True,
            "experimentalDecorators":          True,
            "emitDecoratorMetadata":           True,
        },
        "include":  ["./**/*.ts", "./**/*.tsx"],
        "exclude":  ["node_modules", "dist", ".next"],
    }
    target.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return True


def _ensure_package_json(
    source_dir: Path,
    skills: List[str],
    is_nextjs: bool,
    is_nestjs: bool,
) -> bool:
    target = source_dir / "package.json"
    if target.exists():
        return False

    deps, dev_deps = _resolve_npm_deps(source_dir, skills, is_nextjs, is_nestjs)

    if is_nextjs:
        scripts = {
            "dev":   "next dev",
            "build": "next build",
            "start": "next start",
            "lint":  "next lint",
        }
    elif is_nestjs:
        scripts = {
            "build":       "nest build",
            "start":       "nest start",
            "start:dev":   "nest start --watch",
            "start:prod":  "node dist/main",
        }
    else:
        scripts = {
            "start": "node dist/main.js",
            "dev":   "ts-node-dev --respawn --transpile-only main.ts",
            "build": "tsc",
        }

    pkg = {
        "name":            source_dir.parent.name.lower().replace(" ", "-").replace("_", "-"),
        "version":         "1.0.0",
        "private":         True,
        "scripts":         scripts,
        "dependencies":    deps,
        "devDependencies": dev_deps,
    }
    target.write_text(json.dumps(pkg, indent=2), encoding="utf-8")
    return True


def _resolve_npm_deps(
    source_dir: Path,
    skills: List[str],
    is_nextjs: bool,
    is_nestjs: bool,
) -> tuple[Dict[str, str], Dict[str, str]]:
    """
    Extrae los imports de todos los archivos .ts/.tsx y los resuelve
    contra la tabla de versiones conocidas.
    """
    imported: Set[str] = set()
    import_re = re.compile(
        r"""(?:^|[\n;])\s*(?:import|require)\s*(?:.*?from\s*)?['"]([^'"]+)['"]""",
        re.MULTILINE,
    )

    for ts_file in (
        list(source_dir.glob("*.ts"))
        + list(source_dir.glob("*.tsx"))
        + list(source_dir.glob("**/*.ts"))
        + list(source_dir.glob("**/*.tsx"))
    ):
        try:
            content = ts_file.read_text(encoding="utf-8", errors="ignore")
            for match in import_re.finditer(content):
                raw = match.group(1)
                if raw.startswith(".") or raw in _NODE_BUILTINS:
                    continue
                # Normalizar: @scope/pkg/sub → @scope/pkg; pkg/sub → pkg
                if raw.startswith("@"):
                    parts = raw.split("/")
                    pkg = "/".join(parts[:2])
                else:
                    pkg = raw.split("/")[0]
                imported.add(pkg)
        except Exception:
            pass

    deps: Dict[str, str]      = {}
    type_deps: Dict[str, str] = {}

    for pkg in imported:
        version = _NPM_VERSIONS.get(pkg)
        if version:
            deps[pkg] = version
        else:
            deps[pkg] = "^1.0.0"  # paquete desconocido — versión genérica
        types_pkg = _NPM_TYPES.get(pkg)
        if types_pkg:
            type_deps[types_pkg] = "^1.0.0"

    # DevDependencies base para TypeScript
    dev_base: Dict[str, str] = {
        "typescript":  "^5.4.5",
        "ts-node":     "^10.9.2",
        "ts-node-dev": "^2.0.0",
        "@types/node": "^20.14.0",
    }

    # Forzar dependencias por stack
    if is_nextjs:
        deps.setdefault("next",      _NPM_VERSIONS["next"])
        deps.setdefault("react",     _NPM_VERSIONS["react"])
        deps.setdefault("react-dom", _NPM_VERSIONS["react-dom"])
        dev_base["@types/react"]       = "^18.3.3"
        dev_base["@types/react-dom"]   = "^18.3.0"
        dev_base["eslint"]             = "^8.57.0"
        dev_base["eslint-config-next"] = "^14.2.3"

    if is_nestjs:
        deps.setdefault("@nestjs/core",             _NPM_VERSIONS["@nestjs/core"])
        deps.setdefault("@nestjs/common",           _NPM_VERSIONS["@nestjs/common"])
        deps.setdefault("@nestjs/platform-express", _NPM_VERSIONS["@nestjs/platform-express"])
        deps.setdefault("reflect-metadata",         _NPM_VERSIONS["reflect-metadata"])
        deps.setdefault("rxjs",                     _NPM_VERSIONS["rxjs"])

    # Skill-based additions
    skill_set = set(skills)
    if "skill_sqlite" in skill_set or "skill_repository" in skill_set:
        deps.setdefault("better-sqlite3", _NPM_VERSIONS["better-sqlite3"])
        type_deps.setdefault("@types/better-sqlite3", "^7.6.10")
    if "skill_jwt_auth" in skill_set:
        deps.setdefault("jsonwebtoken", _NPM_VERSIONS["jsonwebtoken"])
        deps.setdefault("bcryptjs",     _NPM_VERSIONS["bcryptjs"])
        type_deps.setdefault("@types/jsonwebtoken", "^9.0.6")
        type_deps.setdefault("@types/bcryptjs",     "^2.4.6")
    if "skill_rest_api" in skill_set or "skill_fastapi" in skill_set:
        deps.setdefault("express", _NPM_VERSIONS["express"])
        deps.setdefault("cors",    _NPM_VERSIONS["cors"])
        deps.setdefault("helmet",  _NPM_VERSIONS["helmet"])
        type_deps.setdefault("@types/express", "^4.17.21")
        type_deps.setdefault("@types/cors",    "^2.8.17")
    if "skill_integration" in skill_set:
        deps.setdefault("axios", _NPM_VERSIONS["axios"])

    dev_deps = {**dev_base, **type_deps}
    return deps, dev_deps


def _ensure_next_config(source_dir: Path) -> bool:
    target = source_dir / "next.config.mjs"
    if target.exists():
        return False
    content = (
        "/** @type {import('next').NextConfig} */\n"
        "const nextConfig = {\n"
        "  reactStrictMode: true,\n"
        "};\n\n"
        "export default nextConfig;\n"
    )
    target.write_text(content, encoding="utf-8")
    return True


# ── Python ────────────────────────────────────────────────────────────────────

def _ensure_requirements_txt(source_dir: Path) -> bool:
    target = source_dir / "requirements.txt"
    if target.exists():
        return False

    import_re = re.compile(
        r"^\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.MULTILINE
    )
    imported: Set[str] = set()

    for py_file in list(source_dir.glob("*.py")) + list(source_dir.glob("**/*.py")):
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for match in import_re.finditer(content):
                pkg = match.group(1)
                if pkg not in _PYTHON_STDLIB:
                    imported.add(pkg)
        except Exception:
            pass

    specs = sorted({
        _PIP_PACKAGES[pkg]
        for pkg in imported
        if pkg in _PIP_PACKAGES
    })

    if not specs:
        specs = ["fastapi>=0.109.0", "uvicorn[standard]>=0.27.0"]

    target.write_text("\n".join(specs) + "\n", encoding="utf-8")
    return True


# ── Variables de entorno ───────────────────────────────────────────────────────

def _ensure_env_example(source_dir: Path) -> bool:
    target = source_dir / ".env.example"
    if target.exists():
        return False

    env_vars: Set[str] = set()

    ts_env_re = re.compile(r"process\.env\.([A-Z_][A-Z0-9_]+)")
    py_env_re = re.compile(
        r"""os\.(?:environ\.get|getenv|environ)\s*[\[(]['"]([A-Z_][A-Z0-9_]+)['"]"""
    )

    all_files = (
        list(source_dir.glob("*.ts"))
        + list(source_dir.glob("*.tsx"))
        + list(source_dir.glob("**/*.ts"))
        + list(source_dir.glob("*.py"))
        + list(source_dir.glob("**/*.py"))
    )
    for f in all_files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            env_vars.update(ts_env_re.findall(content))
            env_vars.update(py_env_re.findall(content))
        except Exception:
            pass

    # Excluir variables de sistema comunes que no son secretos de app
    system_vars = {"NODE_ENV", "PATH", "HOME", "USER", "PORT", "HOST"}
    env_vars -= system_vars

    if not env_vars:
        return False

    lines = [
        "# Variables de entorno requeridas por este proyecto",
        "# Copiá este archivo a .env y completá los valores reales",
        "",
    ]
    for var in sorted(env_vars):
        lines.append(f"{var}=")

    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True
