# SODA - Brief Operativo para Claude Code

> **INSTRUCCIONES INICIALES PARA CLAUDE CODE**
> 
> Este documento es tu brief maestro para trabajar en el proyecto SODA. Lee este archivo completo ANTES de hacer cualquier acción. 
>
> **Protocolo de inicio obligatorio:**
> 1. Ejecutar `ls` o equivalente para ver qué hay en la carpeta actual
> 2. Leer cualquier archivo existente antes de proponer crear nuevos
> 3. NO asumir que la carpeta está vacía (el usuario ya creó cosas)
> 4. Reportar al usuario qué encontraste ANTES de proponer próximos pasos
> 5. No crear archivos hasta tener claridad sobre el estado actual
>
> **Protocolo de trabajo:**
> - Proponer → Esperar aprobación → Ejecutar
> - Un objetivo concreto por vez, no tareas agregadas
> - Commit frecuente con mensajes descriptivos
> - Preguntar ante ambigüedades, no asumir

---

## 1. Identidad del Proyecto

**Nombre:** SODA (Software Orchestration & Development Agency)

**Qué es:** Sistema multi-agente de desarrollo de software que combina modelos de IA locales (Ollama) y cloud (Claude, Gemini) con orquestación determinística en Python.

**Qué NO es:** 
- No es un generador de código simple
- No es un wrapper de LLM
- No es un IDE
- No reemplaza a Claude Code (es un sistema distinto con propósito distinto)

**Objetivo:** A partir de una descripción en lenguaje natural, construir aplicaciones completas mediante coordinación de agentes especializados, con el usuario en control vía checkpoints estratégicos.

---

## 2. Estado Actual del Proyecto

**IMPORTANTE:** Cuando inicies una sesión, verificá el estado real ejecutando comandos de inspección. No asumas basándote en este documento. El documento describe el plan; el estado real puede diferir.

**Qué debería existir (verificar):**
- Carpeta raíz del proyecto (estás ahí)
- Posiblemente: archivos iniciales creados por el usuario sin seguir completamente el plan
- Posiblemente: algunos archivos de configuración parciales

**Qué ya confirmamos que funciona en el sistema del usuario:**
- Python 3.11.9 instalado globalmente
- Node.js v24.15.0 instalado
- Docker Desktop corriendo (4 procesos activos, 7 contenedores en ejecución al momento de última verificación)
- Ollama funcionando con modelo `qwen2.5-coder:7b` descargado
- Claude Code instalado globalmente vía npm
- Sistema operativo: Windows 11 nativo (NO WSL2)

**Qué todavía NO se ha hecho (verificar):**
- Estructura completa de carpetas de SODA
- Drivers de IA (Claude, Gemini, Ollama)
- ContextBuilder
- Orchestrator
- Cualquier componente del Kernel
- UI
- Tests

**Credenciales disponibles:**
- API key de Anthropic (el usuario la tiene)
- API key de Gemini (el usuario la tiene)
- Deben ir en un archivo `.env` en la raíz, NUNCA en código versionado

---

## 3. Principios No Negociables

Estos principios deben respetarse siempre. Si una decisión de implementación contradice uno de estos, detenerse y consultar al usuario.

**P1. Coordinación por código, juicio por IA.**
Las decisiones de routing, dependencias y control de flujo son Python determinístico. Las IAs solo intervienen donde se requiere juicio real. No crear "agentes coordinadores" - son Python puro.

**P2. Contextos mínimos.**
Cada llamada a IA recibe solo la información estrictamente necesaria. Más contexto no es mejor contexto.

**P3. El código tiene trazabilidad obligatoria.**
Todo archivo generado tiene metadata con `goal_id` que lo vincula a un objetivo. Sin goal_id, no se genera.

**P4. Escalado gradual de modelos.**
- Qwen local (gratis) → para volumen
- Gemini API → para contexto amplio
- Claude API → para juicio crítico
- Escalar de local a cloud solo cuando falla el local 3 veces

