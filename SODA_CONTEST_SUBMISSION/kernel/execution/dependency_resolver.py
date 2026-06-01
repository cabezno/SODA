"""
DependencyResolver — tabla estática de versiones pinned para Python y npm.

Provee rangos de versión conocidos como compatibles entre sí para los 80+
paquetes más comunes usados por proyectos generados por SODA.

No hace resolución dinámica ni llama APIs externas — es una tabla de lookup
actualizable manualmente cuando los rangos queden obsoletos.

Uso:
    from kernel.execution.dependency_resolver import pinned_python, pinned_npm
    pkg = pinned_python("fastapi")   # → "fastapi>=0.111.0,<0.120.0"
    pkg = pinned_npm("react")        # → "^18.3.0"
"""

from __future__ import annotations

# ── Python ────────────────────────────────────────────────────────────────────
# Clave: nombre del paquete sin extras (e.g. "fastapi", no "fastapi[all]")
# Valor: especificación completa con extras cuando necesario
_PYTHON: dict[str, str] = {
    # Web frameworks
    "fastapi":                  "fastapi>=0.111.0,<0.120.0",
    "flask":                    "flask>=3.0.0,<4.0.0",
    "django":                   "django>=5.0.0,<6.0.0",
    "starlette":                "starlette>=0.37.0,<0.40.0",
    "tornado":                  "tornado>=6.4.0",
    "sanic":                    "sanic>=23.12.0",
    "aiohttp":                  "aiohttp>=3.9.0,<4.0.0",
    "uvicorn[standard]":        "uvicorn[standard]>=0.29.0,<0.31.0",
    "gunicorn":                 "gunicorn>=22.0.0",
    "httpx":                    "httpx>=0.27.0,<0.28.0",
    "requests":                 "requests>=2.31.0,<3.0.0",
    # Data / ORM
    "sqlalchemy":               "SQLAlchemy>=2.0.0,<2.1.0",
    "alembic":                  "alembic>=1.13.0,<2.0.0",
    "pymongo":                  "pymongo>=4.6.0,<5.0.0",
    "motor":                    "motor>=3.4.0,<4.0.0",
    "redis":                    "redis>=5.0.0,<6.0.0",
    "celery":                   "celery>=5.3.0,<6.0.0",
    "elasticsearch":            "elasticsearch>=8.13.0,<9.0.0",
    "pymysql":                  "pymysql>=1.1.0,<2.0.0",
    "psycopg2-binary":          "psycopg2-binary>=2.9.9",
    "asyncpg":                  "asyncpg>=0.29.0,<0.30.0",
    "tortoise-orm":             "tortoise-orm>=0.21.0,<0.22.0",
    "databases":                "databases>=0.9.0",
    # Validation / serialization
    "pydantic":                 "pydantic>=2.6.0,<3.0.0",
    "marshmallow":              "marshmallow>=3.21.0,<4.0.0",
    "cerberus":                 "cerberus>=1.3.5",
    # Auth / security
    "python-jose[cryptography]": "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]":          "passlib[bcrypt]>=1.7.4",
    "bcrypt":                   "bcrypt>=4.1.0,<5.0.0",
    "cryptography":             "cryptography>=42.0.0",
    "itsdangerous":             "itsdangerous>=2.1.2",
    "python-multipart":         "python-multipart>=0.0.9",
    # Config / env
    "python-dotenv":            "python-dotenv>=1.0.0",
    "python-decouple":          "python-decouple>=3.8",
    "dynaconf":                 "dynaconf>=3.2.0",
    # AI / ML
    "anthropic":                "anthropic>=0.28.0",
    "openai":                   "openai>=1.30.0",
    "langchain":                "langchain>=0.2.0",
    "google-generativeai":      "google-generativeai>=0.7.0",
    "numpy":                    "numpy>=1.26.0,<2.0.0",
    "pandas":                   "pandas>=2.2.0,<3.0.0",
    "Pillow":                   "Pillow>=10.3.0",
    "opencv-python":            "opencv-python>=4.9.0",
    "scikit-learn":             "scikit-learn>=1.4.0",
    # Comms / notifications
    "sendgrid":                 "sendgrid>=6.11.0",
    "stripe":                   "stripe>=9.0.0",
    "twilio":                   "twilio>=9.0.0",
    "boto3":                    "boto3>=1.34.0",
    "botocore":                 "botocore>=1.34.0",
    "firebase-admin":           "firebase-admin>=6.4.0",
    "slack-sdk":                "slack-sdk>=3.27.0",
    "python-telegram-bot":      "python-telegram-bot>=21.0.0",
    # Utilities
    "urllib3":                  "urllib3>=2.2.0,<3.0.0",
    "click":                    "click>=8.1.7",
    "typer":                    "typer>=0.12.0",
    "rich":                     "rich>=13.7.0",
    "loguru":                   "loguru>=0.7.2",
    "structlog":                "structlog>=24.1.0",
    "pyyaml":                   "pyyaml>=6.0.1",
    "toml":                     "toml>=0.10.2",
    "arrow":                    "arrow>=1.3.0",
    "pendulum":                 "pendulum>=3.0.0",
    "python-dateutil":          "python-dateutil>=2.9.0",
    "pytz":                     "pytz>=2024.1",
    "websockets":               "websockets>=12.0",
    "python-socketio":          "python-socketio>=5.11.0",
    "paramiko":                 "paramiko>=3.4.0",
    "pytest":                   "pytest>=8.0.0",
    "pytest-asyncio":           "pytest-asyncio>=0.23.0",
    "httpx":                    "httpx>=0.27.0",
    # JWT / auth helpers
    "pyjwt":                    "PyJWT>=2.8.0",
    "authlib":                  "Authlib>=1.3.0",
    # Cache
    "cachetools":               "cachetools>=5.3.0",
    "diskcache":                "diskcache>=5.6.0",
    # Background tasks / queues
    "rq":                       "rq>=1.16.0",
    "apscheduler":              "APScheduler>=3.10.0",
    # Observability
    "prometheus-client":        "prometheus-client>=0.20.0",
    "opentelemetry-api":        "opentelemetry-api>=1.24.0",
    "sentry-sdk":               "sentry-sdk>=2.0.0",
}

