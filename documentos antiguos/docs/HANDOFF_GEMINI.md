# SODA — Handoff Document para Gemini

> Este documento es para que un modelo de IA (Gemini u otro) pueda retomar el desarrollo
> de SODA sin perder contexto. Leerlo completo antes de actuar.

---

## 1. Qué es SODA

Sistema multi-agente de desarrollo de software. A partir de una descripción en lenguaje
natural, genera aplicaciones completas coordinando modelos de IA locales (Ollama/Qwen) y
cloud (Claude, Gemini) con orquestación determinística en Python.

Documentación completa de arquitectura: `docs/SODA_v3_Documento_Def.md`  
Brief operativo original: `docs/SODA_BRIEF_CLAUDE_CODE.md`

---

## 2. Estado actual (2026-04-20)

### Fases completadas

**Fase A — Fundamentos:** COMPLETA
- Drivers funcionales: `kernel/drivers/claude_driver.py`, `gemini_driver.py`, `ollama_driver.py`
- ContextBuilder: `kernel/context/context_builder.py`
- Test de drivers: `test_drivers.py` (3/3 OK)

**Fase B — Kernel Core:** COMPLETA
- Orchestrator con máquina de estados: `kernel/orchestrator.py`
- DependencyGraph con topological sort: `kernel/dependency_graph.py`
- DockerSandbox para validación de código: `kernel/docker_sandbox.py`
- CodeGenerator con escalado Qwen→Claude: `kernel/code_generator.py`
- GoalIntegrityValidator: `kernel/integrity/goal_integrity_validator.py`
- **Verificado:** genera app CRUD funcional (FastAPI + SQLite) desde descripción en lenguaje natural

### Fase en curso

**Fase C — UI Básica:** EN PROGRESO
- FastAPI server + WebSocket: PARCIAL (estructura creada, falta integración con Orchestrator)
- Monaco Editor: PENDIENTE
- pywebview wrapper: PENDIENTE
- Panel de progreso en tiempo real: PENDIENTE
- Árbol de objetivos (vista): PENDIENTE

---

## 3. Cómo correr el proyecto

```bash
# Activar entorno
venv/Scripts/activate  # Windows

# Test drivers
python test_drivers.py

# Pipeline completo (genera un proyecto desde descripción)
python -m kernel.orchestrator

# UI (cuando Fase C esté completa)
python -m ui.launcher
```

**Requisitos de entorno:**
- Python 3.11.9
- Ollama corriendo con `qwen2.5-coder:7b` (`ollama serve`)
- Docker Desktop corriendo
- `.env` con `ANTHROPIC_API_KEY` y `GEMINI_API_KEY`

---

## 4. Estructura de archivos clave

```
SODA-PROJECT/
├── kernel/
│   ├── orchestrator.py          # Máquina de estados, entry point del pipeline
│   ├── dependency_graph.py      # DAG de módulos (Python puro)
│   ├── docker_sandbox.py        # Ejecución aislada en Docker
│   ├── code_generator.py        # Generación con escalado Qwen→Claude
│   ├── context/
│   │   └── context_builder.py   # Ensamblado de contextos para IAs
│   ├── drivers/
│   │   ├── claude_driver.py     # claude-sonnet-4-6
│   │   ├── gemini_driver.py     # gemini-2.5-pro (REST API, síncrono)
│   │   └── ollama_driver.py     # qwen2.5-coder:7b (async)
│   └── integrity/
│       └── goal_integrity_validator.py  # Validación de metadata goal_id
├── ui/                          # [FASE C - EN PROGRESO]
│   ├── server.py                # FastAPI app
│   ├── websocket_handler.py     # WebSocket broadcaster
│   └── launcher.py              # pywebview starter
├── prompts/
│   ├── claude/                  # requirements_interviewer, code_generator, etc.
│   ├── gemini/                  # global_architect
│   └── ollama/                  # code_generator
├── projects/                    # Workspaces generados (ignorados por git excepto estructura)
├── .env                         # API keys (NO versionar)
└── pyproject.toml
```

---

## 5. Arquitectura del Orchestrator (estado actual)

```python
class ProjectState(Enum):
    IDLE → REQUIREMENTS → ARCHITECTURE → PLANNING → DEVELOPMENT → DONE/FAILED

# Fases implementadas:
# Fase 1: requirements  → Claude Sonnet → blueprint.json
# Fase 2: architecture  → Gemini Pro    → architecture.json
# Fase 3: planning      → Python puro   → execution_plan.json (DAG)
# Fase 4: development   → Qwen/Claude   → source/ (archivos con metadata goal_id)
```