**P5. Usuario en control.**
Cada fase importante termina con un checkpoint donde el usuario aprueba antes de continuar. Nunca avanzar sin su aprobación explícita en los puntos definidos.

**P6. Asignación automática de capacidades.**
Skills y perfiles los asigna el sistema, no el usuario. El usuario ve el resultado, no navega catálogos.

**P7. Integridad estructural, no remedial.**
No "limpiar huérfanos" después de crearlos. Diseñar para que no puedan existir estructuralmente.

---

## 4. Stack Técnico Confirmado

**Runtime:**
- Python 3.11+ (async con asyncio)
- Node.js 24 (para Claude Code y herramientas JS auxiliares)

**Gestión de paquetes Python:**
- `uv` (Astral). NO usar pip ni conda.
- Instalar con: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

**Dependencias Python principales (orden de instalación recomendado):**

Fase A (mínimo viable para drivers):
```
anthropic
google-generativeai
ollama
python-dotenv
```

Fase B (kernel básico):
```
fastapi
uvicorn
websockets
docker
watchdog
pygithub
gitpython
pydantic
```

Fase C (conocimiento y UI):
```
chromadb
pywebview
sqlalchemy
rich
```

Fase D (documentos y comunicación):
```
pypdf
python-docx
unstructured
python-telegram-bot
```

**NO instalar todo de una.** Ir agregando según la fase en la que estés.

**Modelos de IA:**

Locales (vía Ollama):
- Ya descargado: `qwen2.5-coder:7b`
- Recomendado descargar pronto: `qwen2.5-coder:14b` (mejor calidad, necesita ~9GB)
- Opcional más adelante: `deepseek-coder-v2:16b`

Cloud:
- Claude Sonnet 4.5 (modelo id: `claude-sonnet-4-5-20250929` - verificar con el usuario si cambió)
- Gemini 2.5 Pro (modelo id: `gemini-2.5-pro`)
- Gemini 2.5 Flash (modelo id: `gemini-2.5-flash`)

**Infraestructura:**
- Docker Desktop (ya instalado, verificar que `docker ps` funciona en PowerShell)
- Git + GitHub (verificar que el usuario tenga cuenta y acceso)

**Entorno de ejecución:**
- Windows 11 nativo (NO WSL2)
- Rutas usar forward slash en código Python (`pathlib.Path` resuelve esto)
- Evitar rutas con espacios o en OneDrive

---

## 5. Arquitectura del Sistema

### 5.1 Vista de Capas

```
INTERFAZ
├── Ventana nativa (pywebview + Monaco + HTML/JS)
├── Canales externos (Telegram primero, WhatsApp futuro)
└── CLI para desarrollo (primera fase)

KERNEL (FastAPI + asyncio)
├── Orquestación: Orchestrator, DependencyGraph, DockerSandbox, Watchdog, GitManager
├── Inteligencia: ContextBuilder, KnowledgeOrchestrator, WisdomAgent, GoalInterpreter, ImpactAnalyzer, ReferenceAnalyzer
├── Integridad: GoalIntegrityValidator, ContextHealthMonitor, ProjectLineage
├── Capacidades: SkillManager, SkillMatcher, ProfileManager, ProfileMatcher, ProfileEvolution
├── Comunicación: MessagingGateway, ProjectChat
└── Drivers: ClaudeDriver, GeminiDriver, OllamaDriver

MODELOS
├── Locales: Qwen 2.5-Coder (7B y 14B), DeepSeek Coder V2
└── Cloud: Claude Sonnet 4.5, Gemini 2.5 Pro, Gemini 2.5 Flash

PERSISTENCIA
├── ChromaDB (múltiples instancias por propósito)
├── SQLite (metadata estructurada)
├── JSON/YAML (configuración y árboles)
└── Git (código generado)
```

### 5.2 Componentes del Kernel - Responsabilidades

Cada componente tiene UNA responsabilidad clara. No mezclar responsabilidades.

**Orchestrator** - Python puro, sin IA
- Máquina de estados del ciclo de vida del proyecto
- Routing de tareas a agentes
- Manejo de fallos y timeouts