# ── npm ───────────────────────────────────────────────────────────────────────
_NPM: dict[str, str] = {
    # React ecosystem
    "react":                    "^18.3.0",
    "react-dom":                "^18.3.0",
    "react-router-dom":         "^6.23.0",
    "react-query":              "^3.39.3",
    "@tanstack/react-query":    "^5.40.0",
    "react-hook-form":          "^7.51.0",
    "zustand":                  "^4.5.0",
    "jotai":                    "^2.8.0",
    "recoil":                   "^0.7.7",
    # Next.js
    "next":                     "^15.0.0",
    "next-auth":                "^4.24.0",
    # NestJS
    "@nestjs/common":           "^10.3.0",
    "@nestjs/core":             "^10.3.0",
    "@nestjs/platform-express": "^10.3.0",
    "@nestjs/typeorm":          "^10.0.2",
    "@nestjs/jwt":              "^10.2.0",
    "@nestjs/passport":         "^10.0.3",
    "@nestjs/config":           "^3.2.0",
    "@nestjs/swagger":          "^7.3.0",
    "reflect-metadata":         "^0.2.2",
    "rxjs":                     "^7.8.1",
    # Express
    "express":                  "^4.19.0",
    "cors":                     "^2.8.5",
    "helmet":                   "^7.1.0",
    "morgan":                   "^1.10.0",
    "compression":              "^1.7.4",
    "express-rate-limit":       "^7.3.0",
    # TypeORM / Prisma / Sequelize
    "typeorm":                  "^0.3.20",
    "prisma":                   "^5.15.0",
    "@prisma/client":           "^5.15.0",
    "sequelize":                "^6.37.0",
    # Auth
    "bcryptjs":                 "^2.4.3",
    "jsonwebtoken":             "^9.0.2",
    "passport":                 "^0.7.0",
    "passport-jwt":             "^4.0.1",
    "passport-local":           "^1.0.0",
    # HTTP clients
    "axios":                    "^1.7.0",
    "node-fetch":               "^3.3.2",
    # Validation
    "zod":                      "^3.23.0",
    "joi":                      "^17.13.0",
    "class-validator":          "^0.14.1",
    "class-transformer":        "^0.5.1",
    # UI component libraries
    "@mui/material":            "^5.16.0",
    "@mui/icons-material":      "^5.16.0",
    "@emotion/react":           "^11.13.0",
    "@emotion/styled":          "^11.13.0",
    "tailwindcss":              "^3.4.0",
    "postcss":                  "^8.4.0",
    "autoprefixer":             "^10.4.0",
    "@shadcn/ui":               "^0.0.4",
    "lucide-react":             "^0.400.0",
    # DB drivers
    "pg":                       "^8.12.0",
    "mysql2":                   "^3.10.0",
    "sqlite3":                  "^5.1.7",
    "mongoose":                 "^8.4.0",
    "ioredis":                  "^5.4.0",
    # Testing
    "jest":                     "^29.7.0",
    "@types/jest":              "^29.5.0",
    "vitest":                   "^1.6.0",
    "@testing-library/react":   "^16.0.0",
    "supertest":                "^7.0.0",
    # Build tools
    "typescript":               "^5.4.0",
    "tsx":                      "^4.19.0",
    "vite":                     "^5.3.0",
    "@vitejs/plugin-react":     "^4.3.0",
    "esbuild":                  "^0.21.0",
    # Type definitions
    "@types/node":              "^20.14.0",
    "@types/express":           "^4.17.21",
    "@types/react":             "^18.3.0",
    "@types/react-dom":         "^18.3.0",
    "@types/cors":              "^2.8.17",
    "@types/bcryptjs":          "^2.4.6",
    "@types/jsonwebtoken":      "^9.0.6",
    "@types/pg":                "^8.11.0",
    # Observability
    "winston":                  "^3.13.0",
    "pino":                     "^9.3.0",
    "@sentry/node":             "^8.13.0",
    # Misc
    "dotenv":                   "^16.4.0",
    "uuid":                     "^10.0.0",
    "dayjs":                    "^1.11.11",
    "lodash":                   "^4.17.21",
    "@types/lodash":            "^4.17.0",
    "socket.io":                "^4.7.0",
    "socket.io-client":         "^4.7.0",
    "bull":                     "^4.13.0",
    "bullmq":                   "^5.8.0",
    "swagger-ui-express":       "^5.0.1",
    "class-transformer":        "^0.5.1",
    "nest-cli":                 "^10.0.0",
    "@nestjs/cli":              "^10.4.0",
}


