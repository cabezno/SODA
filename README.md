# SODA — Software Orchestration & Development Agency

Sistema multi-agente de desarrollo de software: orquestación determinística en Python con modelos locales (Qwen via Ollama) y cloud (Claude, Gemini, OpenAI).

## Pipeline

```
CAP → WISDOM → REQ → ARCH → PLAN → DEV → EVOLUTION → DONE
```

| Fase | Modelo | Descripción |
|------|--------|-------------|
| **CAP** | Gemini Flash | Selecciona skills y perfil relevantes para el proyecto |
| **WISDOM** | Gemini Flash | Detecta ambigüedades o riesgos antes de generar requerimientos |
| **REQ** | Claude Sonnet | Genera blueprint JSON (funcionalidades, stack, módulos) |
| **ARCH** | Gemini Pro | Diseña arquitectura con módulos, contratos y plan de directorios |
| **PLAN** | Python puro | Construye DAG de dependencias y calcula orden de ejecución |
| **DEV** | Qwen → Claude | Genera cada archivo; escala a Claude si Qwen falla 3 veces |
| **EVOLUTION** | Gemini Flash | Captura learnings del proyecto en el perfil activo |

## Estructura

```
SODA-PROJECT/
├── kernel/
│   ├── orchestrator.py          # Pipeline principal + máquina de estados
│   ├── code_generator.py        # Generación de archivos (Qwen + escalación Claude)
│   ├── dependency_graph.py      # DAG con topological sort (Kahn)
│   ├── docker_sandbox.py        # Validación de sintaxis en Docker
│   ├── drivers/                 # claude_driver, gemini_driver, ollama_driver, openai_driver
│   ├── capabilities/            # skill_matcher, profile_matcher, profile_evolution
│   ├── intelligence/            # wisdom_agent, goal_interpreter, impact_analyzer,
│   │                            # context_health_monitor, refoundation
│   ├── context/                 # context_builder (inyecta skills + perfil en prompts)
│   ├── lineage/                 # project_lineage (log JSON), branching (copia workspace)
│   └── communication/           # telegram_gateway (bot @Soda_black_bot)
├── ui/
│   ├── server.py                # FastAPI + WebSocket + endpoints REST
│   ├── launcher.py              # pywebview (UI nativa)
│   └── static/index.html        # Monaco Editor, objective tree, phase tracker
├── prompts/                     # System prompts por modelo (claude/, gemini/, ollama/)
├── skills/base/                 # skill_fastapi, skill_sqlite, skill_react, skill_jwt_auth, skill_rest_api
├── profiles/base/               # profile_web_fullstack, profile_backend_api, profile_general_dev
├── projects/                    # Workspaces generados (gitignored)
└── tests/
    ├── test_unit.py             # 28 tests: DependencyGraph, BranchManager, HealthMonitor, etc.
    └── test_pipeline.py         # 19 tests: pipeline completo con drivers mockeados
```

## Setup

**Requisitos:** Python 3.11+, Docker Desktop, Ollama con `qwen2.5-coder:7b`

```bash
# 1. Instalar dependencias
pip install -e .

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus API keys

# 3. Levantar Ollama (en otra terminal)
ollama serve
ollama pull qwen2.5-coder:7b
```

### `.env`

```
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
OPENAI_API_KEY=sk-...
OLLAMA_BASE_URL=http://localhost:11434
TELEGRAM_BOT_TOKEN=...        # Opcional — bot de notificaciones
```

## Uso

### UI (recomendado)

```bash
python -m ui.launcher
```

Abre la UI nativa con Monaco Editor. Desde ahí: escribí el objetivo, ejecutá el pipeline, seguí las fases en tiempo real, modificá el proyecto generado.

### CLI

```bash
python kernel/orchestrator.py
```

Edita el `__main__` con la descripción del proyecto que querés generar.

## Tests

```bash
python -m pytest tests/ -v
```

47 tests, ~7 segundos. No requieren API keys ni Docker.

## Skills y Perfiles

### Agregar un skill

1. Crear carpeta `skills/base/skill_<nombre>/`
2. Agregar `manifest.yaml`:

```yaml
name: skill_<nombre>
category: <categoria>
description: <descripción para que Gemini lo seleccione>
applies_to_roles:
  - code_generator
  - global_architect
activation_keywords:
  - palabra1
  - palabra2
version: "1.0"
```

3. Agregar `system_prompt.md` con instrucciones para el generador de código.
4. Opcional: carpeta `knowledge/` con archivos `.md` de referencia.

### Agregar un perfil

1. Crear carpeta `profiles/base/profile_<nombre>/`
2. Agregar `identity.yaml`:

```yaml
name: profile_<nombre>
display_name: <nombre legible>
description: <descripción para que Gemini lo seleccione>
activation_signals:
  - señal1
  - señal2
skills_included:
  - skill_fastapi
version: "1.0"
```

## Operaciones post-generación

### Modificar un proyecto

Desde la UI, panel "Modify": describí el cambio en lenguaje natural. El `GoalInterpreter` clasifica el cambio y el `ImpactAnalyzer` calcula módulos afectados. Si el cambio es estructural, se crea un branch automático.

### Refundar un proyecto

Cuando el contexto se acumula demasiado (proyectos largos), "Refound" resume el estado actual y lanza un nuevo pipeline con descripción condensada + decisiones clave preservadas.

## Telegram

El bot `@Soda_black_bot` notifica eventos clave (inicio, checkpoints, errores, finalización). Configurar `TELEGRAM_BOT_TOKEN` en `.env` y ejecutar `/pair` desde el bot para vincular el chat.

## Integracion De Multiples IAs

SODA ahora incluye un hub de proveedores IA con fallback configurable por API. Esto permite sumar o reordenar IAs sin tocar el core del pipeline.

Configuralo en `soda_config.json`:

```json
{
  "ai_routing": {
    "claude": ["claude", "gemini", "openai", "ollama"],
    "gemini": ["gemini", "claude", "openai", "ollama"],
    "ollama": ["ollama", "claude", "gemini", "openai"],
    "openai": ["openai", "claude", "gemini", "ollama"]
  }
}
```

Cada clave define la cadena de fallback cuando esa IA es la primaria para una fase.

Tambien podes definir la IA primaria por fase (rol de prompt):

```json
{
  "ai_phase_provider": {
    "requirements_interviewer": "claude",
    "global_architect": "gemini",
    "docs_generator": "openai"
  }
}
```

Si una fase tiene override, SODA usa ese proveedor como primario y mantiene fallback segun `ai_routing`.

Tambien podes activar/desactivar el smoke check de runtime del pipeline:

```json
{
  "runtime_smoke_check": true
}
```

Cuando esta activo, SODA intenta un probe HTTP rapido al finalizar para detectar si la app parece estar disponible.

## ContextHealthMonitor

Monitoreo pasivo de salud del contexto durante el pipeline:

| Umbral | Valor | Acción |
|--------|-------|--------|
| Tokens acumulados | > 80,000 | Nivel 3 — considerar refundación |
| Error rate (ventana 15 llamadas) | > 50% | Nivel 2 — revisar escalación |
| Llamadas lentas | > 30s c/u, 2+ recientes | Nivel 1 — posible throttling |