**DependencyGraph** - Python puro
- Construye DAG de dependencias entre módulos
- Calcula orden de ejecución (secuencial vs paralelo)

**DockerSandbox** - Python puro
- Ejecuta código generado en contenedores efímeros
- Captura resultados y errores
- Limpia después de uso

**ContextBuilder** - Python puro (pero consulta IAs indirectamente)
- ÚNICO componente que arma contextos para llamadas a IAs
- Aplica skills, perfiles, RAG según necesidad
- Centralizado para optimización

**WisdomAgent** - Usa Gemini Pro
- Genera preguntas proactivas basadas en experiencia
- Modo sugerido, no bloqueante

**GoalInterpreter** - Usa Claude Sonnet
- Traduce pedidos de usuario a cambios en árbol de objetivos
- Clasifica tipo de modificación

**GoalIntegrityValidator** - Python puro
- Garantiza trazabilidad bidireccional código ↔ objetivos
- Bloquea commits con huérfanos

**ContextHealthMonitor** - Python puro
- Observa señales de fatiga del contexto
- Escala alertas según severidad

**SkillMatcher** - Usa Gemini Pro
- Asigna skills automáticamente a proyectos
- Por rol y por módulo

**ProfileMatcher** - Usa Gemini Pro
- Asigna perfiles automáticamente
- Sin intervención del usuario

**ProfileEvolution** - Python + Gemini Flash
- Acumula aprendizajes en perfiles
- Consolida patrones repetidos

---

## 6. Asignación de Modelos por Rol

**Nivel Proyecto (llamadas puntuales):**
| Rol | Modelo |
|-----|--------|
| Entrevistador de requerimientos | Claude Sonnet 4.5 |
| Arquitecto global | Gemini 2.5 Pro |
| Auditor de arquitectura | Claude Sonnet 4.5 |
| Integrador final | Gemini 2.5 Pro |
| Auditor de integración | Claude Sonnet 4.5 |
| Debugger escalado | Claude Sonnet 4.5 |

**Nivel Módulo (volumen alto):**
| Rol | Modelo |
|-----|--------|
| Generador de código | Qwen 2.5-Coder 14B (local) |
| Revisor de código | Qwen 2.5-Coder 7B (local) |
| Generador de tests | DeepSeek Coder V2 Lite (local) |
| Optimizador | Qwen 2.5-Coder 14B (local) |

**Transversales:**
| Rol | Modelo |
|-----|--------|
| Goal Interpreter | Claude Sonnet 4.5 |
| Skill Matcher | Gemini 2.5 Pro |
| Profile Matcher | Gemini 2.5 Pro |
| Wisdom Agent | Gemini 2.5 Pro |
| Project Chat | Gemini 2.5 Flash |
| Resumen de contextos | Gemini 2.5 Flash |

**Estrategia de escalado en caso de fallo:**
```
1. Qwen local genera
2. Si falla tests → Qwen revisa propio código
3. Si falla → Qwen regenera con más contexto
4. Si falla → Escalar a Claude Sonnet
5. Si falla → Checkpoint humano obligatorio
```

---

## 7. Paralelismo

**Configuración Ollama:**
```
OLLAMA_NUM_PARALLEL=3
```

Setear antes de usar. En Windows:
```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL", "3", "User")
```

**Modos:**
- Secuencial (default para proyectos nuevos)
- Paralelo (activable, máx 3 workers simultáneos)

**Aislamiento:** Cada instancia recibe contexto independiente, aunque compartan modelo.

---

## 8. Estructura de Directorios Objetivo