**Escalado de modelos en desarrollo:**
```
Qwen local intento 1 → Qwen local intento 2 → Qwen local intento 3 → Claude Sonnet → FAILED
```

---

## 6. Issues conocidos y decisiones tomadas

### Issues conocidos
1. **Inconsistencia entre módulos generados:** nombres de funciones/clases pueden variar
   entre archivos (ej: `get_tasks` vs `get_all_tasks`). Causa: cada archivo se genera sin
   ver las interfaces de los vecinos. Fix futuro: contratos más explícitos en el prompt.
   
2. **GeminiDriver es síncrono:** usa `requests` en lugar de SDK oficial. Funciona pero
   no es ideal. Fix: migrar a `google-generativeai` async cuando sea prioridad.

3. **DEBUG logs de Gemini:** el driver imprime `[DEBUG] Testeando modelo...` cada vez
   que no tiene un modelo activo en caché. Mejorar con logging apropiado.

4. **Docker timeout en Windows:** aumentado a 120s para Gemini. En máquinas lentas
   puede necesitar más.

### Decisiones definitivas (NO cambiar sin consultar al usuario)
- Windows 11 nativo (NO WSL2)
- `uv` como gestor Python (aunque el proyecto actual usa venv convencional)
- Claude Sonnet 4.6 para roles de juicio crítico
- Gemini 2.5 Pro para arquitectura y contexto amplio
- Qwen local para volumen de código
- Monaco Editor + pywebview + FastAPI para UI
- Metadata `goal_id` obligatoria en todos los archivos `.py` generados

---

## 7. Próximos pasos — Fase C

### Tarea C1: FastAPI server con WebSocket (PRIORIDAD ALTA)

Crear `ui/server.py` y `ui/websocket_handler.py`.

El WebSocket debe:
- Tener un `ConnectionManager` que maneje múltiples clientes
- Permitir que el Orchestrator emita eventos de progreso
- Eventos: `{"type": "phase_start", "phase": "requirements"}`,
  `{"type": "file_generated", "filepath": "...", "validated": true}`,
  `{"type": "checkpoint", "number": 1, "message": "..."}`

Integración con Orchestrator:
- El Orchestrator acepta un callback opcional `on_event(event: dict)`
- Si no se pasa callback, funciona igual que ahora (modo CLI)
- El server pasa su WebSocket broadcaster como callback

### Tarea C2: UI básica con panel de progreso

`ui/static/index.html` — layout de 3 columnas:
- Izquierda: árbol de objetivos (inicialmente lista simple)
- Centro: log de progreso en tiempo real (eventos del WebSocket)
- Derecha: estado del proyecto actual

No usar frameworks pesados. HTML + CSS + JS vanilla.

### Tarea C3: pywebview wrapper

`ui/launcher.py` — levanta FastAPI en thread y abre ventana nativa:
```python
import webview, threading, uvicorn
from ui.server import app

def start():
    threading.Thread(target=lambda: uvicorn.run(app, port=8000), daemon=True).start()
    webview.create_window("SODA", "http://127.0.0.1:8000", width=1400, height=900)
    webview.start()
```

### Tarea C4: Monaco Editor (puede ir después de C1-C3)

Cargar Monaco desde CDN. Mostrarlo en el panel central cuando un archivo es seleccionado
del árbol. Solo lectura inicialmente.

---

## 8. Protocolo de trabajo

**OBLIGATORIO antes de actuar:**
1. Leer el estado actual de los archivos (`ls`, `cat` de archivos clave)
2. Proponer → esperar aprobación → ejecutar
3. Un objetivo concreto por vez
4. Commit después de cada tarea verificada

**Al encontrar ambigüedades:**
No asumir. Presentar opciones con consecuencias concretas.

**Al modificar kernel/:**
Los principios de diseño son rígidos. No agregar IA donde debe ser Python puro.
No mezclar responsabilidades de componentes.

---

## 9. Comandos útiles

```bash
# Ver proyectos generados
ls projects/

# Ver un proyecto específico
ls projects/proj_XXXXX/source/

# Correr un proyecto generado
cd projects/proj_XXXXX/source
python -m uvicorn app.main:app --port 8002

# Test de drivers
python test_drivers.py

# Git log
git log --oneline
```

---

## 10. Contexto de hardware

- CPU: Intel i9 13900
- RAM: 64 GB DDR5
- GPU: NVIDIA GTX 5070 Ti (16 GB VRAM)
- SO: Windows 11 nativo
- Ollama corre nativamente en Windows con GPU

---

*Documento generado el 2026-04-20. Verificar estado real de archivos antes de actuar.*
