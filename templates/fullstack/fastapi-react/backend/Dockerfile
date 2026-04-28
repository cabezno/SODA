FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv para gestión de paquetes ultra-rápida
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copiar archivos de dependencias
COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml

# Copiar el resto de la aplicación
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