```
soda/
├── .env                    # Secrets, NO versionar
├── .env.example            # Template
├── .gitignore
├── pyproject.toml          # Configuración uv
├── README.md
├── ARCHITECTURE.md         # Este documento o referencia a él
│
├── kernel/
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── dependency_graph.py
│   ├── docker_sandbox.py
│   ├── watchdog_mgr.py
│   ├── git_manager.py
│   ├── context/
│   │   ├── context_builder.py
│   │   └── token_counter.py
│   ├── knowledge/
│   │   ├── knowledge_orchestrator.py
│   │   ├── chromadb_manager.py
│   │   ├── heuristics.py
│   │   └── document_ingestion.py
│   ├── intelligence/
│   │   ├── wisdom_agent.py
│   │   ├── goal_interpreter.py
│   │   ├── impact_analyzer.py
│   │   └── reference_analyzer.py
│   ├── integrity/
│   │   ├── goal_integrity_validator.py
│   │   ├── context_health_monitor.py
│   │   └── project_lineage.py
│   ├── capabilities/
│   │   ├── skill_manager.py
│   │   ├── skill_matcher.py
│   │   ├── profile_manager.py
│   │   ├── profile_matcher.py
│   │   └── profile_evolution.py
│   ├── communication/
│   │   ├── messaging_gateway.py
│   │   ├── project_chat.py
│   │   └── channels/
│   └── drivers/
│       ├── claude_driver.py
│       ├── gemini_driver.py
│       └── ollama_driver.py
│
├── ui/
│   ├── server.py
│   ├── websocket_handler.py
│   ├── launcher.py
│   └── static/
│
├── prompts/                # System prompts por rol
│   ├── claude/
│   ├── gemini/
│   └── ollama/
│
├── skills/
│   ├── base/               # Skills genéricas iniciales
│   └── custom/             # Skills generadas dinámicamente
│
├── profiles/
│   ├── base/               # Perfiles genéricos iniciales
│   └── custom/             # Perfiles evolucionados
│
├── projects/               # Workspaces de proyectos que SODA genere
├── data/                   # ChromaDBs, SQLite, heurísticas globales
├── tests/                  # Tests del propio SODA
└── scripts/                # Utilidades de setup y mantenimiento
```

**IMPORTANTE:** No crear toda esta estructura de una vez. Crear carpetas según se necesiten en cada fase.

---

## 9. Roadmap por Fases

Cada fase tiene un entregable verificable. No avanzar a la siguiente hasta que la anterior funcione.

### Fase A: Fundamentos (Prioridad 1)

**Objetivo:** Los 3 drivers (Claude, Gemini, Ollama) responden correctamente.

**Tareas:**
1. Verificar estado actual de la carpeta
2. Instalar `uv` si no está
3. Configurar proyecto con `uv init`
4. Crear `.env` con API keys (el usuario provee los valores)
5. Crear `.gitignore` completo
6. Instalar dependencias de Fase A
7. Crear script de test que verifica los 3 drivers en paralelo
8. Ejecutar y validar que los 3 responden

**Entregable:** Un `test_drivers.py` que al ejecutarse muestra los 3 modelos respondiendo.

### Fase B: Kernel Core Secuencial

**Objetivo:** Ciclo completo requirements → architecture → code → validate, secuencial, sin UI.

**Tareas:**
1. Estructura de carpetas del kernel
2. Drivers como clases reutilizables (`kernel/drivers/`)
3. ContextBuilder básico (sin RAG aún)
4. Orchestrator mínimo con máquina de estados
5. DockerSandbox funcional
6. GoalIntegrityValidator (barreras anti-huérfanos)
7. Primer proyecto test: CRUD simple

**Entregable:** CLI que construye un CRUD básico desde descripción.

### Fase C: UI Básica

**Objetivo:** Interfaz visual funcional.

**Tareas:**
1. FastAPI server + WebSocket
2. Monaco Editor integrado
3. pywebview wrapper
4. ChromaDB para Project RAG
5. Panel de progreso tiempo real
6. Árbol de objetivos (vista)

**Entregable:** SODA como app de escritorio.

### Fase D: Skills y Perfiles

**Objetivo:** Asignación automática de capacidades.

### Fase E: Inteligencia Avanzada

**Objetivo:** Wisdom Agent, Goal Interpreter, Context Health Monitor.

### Fase F: Branching y Evolución

**Objetivo:** Variantes con contraste pragmático + aprendizaje acumulativo.

### Fase G: Comunicación Externa

