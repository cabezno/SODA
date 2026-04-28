# Runtime para Python con UV
FROM python:3.11-slim

WORKDIR /app

# Herramientas de sistema necesarias
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Instalar UV (Gestor ultra-rápido de Python)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Pre-instalar herramientas de calidad de código
RUN uv pip install --system ruff pytest mypy

ENV PYTHONUNBUFFERED=1
CMD ["python3"]
