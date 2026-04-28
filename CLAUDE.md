# SODA — Claude Code Context

Sistema multi-agente de desarrollo de software. Orquestación determinística Python + modelos locales (Qwen/Ollama) + cloud (Claude Sonnet, Gemini Pro/Flash).

## Stack

- Python 3.11.9, Windows 11 nativo (NO WSL2)
- Claude Sonnet 4.6 (`claude-sonnet-4-6`), Gemini 2.5 Pro/Flash, Qwen 2.5-coder:7b (Ollama)
- FastAPI + uvicorn + pywebview + Monaco Editor
- Docker Desktop (npipe Windows) para validación de sintaxis
- python-telegram-bot v22 (`@Soda_black_bot`, chat_id `7349653298`)

## Pipeline

```
CAP → WISDOM → REQ → ARCH → PLAN → DEV → EVOLUTION → DONE
```

- **CAP**: Gemini selecciona skills + perfil (`skill_matcher`, `profile_matcher`)
- **WISDOM**: Gemini detecta ambigüedades (`wisdom_agent`)
- **REQ**: Claude genera `blueprint.json` (`requirements_interviewer`)
- **ARCH**: Gemini genera `architecture.json` con módulos y DAG (`global_architect`)
- **PLAN**: Python puro construye grafo de ejecución (`dependency_graph.py`)
- **DEV**: Qwen genera archivos; escala a Claude tras 3 fallos (`code_generator.py`)
- **EVOLUTION**: Gemini captura learnings en el perfil (`profile_evolution`)

## Archivos críticos

| Archivo | Rol |
|---------|-----|
| `kernel/orchestrator.py` | Pipeline completo, entry point principal |
| `kernel/code_generator.py` | Generación con retry Qwen×3 → Claude |
| `kernel/dependency_graph.py` | DAG + Kahn topological sort |
| `kernel/intelligence/context_health_monitor.py` | Monitoreo pasivo tokens/errores |
| `kernel/intelligence/goal_interpreter.py` | Interpreta cambios post-generación |
| `kernel/intelligence/impact_analyzer.py` | Análisis transitivo de impacto |
| `kernel/lineage/branching.py` | Copia workspace en cambios estructurales |
| `ui/server.py` | FastAPI + WebSocket; carga `.env` explícitamente |
| `prompts/gemini/global_architect.md` | Prompt crítico — `dependencias` deben ser nombres de módulo, NO rutas |

## Reglas de arquitectura

**`architecture.json` — campo `dependencias`**: debe contener nombres exactos del campo `nombre` de otros módulos del array `modulos`. Rutas de archivo y librerías externas NO van aquí — el `DependencyGraph` las filtraría. Ver `prompts/gemini/global_architect.md`.

**Escalación de código**: `CodeGenerator` reintenta Qwen 3 veces. Si falla, escala a Claude. Si Claude falla, guarda el archivo con `validated=False` y continúa (no aborta el pipeline).

**Notificaciones UI**: `_notify()` usa `timeout=0.05s` (fire-and-forget). Nunca bloquea el pipeline.

**`.env`**: se carga explícitamente en `server.py` y `orchestrator.py` con `load_dotenv(Path(...).parent / ".env")`. Variables: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OLLAMA_BASE_URL`, `TELEGRAM_BOT_TOKEN`.

## Conocimiento base

**Skills** (`skills/base/`): `skill_fastapi`, `skill_sqlite`, `skill_react`, `skill_jwt_auth`, `skill_rest_api`
- Estructura: `manifest.yaml` + `system_prompt.md` + `knowledge/*.md`

**Perfiles** (`profiles/base/`): `profile_web_fullstack`, `profile_backend_api`, `profile_general_dev`
- Estructura: `identity.yaml` + `experience/` + `style/`

**Prompts** (`prompts/<provider>/<role>.md`): cargados por `ContextBuilder.build_payload()`. Si no existe el archivo, usa fallback genérico.

## Tests

```bash
python -m pytest tests/ -v   # 47 tests, ~7s, sin API keys ni Docker
```

- `tests/test_unit.py` — componentes determinísticos (28 tests)
- `tests/test_pipeline.py` — pipeline completo con drivers mockeados (19 tests)
- Los tests stub dependencias opcionales no instaladas (`docker`, `anthropic`, etc.) vía `sys.modules` antes del import.

## ContextHealthMonitor — umbrales calibrados

| Umbral | Valor | Razón |
|--------|-------|-------|
| `TOKEN_WARN_THRESHOLD` | 80,000 | ~80% límite 100k |
| `SLOW_CALL_S` | 30s | Qwen normal: 15-25s |
| `ERROR_RATE_WARN` | 0.50 | Evita falso positivo en burst Qwen×3→Claude |
| `ROLLING_WINDOW` | 15 | Suaviza ráfagas de escalación |

## Operaciones post-generación

- **`modify(project, request)`**: GoalInterpreter clasifica cambio → ImpactAnalyzer calcula afectados → BranchManager crea branch si `change_type in {structural, scope, new_module}` Y `requires_regeneration=True`
- **`refound(project)`**: RefoundationEngine resume proyecto → `run()` con descripción condensada
- **Telegram**: `/status`, `/projects`, `/pair` — bot pareado con `soda_config.json`

## Decisiones que NO cambiar sin analizar impacto

- `_notify()` timeout=0.05s — si se aumenta, bloquea el pipeline
- `load_dotenv()` explícito en cada entry point — sin esto las keys no se cargan desde la UI
- `DockerSandbox` usa npipe (Windows) — no usar unix socket