**Objetivo:** Telegram bot.

### Fase H: Pulido

**Objetivo:** Producto maduro, calibrado con uso real.

---

## 10. Protocolo de Trabajo para Claude Code

### 10.1 Al inicio de cada sesión

1. **Inspeccionar estado:** ejecutar `ls` (o `dir` en PowerShell), leer archivos clave existentes
2. **Confirmar fase actual:** basándose en lo que existe, inferir en qué fase del roadmap está el proyecto
3. **Reportar al usuario:** "Veo que el proyecto está en [estado X]. El próximo paso según el plan sería [Y]. ¿Procedemos?"
4. **Esperar confirmación** antes de actuar

### 10.2 Al proponer código

1. Mostrar el código completo que se va a crear/modificar
2. Explicar qué hace y por qué
3. Indicar qué dependencias requiere (si hay que instalar algo)
4. Esperar aprobación del usuario
5. Solo entonces ejecutar

### 10.3 Al enfrentar ambigüedad

Nunca asumir. Preguntar con opciones concretas:
```
Detecté esta ambigüedad: [descripción]

Opciones:
1. [opción A con consecuencia]
2. [opción B con consecuencia]
3. [opción C]

¿Cuál preferís?
```

### 10.4 Al ejecutar comandos

- Para comandos de lectura (ls, cat, etc.): ejecutar directamente
- Para comandos de modificación: pedir confirmación
- Para comandos destructivos (rm, etc.): confirmación explícita y backup si aplica

### 10.5 Control de versiones

- Hacer `git init` al inicio si no existe
- Commit después de cada tarea completada, no al final del día
- Mensajes de commit descriptivos: "feat: Agrega ClaudeDriver con test básico"
- Antes de cambios grandes, verificar que todo está commiteado

### 10.6 Comunicación con el usuario

**Evitar:**
- Instalar dependencias sin avisar
- Crear archivos sin mostrar su contenido
- Ejecutar comandos largos sin explicar qué hacen
- Avanzar varias tareas sin checkpoint
- Usar jerga técnica innecesaria
- Cambiar el plan sin avisar

**Hacer:**
- Explicar antes de actuar
- Un objetivo claro por ciclo
- Confirmar antes de comandos que modifican
- Reportar resultados con claridad
- Señalar si algo no salió como esperaba
- Mantener visibilidad del progreso

### 10.7 Cuando algo sale mal

1. Detener inmediatamente
2. Reportar el error al usuario con el output completo
3. Proponer diagnóstico con al menos 2 hipótesis
4. NO intentar "arreglar" cosas sin entender la causa
5. Si el error requiere decisión del usuario, esperar

---

## 11. Convenciones de Código

### Python

- Python 3.11+
- Type hints obligatorios en funciones públicas
- Docstrings en formato Google o NumPy
- Async por default para operaciones I/O
- `pathlib.Path` en vez de strings para rutas
- `pydantic` para modelos de datos
- Tests con `pytest`
- Linting con `ruff`

### Archivos generados por el sistema

Todo archivo de código generado por SODA debe tener metadata:

```python
# --- METADATA SODA (no editar manualmente) ---
# goal_id: [id único del objetivo]
# goal_path: [path jerárquico legible]
# contract_version: [versión del contrato]
# generated: [timestamp ISO]
# goal_hash: [hash para detectar desincronización]
# --- FIN METADATA ---
```

### Commits

Seguir Conventional Commits:
- `feat:` nueva funcionalidad
- `fix:` corrección de bug
- `refactor:` cambios sin alterar comportamiento
- `docs:` documentación
- `test:` agregar o modificar tests
- `chore:` tareas de mantenimiento

---

## 12. Contexto de Decisiones Tomadas

Estas decisiones ya se discutieron con el usuario y son definitivas. No proponer cambios a menos que el usuario lo pida explícitamente.

