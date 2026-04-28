# Runtime para Node.js y TypeScript
FROM node:20-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Instalar PNPM como gestor de paquetes preferido
RUN npm install -g pnpm tsx tsup vitest typescript

CMD ["node"]
