"""
ProjectScaffolder — genera archivos de infraestructura faltantes después de la
generación de código y antes del BootAgent.

Opera de forma 100% determinística (sin IA). Detecta el stack a partir de los
archivos ya guardados en source/ y de las skills del proyecto, luego emite
los archivos mínimos necesarios para que el stack sea reconocible por el BootAgent
(package.json, tsconfig.json, requirements.txt, go.mod, etc.).

Solo genera archivos que NO existen — nunca sobreescribe trabajo del AI.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from kernel.execution.dependency_resolver import pinned_python, pinned_npm


# ── Plantillas mínimas por stack ──────────────────────────────────────────────

def _nextjs_package(project_name: str) -> dict:
    return {
        "name": project_name.lower().replace(" ", "-"),
        "version": "0.1.0",
        "private": True,
        "scripts": {
            "dev": "next dev",
            "build": "next build",
            "start": "next start",
            "lint": "next lint"
        },
        "dependencies": {
            "next":      pinned_npm("next"),
            "react":     pinned_npm("react"),
            "react-dom": pinned_npm("react-dom"),
        },
        "devDependencies": {
            "typescript":        pinned_npm("typescript"),
            "@types/react":      pinned_npm("@types/react"),
            "@types/react-dom":  pinned_npm("@types/react-dom"),
            "@types/node":       pinned_npm("@types/node"),
        }
    }


def _react_package(project_name: str) -> dict:
    return {
        "name": project_name.lower().replace(" ", "-"),
        "version": "0.1.0",
        "private": True,
        "scripts": {
            "dev": "vite",
            "build": "vite build",
            "preview": "vite preview"
        },
        "dependencies": {
            "react":     pinned_npm("react"),
            "react-dom": pinned_npm("react-dom"),
        },
        "devDependencies": {
            "typescript":           pinned_npm("typescript"),
            "@types/react":         pinned_npm("@types/react"),
            "@types/react-dom":     pinned_npm("@types/react-dom"),
            "vite":                 pinned_npm("vite"),
            "@vitejs/plugin-react": pinned_npm("@vitejs/plugin-react"),
        }
    }


def _nestjs_package(project_name: str) -> dict:
    return {
        "name": project_name.lower().replace(" ", "-"),
        "version": "0.1.0",
        "scripts": {
            "build": "nest build",
            "start": "nest start",
            "start:dev": "nest start --watch",
            "dev": "nest start --watch"
        },
        "dependencies": {
            "@nestjs/common":           pinned_npm("@nestjs/common"),
            "@nestjs/core":             pinned_npm("@nestjs/core"),
            "@nestjs/platform-express": pinned_npm("@nestjs/platform-express"),
            "reflect-metadata":         pinned_npm("reflect-metadata"),
            "rxjs":                     pinned_npm("rxjs"),
        },
        "devDependencies": {
            "@nestjs/cli": pinned_npm("@nestjs/cli"),
            "typescript":  pinned_npm("typescript"),
            "@types/node": pinned_npm("@types/node"),
        }
    }


def _nodejs_package(project_name: str) -> dict:
    return {
        "name": project_name.lower().replace(" ", "-"),
        "version": "0.1.0",
        "scripts": {
            "dev": "npx tsx src/index.ts",
            "start": "npx tsx src/index.ts",
            "build": "tsc --outDir dist",
            "start:prod": "node dist/index.js"
        },
        "dependencies": {
            "express": pinned_npm("express"),
        },
        "devDependencies": {
            "typescript":    pinned_npm("typescript"),
            "@types/node":   pinned_npm("@types/node"),
            "@types/express": pinned_npm("@types/express"),
            "tsx":           pinned_npm("tsx"),
        }
    }


_TSCONFIG_BASE = {
    "compilerOptions": {
        "target": "ES2020",
        "lib": ["dom", "dom.iterable", "esnext"],
        "allowJs": True,
        "skipLibCheck": True,
        "strict": True,
        "noEmit": True,
        "esModuleInterop": True,
        "module": "esnext",
        "moduleResolution": "bundler",
        "resolveJsonModule": True,
        "isolatedModules": True,
        "jsx": "preserve",
        "incremental": True,
        "paths": {"@/*": ["./*"]}
    },
    "include": ["**/*.ts", "**/*.tsx"],
    "exclude": ["node_modules"]
}

_GITIGNORE_NODE = (
    "node_modules/\n.next/\ndist/\nbuild/\n.env\n.env.local\n*.log\n"
)

_ENV_EXAMPLE = (
    "# Completar con valores reales antes de ejecutar\n"
    "# DATABASE_URL=\n"
    "# NEXTAUTH_SECRET=\n"
    "# NEXT_PUBLIC_API_URL=http://localhost:3000\n"
)

# Python .env con defaults seguros para desarrollo local.
# DATABASE_URL usa SQLite — no requiere servidor externo.
# Las keys de servicios externos quedan comentadas y son opcionales para que el proyecto arranque.
_ENV_PYTHON_DEFAULTS = (
    "# Variables de entorno — generadas por SODA para desarrollo local\n"
    "# Para producción, reemplazá con valores reales y nunca commitees este archivo.\n"
    "\n"
    "# Base de datos — SQLite por defecto (sin servidor externo requerido)\n"
    "DATABASE_URL=sqlite:///./app.db\n"
    "\n"
    "# Seguridad\n"
    "SECRET_KEY=dev-secret-key-change-in-production\n"
    "ALGORITHM=HS256\n"
    "ACCESS_TOKEN_EXPIRE_MINUTES=30\n"
    "\n"
    "# Entorno\n"
    "DEBUG=true\n"
    "ENVIRONMENT=development\n"
    "\n"
    "# Servicios externos (opcionales — comentar si no se usan)\n"
    "# SENDGRID_API_KEY=\n"
    "# STRIPE_SECRET_KEY=\n"
    "# STRIPE_PUBLISHABLE_KEY=\n"
    "# TWILIO_ACCOUNT_SID=\n"
    "# TWILIO_AUTH_TOKEN=\n"
    "# REDIS_URL=redis://localhost:6379\n"
    "# MONGODB_URI=mongodb://localhost:27017/app\n"
    "# AWS_ACCESS_KEY_ID=\n"
    "# AWS_SECRET_ACCESS_KEY=\n"
    "# AWS_REGION=us-east-1\n"
    "# OPENAI_API_KEY=\n"
    "# ANTHROPIC_API_KEY=\n"
)


# ── Scaffolder principal ───────────────────────────────────────────────────────

class ProjectScaffolder:
    """
    Genera archivos de infraestructura faltantes en source/.
    Se invoca después de execute_bottom_up y antes del BootAgent.
    """

    def scaffold(
        self,
        source_dir: Path,
        skills: List[str],
        project_name: str = "soda-project",
        notify_fn=None,
    ) -> List[str]:
        """
        Retorna lista de archivos generados.
        """
        notify = notify_fn or (lambda *a, **kw: None)
        generated: List[str] = []

        # Microservices projects (docker-compose.yml at root) are fully
        # managed by the recursive engine — scaffolder must not touch them.
        if (source_dir / "docker-compose.yml").exists() or (source_dir / "docker-compose.yaml").exists():
            notify("LOG", "  [Scaffolder] docker-compose.yml detectado — proyecto microservicios, scaffolding omitido.")
            return generated

        stack = self._detect_stack(source_dir, skills)
        if not stack:
            return generated

        notify("LOG", f"  [Scaffolder] Stack detectado: {stack}. Generando infraestructura faltante...")

        if stack == "nextjs":
            generated += self._scaffold_nextjs(source_dir, project_name)
        elif stack == "react":
            generated += self._scaffold_react(source_dir, project_name)
        elif stack == "nestjs":
            generated += self._scaffold_nestjs(source_dir, project_name)
        elif stack in ("nodejs", "typescript"):
            generated += self._scaffold_nodejs(source_dir, project_name)
        elif stack == "python":
            generated += self._scaffold_python(source_dir)

        # Shared across all node stacks
        if stack in ("nextjs", "react", "nestjs", "nodejs", "typescript"):
            generated += self._scaffold_node_shared(source_dir)

        if generated:
            notify("LOG", f"  [Scaffolder] Archivos generados: {generated}")
        else:
            notify("LOG", "  [Scaffolder] Infraestructura ya presente, nada que generar.")

        return generated

    # ── Stack detection ───────────────────────────────────────────────────────

    _PYTHON_ENTRIES = ("main.py", "app.py", "run.py", "server.py", "manage.py")

    def _detect_stack(self, source_dir: Path, skills: List[str]) -> Optional[str]:
        """Detecta el stack en orden de prioridad."""
        # 1. Node manifest → BootAgent can handle it directly
        if (source_dir / "package.json").exists():
            return None

        # 2. Python manifest exists — but still check for entry point
        if (source_dir / "requirements.txt").exists() or (source_dir / "pyproject.toml").exists():
            if any((source_dir / e).exists() for e in self._PYTHON_ENTRIES):
                return None  # Fully ready
            return "python"  # Has manifest but no runnable entry — generate it

        # 2. Detectar por skills
        skill_set = set(skills or [])
        if "skill_nextjs" in skill_set:
            return "nextjs"
        if "skill_react" in skill_set or "skill_react_native" in skill_set:
            return "react"
        if "skill_nestjs" in skill_set:
            return "nestjs"
        if "skill_nodejs" in skill_set or "skill_typescript" in skill_set:
            return "nodejs"
        if "skill_fastapi" in skill_set:
            return "python"

        # 3. Detectar por archivos generados en source/
        ts_files = list(source_dir.rglob("*.tsx")) + list(source_dir.rglob("*.ts"))
        if ts_files:
            # Heurística: si hay archivos con "page" o "layout" → nextjs
            names = [f.stem.lower() for f in ts_files]
            if any(n in ("page", "layout", "route") for n in names):
                return "nextjs"
            return "typescript"

        py_files = list(source_dir.rglob("*.py"))
        if py_files:
            return "python"

        return None

    # ── Node stacks ───────────────────────────────────────────────────────────

    def _scaffold_nextjs(self, source_dir: Path, project_name: str) -> List[str]:
        files = []
        pkg = _nextjs_package(project_name)
        files += self._write_if_missing(source_dir / "package.json",
                                         json.dumps(pkg, indent=2))
        files += self._write_if_missing(source_dir / "tsconfig.json",
                                         json.dumps(_TSCONFIG_BASE, indent=2))
        files += self._write_if_missing(source_dir / "next.config.js",
                                         "/** @type {import('next').NextConfig} */\n"
                                         "const nextConfig = {};\nmodule.exports = nextConfig;\n")
        return files

    def _scaffold_react(self, source_dir: Path, project_name: str) -> List[str]:
        files = []
        pkg = _react_package(project_name)
        files += self._write_if_missing(source_dir / "package.json",
                                         json.dumps(pkg, indent=2))
        files += self._write_if_missing(source_dir / "tsconfig.json",
                                         json.dumps(_TSCONFIG_BASE, indent=2))
        files += self._write_if_missing(source_dir / "vite.config.ts",
                                         "import { defineConfig } from 'vite';\n"
                                         "import react from '@vitejs/plugin-react';\n"
                                         "export default defineConfig({ plugins: [react()] });\n")
        # Minimal index.html for Vite
        files += self._write_if_missing(source_dir / "index.html",
                                         '<!DOCTYPE html>\n<html><head><meta charset="UTF-8" />'
                                         '<title>App</title></head>\n'
                                         '<body><div id="root"></div>'
                                         '<script type="module" src="/src/main.tsx"></script></body></html>\n')
        return files

    def _scaffold_nestjs(self, source_dir: Path, project_name: str) -> List[str]:
        files = []
        pkg = _nestjs_package(project_name)
        files += self._write_if_missing(source_dir / "package.json",
                                         json.dumps(pkg, indent=2))
        ts = dict(_TSCONFIG_BASE)
        ts["compilerOptions"] = {**ts["compilerOptions"],
                                   "module": "commonjs",
                                   "declaration": True,
                                   "removeComments": True,
                                   "emitDecoratorMetadata": True,
                                   "experimentalDecorators": True,
                                   "outDir": "./dist",
                                   "baseUrl": "./"}
        files += self._write_if_missing(source_dir / "tsconfig.json",
                                         json.dumps(ts, indent=2))
        return files

    def _scaffold_nodejs(self, source_dir: Path, project_name: str) -> List[str]:
        files = []
        pkg = _nodejs_package(project_name)
        files += self._write_if_missing(source_dir / "package.json",
                                         json.dumps(pkg, indent=2))
        files += self._write_if_missing(source_dir / "tsconfig.json",
                                         json.dumps(_TSCONFIG_BASE, indent=2))
        return files

    def _scaffold_node_shared(self, source_dir: Path) -> List[str]:
        files = []
        files += self._write_if_missing(source_dir / ".gitignore", _GITIGNORE_NODE)
        files += self._write_if_missing(source_dir / ".env.example", _ENV_EXAMPLE)
        return files

    # ── Python ────────────────────────────────────────────────────────────────

    def _scaffold_python(self, source_dir: Path) -> List[str]:
        files = []
        # Collect imports from .py files to build requirements.txt
        imports = self._infer_python_requirements(source_dir)
        if imports:
            content = "\n".join(sorted(imports)) + "\n"
            files += self._write_if_missing(source_dir / "requirements.txt", content)

        # Generate a runnable entry point if none exists
        if not any((source_dir / e).exists() for e in self._PYTHON_ENTRIES):
            entry = self._generate_python_entry(source_dir, imports)
            if entry:
                files += self._write_if_missing(source_dir / "main.py", entry)

        # Generate .env with safe local defaults (SQLite, no external services required).
        # Writes both .env (used at runtime) and .env.example (version-control reference).
        # _write_if_missing never overwrites an existing .env the user or SODA already created.
        files += self._write_if_missing(source_dir / ".env.example", _ENV_PYTHON_DEFAULTS)
        files += self._write_if_missing(source_dir / ".env", _ENV_PYTHON_DEFAULTS)

        # Python .gitignore
        files += self._write_if_missing(
            source_dir / ".gitignore",
            "__pycache__/\n*.pyc\n.venv/\nvenv/\n.env\n*.db\n*.log\ndist/\nbuild/\n",
        )

        return files

    def _generate_python_entry(self, source_dir: Path, packages: List[str]) -> str:
        """Return a minimal runnable main.py for the detected framework."""
        import re as _re

        pkg_set = {p.split("[")[0].lower() for p in packages}

        is_fastapi = "fastapi" in pkg_set
        is_flask   = "flask"   in pkg_set
        is_django  = "django"  in pkg_set

        # Try to locate an existing `app = FastAPI(...)` in generated files
        app_module: Optional[str] = None
        if is_fastapi:
            for py_file in sorted(source_dir.rglob("*.py")):
                try:
                    text = py_file.read_text(encoding="utf-8", errors="ignore")
                    if _re.search(r"^app\s*=\s*FastAPI\s*\(", text, _re.MULTILINE):
                        rel = py_file.relative_to(source_dir)
                        mod = str(rel).replace("\\", "/").replace("/", ".").removesuffix(".py")
                        app_module = mod
                        break
                except Exception:
                    pass

        if is_fastapi:
            if app_module and app_module != "main":
                return (
                    '"""Entry point generado por SODA — arranca la app FastAPI."""\n'
                    "import uvicorn\n\n"
                    'if __name__ == "__main__":\n'
                    f'    uvicorn.run("{app_module}:app", host="0.0.0.0", port=8080, reload=False)\n'
                )
            return (
                '"""Entry point generado por SODA."""\n'
                "from fastapi import FastAPI\n"
                "import uvicorn\n\n"
                "app = FastAPI()\n\n"
                '@app.get("/health")\n'
                "async def health():\n"
                '    return {"status": "ok"}\n\n'
                'if __name__ == "__main__":\n'
                '    uvicorn.run(app, host="0.0.0.0", port=8080)\n'
            )

        if is_flask:
            return (
                '"""Entry point generado por SODA."""\n'
                "from flask import Flask\n\n"
                "app = Flask(__name__)\n\n"
                '@app.route("/health")\n'
                "def health():\n"
                '    return {"status": "ok"}\n\n'
                'if __name__ == "__main__":\n'
                '    app.run(host="0.0.0.0", port=8080)\n'
            )

        if is_django:
            return (
                '"""Entry point generado por SODA — equivalente a manage.py runserver."""\n'
                "import os\n"
                "import sys\n\n"
                'if __name__ == "__main__":\n'
                '    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")\n'
                "    from django.core.management import execute_from_command_line\n"
                '    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8080"])\n'
            )

        # Generic — uvicorn looking for app:app in the generated code
        return (
            '"""Entry point generado por SODA."""\n'
            "import uvicorn\n\n"
            'if __name__ == "__main__":\n'
            '    uvicorn.run("app:app", host="0.0.0.0", port=8080)\n'
        )

    def _infer_python_requirements(self, source_dir: Path) -> List[str]:
        """Heurística: escanea imports en .py y mapea a packages conocidos."""
        import re
        _IMPORT_TO_PACKAGE = {
            # Web frameworks
            "fastapi": "fastapi",
            "flask": "flask",
            "django": "django",
            "starlette": "starlette",
            "tornado": "tornado",
            "sanic": "sanic",
            "aiohttp": "aiohttp",
            "uvicorn": "uvicorn[standard]",
            "gunicorn": "gunicorn",
            "httpx": "httpx",
            # Data / ORM
            "sqlalchemy": "sqlalchemy",
            "alembic": "alembic",
            "pymongo": "pymongo",
            "motor": "motor",
            "redis": "redis",
            "celery": "celery",
            "elasticsearch": "elasticsearch",
            "pymysql": "pymysql",
            "psycopg2": "psycopg2-binary",
            "asyncpg": "asyncpg",
            "tortoise": "tortoise-orm",
            # Validation / serialization
            "pydantic": "pydantic",
            "marshmallow": "marshmallow",
            "cerberus": "cerberus",
            # Auth / security
            "jwt": "python-jose[cryptography]",
            "passlib": "passlib[bcrypt]",
            "bcrypt": "bcrypt",
            "cryptography": "cryptography",
            "itsdangerous": "itsdangerous",
            # Config / env
            "dotenv": "python-dotenv",
            "decouple": "python-decouple",
            "dynaconf": "dynaconf",
            # AI / ML
            "anthropic": "anthropic",
            "openai": "openai",
            "langchain": "langchain",
            "google": "google-generativeai",
            "transformers": "transformers",
            "torch": "torch",
            "tensorflow": "tensorflow",
            "sklearn": "scikit-learn",
            "numpy": "numpy",
            "pandas": "pandas",
            "PIL": "Pillow",
            "cv2": "opencv-python",
            # Comms / notifications
            "sendgrid": "sendgrid",
            "stripe": "stripe",
            "twilio": "twilio",
            "boto3": "boto3",
            "botocore": "botocore",
            "firebase_admin": "firebase-admin",
            "slack_sdk": "slack-sdk",
            "telegram": "python-telegram-bot",
            "smtplib": "",   # stdlib — skip
            # Utilities
            "requests": "requests",
            "httplib2": "httplib2",
            "urllib3": "urllib3",
            "click": "click",
            "typer": "typer",
            "rich": "rich",
            "loguru": "loguru",
            "structlog": "structlog",
            "yaml": "pyyaml",
            "toml": "toml",
            "arrow": "arrow",
            "pendulum": "pendulum",
            "dateutil": "python-dateutil",
            "pytz": "pytz",
            "websockets": "websockets",
            "socketio": "python-socketio",
            "paramiko": "paramiko",
            "fabric": "fabric",
            "pytest": "pytest",
            "hypothesis": "hypothesis",
        }
        found: set[str] = set()
        for py_file in source_dir.rglob("*.py"):
            try:
                text = py_file.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(r'^(?:import|from)\s+([\w]+)', text, re.MULTILINE):
                    mod = m.group(1).lower()
                    if mod in _IMPORT_TO_PACKAGE and _IMPORT_TO_PACKAGE[mod]:
                        found.add(pinned_python(_IMPORT_TO_PACKAGE[mod]))
            except Exception:
                pass
        return list(found)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _write_if_missing(path: Path, content: str) -> List[str]:
        """Escribe solo si el archivo no existe. Retorna [path_str] si escribió."""
        if path.exists():
            return []
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return [str(path.name)]
        except Exception:
            return []
