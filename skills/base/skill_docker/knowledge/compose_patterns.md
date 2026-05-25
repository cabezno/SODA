## Docker Compose Patterns

### Python FastAPI + SQLite (single service)

```yaml
version: "3.9"
services:
  api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data      # persist SQLite file
    environment:
      - DATABASE_URL=sqlite:///./data/app.db
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      retries: 3
```

### Node.js + SQLite

```yaml
version: "3.9"
services:
  api:
    build: .
    ports:
      - "3000:3000"
    volumes:
      - ./data:/app/data
    environment:
      - NODE_ENV=production
      - DB_PATH=/app/data/app.db
```

### Multi-service (FastAPI backend + React frontend)

```yaml
version: "3.9"
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - DATABASE_URL=sqlite:///./data/app.db

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
    depends_on:
      - backend
```

### Minimal Dockerfile — Python

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Minimal Dockerfile — Node.js

```dockerfile
FROM node:20-slim
WORKDIR /app
COPY package*.json .
RUN npm ci --production
COPY . .
CMD ["node", "main.js"]
```
