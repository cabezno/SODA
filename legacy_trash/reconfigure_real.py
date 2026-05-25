import os
from pathlib import Path
import json

root = Path("projects/APLICACION/source")

# 1. Update docker-compose.yml to restore real builds and use standard ports
dc_path = root / "docker-compose.yml"
dc_content = """version: '3.8'

services:
  # Base Database
  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=soda
      - POSTGRES_PASSWORD=soda
      - POSTGRES_DB=soda
    ports:
      - "5432:5432"

  # CEO Gateway - Central entry point for backend
  ceo-gateway:
    build: ./ceo-core-002-gateway
    ports:
      - "3006:3006"
    environment:
      - DATABASE_URL=postgresql://soda:soda@db:5432/soda
      - BRAIN_URL=http://ceo-brain:3005
    depends_on:
      - db

  # CEO Brain - Logic
  ceo-brain:
    build: ./ceo-core-002-brain
    ports:
      - "3005:3005"

  # Frontend - The actual interface
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "80:80"
    environment:
      - VITE_API_URL=http://localhost:3006
    depends_on:
      - ceo-gateway
"""
dc_path.write_text(dc_content, encoding="utf-8")

# 2. Fix Frontend Dockerfile (Bun issues) -> Use simpler Nginx build if possible or fix Bun
# For now, let's make it a simple React build
frontend_dockerfile = root / "frontend" / "Dockerfile"
frontend_dockerfile.write_text("""FROM node:18-alpine as build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
""", encoding="utf-8")

# 3. Ensure frontend/package.json has build script
frontend_pkg = root / "frontend" / "package.json"
if frontend_pkg.exists():
    pkg_data = json.loads(frontend_pkg.read_text(encoding="utf-8"))
    pkg_data["scripts"]["build"] = "vite build"
    frontend_pkg.write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")

print("Project reconfiguration for REAL interface completed.")
