# Build Infrastructure Checklist — Python FastAPI

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `requirements.txt` | Sin esto `pip install` no puede instalar dependencias |
| `pyproject.toml` | Metadatos del proyecto, configuración de herramientas (black, ruff, pytest) |
| `.env.example` | Documenta todas las variables de entorno requeridas |
| `.env` | Variables reales en local (nunca commitear; ignorado por .gitignore) |
| `.gitignore` | Debe excluir `.env`, `__pycache__`, `*.pyc`, `venv/`, `.venv/` |
| `main.py` | Entry point de la aplicación FastAPI con `app = FastAPI(...)` |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no lanza el servidor |
| `.vscode/launch.json` | Sin esto F5 no inicia el debugger |
| `.vscode/extensions.json` | Recomienda Python, Pylance, REST Client |

## Contenido mínimo de requirements.txt

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
```

## Contenido mínimo de pyproject.toml

```toml
[project]
name = "my-fastapi-app"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 88

[tool.black]
line-length = 88
```

## Contenido mínimo de .env.example

```
APP_NAME=MyApp
APP_ENV=development
APP_PORT=8000
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=changeme_generate_with_openssl_rand_hex_32
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

## .vscode/tasks.json

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Install dependencies",
      "type": "shell",
      "command": "pip install -r requirements.txt",
      "group": "build",
      "presentation": { "reveal": "always" }
    },
    {
      "label": "Run dev server",
      "type": "shell",
      "command": "uvicorn main:app --reload --port 8000",
      "group": { "kind": "build", "isDefault": true },
      "presentation": { "reveal": "always", "panel": "dedicated" }
    },
    {
      "label": "Run tests",
      "type": "shell",
      "command": "python -m pytest tests/ -v",
      "group": { "kind": "test", "isDefault": true }
    }
  ]
}
```

## .vscode/launch.json

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI: Debug",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload", "--port", "8000"],
      "jinja": true,
      "justMyCode": true,
      "env": { "PYTHONDONTWRITEBYTECODE": "1" }
    }
  ]
}
```

## .vscode/extensions.json

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.pylance",
    "ms-python.debugpy",
    "charliermarsh.ruff",
    "humao.rest-client",
    "42crunch.vscode-openapi"
  ]
}
```

## Pasos que debe ejecutar el usuario para correr el proyecto

1. Instalar Python >= 3.11 (https://python.org/downloads/)
2. Crear y activar entorno virtual: `python -m venv .venv && .venv\Scripts\activate` (Windows) o `source .venv/bin/activate` (Linux/Mac)
3. Instalar dependencias: `pip install -r requirements.txt`
4. Copiar `.env.example` a `.env` y completar valores reales
5. Correr servidor: `uvicorn main:app --reload`
6. Abrir docs: http://localhost:8000/docs

## Build commands

| Acción | Comando |
|--------|---------|
| Crear venv | `python -m venv .venv` |
| Activar venv (Windows) | `.venv\Scripts\activate` |
| Activar venv (Linux/Mac) | `source .venv/bin/activate` |
| Instalar deps | `pip install -r requirements.txt` |
| Dev server | `uvicorn main:app --reload` |
| Prod server | `uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4` |
| Tests | `python -m pytest tests/ -v` |
| Tests con coverage | `python -m pytest tests/ -v --cov=. --cov-report=html` |
| Linting | `ruff check . && black --check .` |

## Reglas del auditor (checklist para código generado)

1. **Entry point correcto** — `main.py` debe tener `app = FastAPI(...)` y los routers montados con `app.include_router()`; no exponer rutas directamente en `main.py`
2. **Variables de entorno via pydantic-settings** — nunca `os.environ["KEY"]` directo; usar clase `Settings(BaseSettings)` con `model_config = SettingsConfigDict(env_file=".env")`
3. **Routers en carpeta `routers/`** — cada dominio en su propio archivo con `router = APIRouter(prefix="/items", tags=["items"])`
4. **Modelos Pydantic v2** — usar `model_validator`, `field_validator` (no `@validator` de v1); `BaseModel` para schemas, `SQLModel` o `Base` de SQLAlchemy para ORM
5. **CORS configurado** — `CORSMiddleware` presente si hay frontend; origins leídos de `.env`, no hardcodeados
6. **Lifespan en lugar de `@app.on_event`** — usar `@asynccontextmanager` + `app = FastAPI(lifespan=lifespan)` para startup/shutdown
7. **HTTPException en lugar de respuestas raw de error** — todos los errores vía `raise HTTPException(status_code=..., detail=...)`
8. **`requirements.txt` completo** — verificar que cada `import` en el código tiene su paquete correspondiente en `requirements.txt`

## Errores comunes de generación AI

- Usar `@app.on_event("startup")` (deprecado) en lugar de `lifespan`
- Importar `from pydantic import validator` (Pydantic v1) en lugar de `field_validator` (v2)
- Olvidar `uvicorn[standard]` — instalar solo `uvicorn` sin el extra causa error con websockets y recarga
- Poner todas las rutas en `main.py` en lugar de usar `APIRouter`
- Hardcodear `SECRET_KEY = "secret"` sin leerlo del `.env`
- Olvidar el campo `response_model` en los decoradores de ruta
- No incluir `.gitignore` — el `.env` con secretos queda expuesto
- Usar `async def` con drivers síncronos (psycopg2, sqlite3) sin `run_in_executor`
- Olvidar `python-dotenv` en `requirements.txt` cuando se usa `load_dotenv()`
- No crear `tests/` con al menos un `conftest.py` vacío (pytest no encuentra el directorio)