def pinned_python(package_name: str) -> str:
    """
    Retorna la versión pinned para un paquete Python.
    Si no está en la tabla, retorna el nombre sin versión.
    La clave puede tener o no extras (e.g. 'fastapi' o 'fastapi[all]').

    Ejemplos:
        pinned_python("fastapi")      → "fastapi>=0.111.0,<0.120.0"
        pinned_python("unknown-pkg")  → "unknown-pkg"
    """
    # Normalizar: comparar sin extras y en minúscula
    base = package_name.split("[")[0].lower()
    # Buscar por base primero
    for key, val in _PYTHON.items():
        if key.split("[")[0].lower() == base:
            return val
    return package_name  # fallback: sin pinning


def pinned_npm(package_name: str) -> str:
    """
    Retorna la versión pinned para un paquete npm.
    Si no está en la tabla, retorna "latest".

    Ejemplos:
        pinned_npm("react")     → "^18.3.0"
        pinned_npm("unknown")   → "latest"
    """
    return _NPM.get(package_name, "latest")


def apply_pinning_to_requirements(requirements_list: list[str]) -> list[str]:
    """
    Toma una lista de paquetes Python (con o sin versión) y aplica pinning
    a los que no tienen versión especificada.

    Ejemplo:
        ["fastapi", "pydantic>=2.0", "unknown-pkg"]
        → ["fastapi>=0.111.0,<0.120.0", "pydantic>=2.0", "unknown-pkg"]
    """
    result = []
    for pkg in requirements_list:
        pkg = pkg.strip()
        if not pkg or pkg.startswith("#"):
            result.append(pkg)
            continue
        # Si ya tiene especificación de versión, no tocar
        if any(op in pkg for op in (">=", "<=", "==", "!=", "~=", ">")):
            result.append(pkg)
        else:
            result.append(pinned_python(pkg))
    return result