1. Windows 11 nativo (no WSL2)
2. `uv` como gestor de Python (no pip, no conda)
3. Cursor + Claude Code como herramientas de desarrollo
4. Modelos locales para volumen, APIs para juicio
5. Monaco Editor + pywebview + FastAPI para UI
6. Telegram antes que WhatsApp para comunicación externa
7. Skills y perfiles asignados automáticamente por la IA (no por el usuario)
8. Perfiles arrancan genéricos y se especializan con uso
9. Branching pragmático (ejecución real de variantes) para cambios grandes
10. Barreras anti-huérfanos estructurales, no remediales
11. ContextHealthMonitor basado en señales objetivas de fatiga
12. Project Chat como pestaña, no ventana flotante
13. Preguntas proactivas del Wisdom Agent son sugeridas, no bloqueantes
14. Referencias bajo demanda cuando el usuario las menciona, no biblioteca permanente

---

## 13. Contexto de Conversación Previa

El usuario y el Claude asistente (de la conversación web, no Claude Code) ya tuvieron una conversación extensa donde se diseñó SODA. Este documento es la consolidación de ese diseño.

**El usuario ya sabe:**
- La arquitectura general
- Los trade-offs discutidos
- Qué componentes son críticos vs avanzados
- Que hay un roadmap por fases

**El usuario probablemente necesita:**
- Ayuda implementando paso a paso
- Evitar desviaciones del plan (scope creep)
- Validar enfoques antes de código largo
- Debugging cuando algo falla
- Decisiones en ambigüedades

**El usuario NO necesita:**
- Re-explicaciones de conceptos ya acordados
- Propuestas de cambio arquitectónico no solicitadas
- Sobrecargar de información técnica
- Que se hagan cosas sin consultar

---

## 14. Glosario de Términos del Proyecto

**Agente:** instancia de un modelo de IA con rol y contexto específico.

**Branching pragmático:** crear ramas del proyecto para comparar variantes en ejecución, no solo en código.

**Checkpoint:** momento de validación obligatoria del usuario.

**ContextBuilder:** componente central que arma contextos mínimos.

**Goal ID:** identificador único de un objetivo en el árbol.

**Goal Integrity:** propiedad de que todo código tiene objetivo y viceversa.

**Huérfano:** código sin objetivo vinculado (prohibido estructuralmente).

**Kernel:** el cerebro determinístico en Python.

**Perfil:** agrupación de skills + experiencia acumulada que actúa como "especialista".

**Profile Evolution:** mecanismo de aprendizaje acumulativo de perfiles.

**Skill:** unidad atómica de capacidad (conocimiento + ejemplos + checklist).

**Wisdom Agent:** componente de preguntas proactivas basadas en experiencia.

---

## 15. Referencias Externas

Documentación que puede ser útil consultar:

- Anthropic API: https://docs.anthropic.com/
- Google AI (Gemini): https://ai.google.dev/docs
- Ollama: https://github.com/ollama/ollama
- uv: https://github.com/astral-sh/uv
- FastAPI: https://fastapi.tiangolo.com/
- ChromaDB: https://docs.trychroma.com/
- Monaco Editor: https://microsoft.github.io/monaco-editor/
- pywebview: https://pywebview.flowrl.com/
- Docker SDK Python: https://docker-py.readthedocs.io/

---

## 16. Acción Inmediata Sugerida

Cuando termines de leer este documento, tu primera respuesta al usuario debería ser:

1. Confirmar que leíste el documento
2. Reportar la estructura actual de la carpeta (ejecutar inspección)
3. Identificar en qué fase del roadmap parece estar el proyecto
4. Proponer el próximo paso específico más pequeño posible
5. Esperar aprobación antes de ejecutar

Ejemplo de respuesta inicial esperada:

```
Leí el documento de SODA. Revisé la carpeta y encontré:
- [lista de archivos/carpetas existentes]

Por el estado actual, parecería que estamos en [Fase X], 
específicamente en [tarea Y].

Sugiero como próximo paso: [acción concreta mínima]

Esto implicaría [qué se va a hacer], y me llevaría [X minutos 
o N acciones].

¿Procedemos con esto o preferís empezar por otro lado?
```

**No avanzar sin este check-in inicial.**
