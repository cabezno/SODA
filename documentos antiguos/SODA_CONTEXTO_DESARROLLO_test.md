# SODA: Contexto Completo de Desarrollo

Guía completa para el desarrollo eficiente de SODA, desde el estado actual hasta el sistema completo, con todos los puntos de conexión explicitados.

---

## TABLA DE CONTENIDOS

1. [Estado Inicial Verificado](#1-estado-inicial-verificado)
2. [Visión del Sistema Completo](#2-visión-del-sistema-completo)
3. [Mapa de Dependencias entre Componentes](#3-mapa-de-dependencias-entre-componentes)
4. [Contratos e Interfaces Críticas](#4-contratos-e-interfaces-críticas)
5. [Flujos de Datos del Sistema](#5-flujos-de-datos-del-sistema)
6. [Secuencia de Desarrollo Paso a Paso](#6-secuencia-de-desarrollo-paso-a-paso)
7. [Puntos de Conexión entre Módulos](#7-puntos-de-conexión-entre-módulos)
8. [Estrategia de Testing por Fase](#8-estrategia-de-testing-por-fase)
9. [Integración con Claude Code](#9-integración-con-claude-code)
10. [Checkpoints de Validación](#10-checkpoints-de-validación)

---

## 1. ESTADO INICIAL VERIFICADO

### 1.1 Entorno del usuario confirmado

**Sistema:**
- Windows 11 nativo
- Python 3.11.9 instalado
- Node.js v24.15.0 instalado

**Infraestructura:**
- Docker Desktop corriendo (con contenedores del usuario, SODA usa puertos altos para no interferir)
- Ollama funcionando con qwen2.5-coder:7b descargado

**Credenciales:**
- API key de Anthropic (disponible)
- API key de Gemini (disponible)

**Herramientas:**
- Cursor instalado como editor
- Claude Code instalado globalmente vía npm

### 1.2 Acciones previas a desarrollo

Antes de empezar cualquier desarrollo, verificar:

1. Que `docker` responda en PowerShell (puede requerir agregar PATH)
2. Que `ollama list` muestre al menos qwen2.5-coder:7b
3. Que las API keys sean válidas (test básico)

### 1.3 Configuración base del entorno de desarrollo

**Variables de entorno globales (Windows, sesión de usuario):**

```
OLLAMA_NUM_PARALLEL=3
```

**Comando para setear:**
```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL", "3", "User")
```

---

## 2. VISIÓN DEL SISTEMA COMPLETO

### 2.1 Stack definitivo

**Runtime y gestión:**
- Python 3.11+ con uv
- Async/await con asyncio en todo el sistema

**Core del Kernel:**
- FastAPI como servidor principal
- WebSockets para comunicación en tiempo real con UI
- Pydantic v2 para modelos de datos

**Persistencia:**
- ChromaDB para memoria vectorial
- SQLite para metadata estructurada
- YAML para configuración de skills/perfiles
- JSON para árboles de objetivos
- Git para código generado

**Modelos de IA:**
- Ollama (local): Qwen 2.5-Coder 7B y 14B
- Anthropic API: Claude Sonnet 4.5 (modelo ID: `claude-sonnet-4-5-20250929`), Claude Haiku 4.5
- Google AI API: Gemini 2.5 Pro, Gemini 2.5 Flash

**Ejecución:**
- Docker SDK para contenedores
- Playwright para web scraping y capturas
- httpx para requests HTTP

**Interface:**
- pywebview como wrapper nativo
- Monaco Editor embebido
- Vanilla HTML/CSS/JS en frontend (sin framework pesado)

**Comunicación externa:**
- python-telegram-bot para canal Telegram
- Perplexity API para investigación web

### 2.2 Arquitectura por capas

```
┌─────────────────────────────────────────────────────────────┐
│ CAPA DE INTERFAZ                                            │
│                                                             │
│ Usuario → UI Principal (pywebview)                          │
│        → Monaco Editor                                      │
│        → Árbol de objetivos interactivo                     │
│        → Panel de progreso en tiempo real                   │
│        → Project Chat                                       │
│        → Dashboard de consumo                               │
│                                                             │
│ Usuario remoto → Telegram Bot                               │
│                                                             │
│ API externa (futuro) → REST endpoints                       │
└─────────────────────────────────────────────────────────────┘
                          ↕ WebSocket
┌─────────────────────────────────────────────────────────────┐
│ CAPA DE KERNEL (FastAPI + asyncio)                          │
│                                                             │
│ ORQUESTACIÓN                                                │
│ ├── Orchestrator (máquina de estados del proyecto)          │
│ ├── IntensityOrchestrator (nivel 1-4 por tarea)             │
│ ├── DependencyGraph (DAG de módulos)                        │
│ ├── ProjectRunner (ejecución de proyectos)                  │
│ ├── DockerSandbox (tests unitarios aislados)                │
│ ├── Watchdog (monitor de archivos)                          │
│ └── GitManager (control de versiones)                       │
│                                                             │
│ INTELIGENCIA                                                │
│ ├── ContextBuilder (único armador de contextos)             │
│ ├── KnowledgeOrchestrator (4 capas de conocimiento)         │
│ ├── WisdomAgent (preguntas proactivas)                      │
│ ├── GoalInterpreter (traduce pedidos a cambios de árbol)    │
│ ├── ImpactAnalyzer (branching pragmático)                   │
│ └── ReferenceAnalyzer (análisis de programas referenciados) │
│                                                             │
│ INTEGRIDAD                                                  │
│ ├── GoalIntegrityValidator (anti-huérfanos)                 │
│ ├── ContextHealthMonitor (señales de fatiga)                │
│ └── ProjectLineage (historial de refundaciones)             │
│                                                             │
│ CAPACIDADES                                                 │
│ ├── SkillManager (catálogo de skills)                       │
│ ├── SkillMatcher (asignación automática)                    │
│ ├── ProfileManager (catálogo de perfiles)                   │
│ ├── ProfileMatcher (asignación automática)                  │
│ └── ProfileEvolution (aprendizaje acumulativo)              │
│                                                             │
│ HERRAMIENTAS EXTERNAS                                       │
│ ├── WebResearcher (Perplexity + sintesis)                   │
│ ├── SystemActionsExecutor (acciones en PC con catálogo)     │
│ ├── VisionCapturer (screenshots y captura visual)           │
│ └── VisualInspector (análisis con IA)                       │
│                                                             │
│ COMUNICACIÓN                                                │
│ ├── MessagingGateway (abstracción de canales)               │
│ ├── ProjectChat (consultas al proyecto)                     │
│ └── Channels/ (telegram, futuro whatsapp)                   │
│                                                             │
│ MONITOREO                                                   │
│ ├── UsageMonitor (tracking de uso por modelo)               │
│ ├── CostTracker (tracking de costos pagos)                  │
│ └── AlertManager (alertas preventivas)                      │
│                                                             │
│ DRIVERS                                                     │
│ ├── ClaudeDriver                                            │
│ ├── GeminiDriver                                            │
│ └── OllamaDriver                                            │
└─────────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────────┐
│ CAPA DE MODELOS DE IA                                       │
│                                                             │
│ Locales (Ollama): Qwen 14B, Qwen 7B, DeepSeek (opcional)    │
│ Cloud Anthropic: Claude Sonnet 4.5, Claude Haiku 4.5        │
│ Cloud Google: Gemini 2.5 Pro, Gemini 2.5 Flash              │
└─────────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────────┐
│ CAPA DE PERSISTENCIA                                        │
│                                                             │
│ ChromaDB: memoria semántica (proyecto, perfiles, skills)    │
│ SQLite: metadata, heurísticas, usage analytics              │
│ JSON/YAML: configuración y árboles                          │
│ Git + Filesystem: código de proyectos generados             │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Principios arquitectónicos vigentes

Respetar durante todo el desarrollo:

- **P1:** Coordinación por código Python, juicio por IA
- **P2:** Contextos mínimos en cada llamada
- **P3:** Trazabilidad obligatoria código↔objetivos
- **P4:** Escalado gradual de modelos por costo
- **P5:** Usuario en control en checkpoints
- **P6:** Asignación automática de capacidades
- **P7:** Integridad estructural, no remedial
- **P8:** Priorizar modelos gratuitos
- **P9:** Máxima calidad en puntos críticos
- **P10:** Prevención sobre reacción

---

## 3. MAPA DE DEPENDENCIAS ENTRE COMPONENTES

Este mapa es crítico para saber en qué orden construir y qué puede hacerse en paralelo.

### 3.1 Grafo de dependencias de desarrollo

```
FUNDACIONES (no dependen de otros componentes SODA)
├── Drivers (Claude, Gemini, Ollama)
├── Configuración base (.env, pyproject.toml)
└── UsageMonitor + CostTracker

PRIMERA CAPA (depende solo de fundaciones)
├── ContextBuilder → depende de: Drivers
├── DockerSandbox → depende de: Docker SDK
├── Watchdog → depende de: filesystem
├── GitManager → depende de: git
└── KnowledgeOrchestrator base → depende de: ChromaDB

SEGUNDA CAPA (depende de primera)
├── GoalIntegrityValidator → depende de: filesystem + metadata
├── SkillManager → depende de: filesystem + YAML
├── ProfileManager → depende de: filesystem + YAML
└── Orchestrator base → depende de: ContextBuilder, Drivers

TERCERA CAPA
├── SkillMatcher → depende de: SkillManager, Drivers
├── ProfileMatcher → depende de: ProfileManager, Drivers
├── DependencyGraph → depende de: contratos definidos
├── ProjectRunner → depende de: DockerSandbox, Stack profiles
├── GoalInterpreter → depende de: ContextBuilder, Claude Driver
└── WebResearcher → depende de: Drivers

CUARTA CAPA (nivel de características avanzadas)
├── WisdomAgent → depende de: KnowledgeOrchestrator, Drivers
├── ImpactAnalyzer → depende de: ProjectRunner, DependencyGraph
├── ReferenceAnalyzer → depende de: WebResearcher, Drivers
├── VisionCapturer → depende de: Playwright
├── VisualInspector → depende de: VisionCapturer, Drivers con visión
└── ProfileEvolution → depende de: ProfileManager, KnowledgeOrchestrator

QUINTA CAPA (requiere todo lo anterior)
├── IntensityOrchestrator → depende de: Orchestrator, todos los evaluadores
├── ContextHealthMonitor → depende de: UsageMonitor, logs históricos
├── ProjectLineage → depende de: GitManager, ProjectManager
└── SystemActionsExecutor → depende de: validación de paths

CAPA DE INTERFAZ
├── FastAPI server → depende de: Orchestrator
├── WebSocket handler → depende de: FastAPI, estado en vivo
├── UI Frontend → depende de: WebSocket server funcionando
└── pywebview wrapper → depende de: FastAPI corriendo

CAPA DE COMUNICACIÓN
├── MessagingGateway → depende de: Orchestrator
├── Telegram Channel → depende de: MessagingGateway
└── ProjectChat → depende de: KnowledgeOrchestrator
```

### 3.2 Implicancias del grafo

**Lo que se puede paralelizar en desarrollo:**

En la primera capa, los drivers pueden construirse independientemente entre sí. Uno puede estar haciendo el ClaudeDriver mientras otro hace el OllamaDriver.

DockerSandbox, Watchdog y GitManager son independientes entre sí, cualquier orden.

**Lo que tiene dependencias fuertes:**

ContextBuilder es central y muchos otros dependen de él. Construirlo temprano y bien.

Orchestrator es el corazón del sistema. Construirlo simple primero y enriquecerlo por fases.

La UI solo puede probarse end-to-end cuando el Kernel responde correctamente.

---

## 4. CONTRATOS E INTERFACES CRÍTICAS

Estas son las interfaces entre componentes que deben definirse claramente antes de que los componentes interactúen. Son los "contratos" del sistema.

### 4.1 Interfaz Driver → Resto del sistema

Todos los drivers deben cumplir una interfaz común para que el ContextBuilder y el Orchestrator no necesiten saber qué modelo están usando.

```python
class BaseDriver:
    async def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float = 0.7,
        response_format: str = "text",  # o "json"
        images: list[Image] | None = None,  # para visión
        metadata: dict | None = None
    ) -> DriverResponse:
        """Interfaz unificada de llamada."""

class DriverResponse:
    content: str
    tokens_input: int
    tokens_output: int
    latency_ms: int
    model_used: str
    cost_usd: float  # 0 para locales
    metadata: dict
```

**Punto de conexión crítico:** esta interfaz es consumida por ContextBuilder. Si cambia, todos los consumidores deben actualizarse. Por eso definirla bien desde el principio.

### 4.2 Interfaz Context → Driver

ContextBuilder produce contextos que los drivers consumen:

```python
class BuiltContext:
    system_prompt: str  # listo para enviar
    user_message: str   # listo para enviar
    estimated_tokens: int
    active_skills: list[str]  # para logging
    active_profile: str | None  # para logging
    knowledge_sources: list[str]  # qué se consultó
    cache_key: str | None  # para prompt caching

class ContextBuilder:
    async def build(
        self,
        role: str,  # "generator", "reviewer", etc
        task: Task,
        project: Project,
        force_model: str | None = None  # override opcional
    ) -> tuple[BuiltContext, BaseDriver]:
        """Retorna contexto listo + driver a usar."""
```

**Punto de conexión crítico:** ContextBuilder decide qué driver usar según rol, task, y capacidad requerida. Esta decisión encapsula mucha lógica de P8 y P9.

### 4.3 Interfaz Orchestrator → Componentes

El Orchestrator dispara tareas a componentes. Usa un patrón de "task dispatch":

```python
class Task:
    id: str  # UUID
    type: TaskType  # Enum
    role: str
    project_id: str
    inputs: dict
    metadata: dict
    parent_task_id: str | None  # para sub-tareas
    
class TaskResult:
    task_id: str
    status: Literal["success", "failure", "partial"]
    outputs: dict
    errors: list[str]
    logs: list[LogEntry]
    children_tasks: list[Task]  # si generó sub-tareas
```

**Punto de conexión crítico:** el patrón Task/TaskResult es uniforme en todo el sistema. Cualquier trabajo que se pueda hacer es una Task.

### 4.4 Interfaz Goal Tree → Código

La trazabilidad bidireccional requiere interfaz clara:

```python
class GoalNode:
    id: str  # único
    parent_id: str | None
    type: Literal["category", "objective", "decision"]
    description: str
    status: Literal["planned", "in_progress", "implemented", "deprecated"]
    implemented_by: list[str]  # paths de archivos
    dependencies: list[str]  # ids de otros nodos
    metadata: dict
    hash: str  # para detectar desincronización

class CodeFile:
    path: str
    goal_id: str  # required, no null
    goal_path: str  # human-readable
    generated_at: datetime
    generated_by: str  # role que lo generó
    goal_hash: str  # hash del goal al momento de generar
    
    def is_synced(self, current_goal: GoalNode) -> bool:
        return self.goal_hash == current_goal.hash
```

**Punto de conexión crítico:** GoalIntegrityValidator usa estas interfaces constantemente. Sin consistencia en metadata, todo el sistema de integridad falla.

### 4.5 Interfaz Skill/Profile → Context

Skills y perfiles se inyectan en contextos. Deben ser declarativos:

```yaml
# Estructura de skill
name: skill_id
version: "1.0"
category: technical | domain | discipline | language
applies_to_roles:
  generator:
    load_level: full  # full | summary | checklist
  reviewer:
    load_level: checklist
  architect:
    load_level: summary

activation_signals:
  keywords: [...]
  file_patterns: [...]
  dependencies: [...]

content:
  system_prompt_addition: "..."
  knowledge_chunks: [...]
  examples: [...]
  checklist: [...]
```

**Punto de conexión crítico:** el SkillManager lee estos archivos y el ContextBuilder los carga dinámicamente. La estructura debe ser estable.

### 4.6 Interfaz UI → Kernel

Comunicación bidireccional vía WebSocket con mensajes tipados:

```typescript
// Del UI al Kernel
type ClientMessage = 
  | { type: "create_project", description: string }
  | { type: "approve_checkpoint", project_id: string, checkpoint_id: string }
  | { type: "modify_goal", project_id: string, goal_id: string, change: string }
  | { type: "query_project", project_id: string, question: string }
  | { type: "execute_action", action: string, params: dict };

// Del Kernel al UI  
type ServerMessage =
  | { type: "progress_update", project_id: string, progress: ProgressInfo }
  | { type: "checkpoint_required", checkpoint: Checkpoint }
  | { type: "log_entry", entry: LogEntry }
  | { type: "notification", notification: Notification }
  | { type: "result", request_id: string, result: any };
```

**Punto de conexión crítico:** el formato debe ser estable y versionado. Cambios rompen clientes.

---

## 5. FLUJOS DE DATOS DEL SISTEMA

### 5.1 Flujo: Usuario describe proyecto

```
Usuario escribe descripción
    ↓
UI → WebSocket → Kernel.Orchestrator
    ↓
Orchestrator crea Project con id único
    ↓
Llama a SkillMatcher (usando Gemini Pro)
    ↓ retorna skills relevantes
    ↓
Llama a ProfileMatcher (usando Gemini Pro)
    ↓ retorna perfiles aplicables
    ↓
Llama a WisdomAgent con la descripción
    ↓ retorna preguntas proactivas (si aplica)
    ↓
Crea Task: "entrevistar_requerimientos"
    ↓
ContextBuilder arma contexto con skills/perfiles/preguntas
    ↓
ClaudeDriver (rol entrevistador) recibe contexto
    ↓ responde con entrevista
    ↓
UI muestra entrevista → Usuario responde
    ↓
Ciclo hasta blueprint completo
    ↓
Orchestrator genera blueprint.json
    ↓
Checkpoint 1: usuario valida blueprint
```

### 5.2 Flujo: Construcción de un módulo

```
Orchestrator determina próximo módulo a construir
    ↓
DependencyGraph verifica que las dependencias estén resueltas
    ↓
IntensityOrchestrator determina nivel (1-4)
    ↓
Crea Task: "generar_módulo_X" con intensidad N
    ↓
    SI intensidad 1: un agente
    SI intensidad 2: N agentes paralelos (para módulos distintos)
    SI intensidad 3: un generador + un revisor
    SI intensidad 4: ensemble con árbitro
    ↓
ContextBuilder arma contexto para el generador:
    - System prompt del rol
    - Skills relevantes al módulo (filtradas por load_level)
    - Perfil activo
    - Contrato del módulo
    - Contratos de módulos vecinos (no código completo)
    - Reglas heurísticas relevantes vía RAG
    ↓
Driver correspondiente genera código
    ↓
Código generado incluye metadata obligatoria (goal_id, etc)
    ↓
GoalIntegrityValidator verifica metadata
    ↓
Código se escribe al filesystem (Watchdog registra)
    ↓
DockerSandbox ejecuta tests unitarios
    ↓
ProjectRunner levanta proyecto (si aplica en esta fase)
    ↓
    SI tests + runtime OK: commit + siguiente tarea
    SI falla: cascada de escalado
    ↓
UsageMonitor registra uso
```

### 5.3 Flujo: Usuario modifica algo

```
Usuario expresa modificación en lenguaje natural
("quiero que tenga X", "sacá Y", "cambiá Z")
    ↓
UI → WebSocket → Kernel
    ↓
GoalInterpreter (usando Claude Sonnet - máxima calidad)
analiza el pedido:
    - ¿Qué nodos del árbol afecta?
    - ¿Qué tipo de cambio es?
    - ¿Hay ambigüedades?
    - ¿Hay referencias a otros productos?
    ↓
    SI hay ambigüedad: preguntar al usuario con opciones
    SI es claro: continuar
    ↓
ImpactAnalyzer evalúa alcance:
    - Módulos afectados
    - Complejidad
    - Esfuerzo estimado
    ↓
    SI es cambio pequeño: aplicar directamente en main
    SI es cambio grande: crear rama (branching pragmático)
        - Copia del proyecto
        - Aplicar cambios en rama
        - Ejecutar ambas versiones
        - Comparar pragmáticamente
        - Usuario elige cuál adoptar
    ↓
GoalIntegrityValidator asegura que no queden huérfanos
    ↓
Actualización del árbol de objetivos
    ↓
Notificación al usuario
```

### 5.4 Flujo: Ejecución y verificación visual

```
ProjectRunner detecta stack del proyecto
    ↓
Prepara ambiente (dependencias, servicios auxiliares)
    ↓
Asigna puertos disponibles (rangos altos para no conflictuar)
    ↓
Levanta en Docker
    ↓
Espera ready indicator
    ↓
Health checks básicos
    ↓
    SI proyecto tiene UI web:
        VisionCapturer toma screenshots de páginas principales
        VisualInspector (Gemini Flash) analiza:
            - ¿Se renderiza correctamente?
            - ¿Hay errores visibles?
            - ¿Los elementos esperados están presentes?
        SI hay problemas: escalar a Gemini Pro o Claude
    ↓
SmokeTester genera y ejecuta tests funcionales:
    - Para cada endpoint detectado: request básico
    - Verificar códigos de respuesta
    - Verificar estructura de responses
    ↓
ProjectRunner reporta estado de salud
    ↓
Proyecto queda corriendo accesible al usuario
```

### 5.5 Flujo: Monitoreo y alertas

```
UsageMonitor registra cada llamada a IA
    ↓
CostTracker calcula costos acumulados
    ↓
AlertManager evalúa umbrales cada N llamadas:
    SI 70% tier gratuito Gemini: alerta preventiva
    SI 90% tier: alerta urgente
    SI 70% budget mensual Claude: alerta preventiva
    SI contexto 70% del límite del modelo: alerta técnica
    ↓
ContextHealthMonitor evalúa patrones:
    SI hay múltiples reintentos: flag de fatiga
    SI respuestas inconsistentes: flag crítico
    SI contexto creciendo sostenido: sugerir refundación
    ↓
Alertas preventivas se muestran en UI
Usuario decide acción
```

---

## 6. SECUENCIA DE DESARROLLO PASO A PASO

Esta sección es el corazón operativo: qué hacer, en qué orden, con qué verificación.

### FASE 0: Preparación (antes de codear)

**Objetivo:** entorno listo para desarrollo sin fricciones.

**Pasos:**

1. Verificar estado del sistema
   ```powershell
   python --version
   node --version
   docker --version
   docker ps
   ollama list
   ```

2. Instalar uv si no está
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

3. Verificar carpeta del proyecto y estado actual
   - Si hay carpeta de SODA existente (por Claude Code): hacer inventario
   - Si no hay: crear estructura base

4. Descargar qwen2.5-coder:14b en background
   ```powershell
   ollama pull qwen2.5-coder:14b
   ```

5. Setear variable de entorno
   ```powershell
   [Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL", "3", "User")
   ```

**Verificación:** todos los comandos responden, no hay errores.

### FASE 1: Fundaciones del Kernel

**Objetivo:** los 3 drivers funcionan y se puede hacer una llamada completa al sistema.

**Orden sugerido:**

1. **Estructura base del proyecto**
   ```
   soda/
   ├── .env (con API keys)
   ├── .gitignore
   ├── pyproject.toml
   ├── README.md
   ├── kernel/
   │   ├── __init__.py
   │   └── drivers/
   │       └── __init__.py
   └── scripts/
   ```

2. **Instalar dependencias mínimas**
   ```
   uv add anthropic google-generativeai ollama python-dotenv pydantic httpx
   ```

3. **Implementar ClaudeDriver**
   - Archivo: `kernel/drivers/claude_driver.py`
   - Clase: `ClaudeDriver(BaseDriver)`
   - Métodos: `call()`, soporte de caching, manejo de errores
   - Test básico que verifique respuesta

4. **Implementar GeminiDriver**
   - Archivo: `kernel/drivers/gemini_driver.py`
   - Soporta: Gemini 2.5 Pro, Gemini 2.5 Flash
   - Tracking de uso de tier gratuito
   - Test básico

5. **Implementar OllamaDriver**
   - Archivo: `kernel/drivers/ollama_driver.py`
   - Soporta múltiples modelos
   - Configuración de paralelismo
   - Test básico

6. **Definir BaseDriver abstract**
   - Archivo: `kernel/drivers/base.py`
   - Interfaz que todos cumplen
   - Retrofit los drivers existentes si es necesario

7. **UsageMonitor inicial**
   - Archivo: `kernel/monitoring/usage_monitor.py`
   - SQLite para persistencia
   - Registra cada llamada de driver

8. **CostTracker inicial**
   - Archivo: `kernel/monitoring/cost_tracker.py`
   - Cálculo de costo por modelo
   - Acumulados diarios/mensuales

9. **Test integrado de los 3 drivers**
   - Script que llama a los 3 en paralelo
   - Verifica respuestas
   - Verifica tracking de uso

**Puntos de conexión críticos:**
- BaseDriver define el contrato que consumen todos
- UsageMonitor se llama desde cada driver (callback)
- CostTracker consume datos de UsageMonitor

**Verificación:** test integrado retorna OK en los 3 drivers, UsageMonitor tiene registros, CostTracker calcula costos.

### FASE 2: ContextBuilder y Orchestrator básicos

**Objetivo:** poder hacer un ciclo completo: descripción → entrevista → blueprint.

**Orden:**

1. **Definir modelos de datos fundamentales (Pydantic)**
   - Archivo: `kernel/models/`
   - Task, TaskResult, Project, BuiltContext, DriverResponse

2. **ContextBuilder mínimo**
   - Archivo: `kernel/context/context_builder.py`
   - Por ahora: arma contexto simple sin RAG ni skills
   - Selección de driver según rol
   - Contar tokens estimados

3. **Cargador de system prompts**
   - Archivo: `kernel/context/prompt_loader.py`
   - Lee prompts desde `prompts/` según rol

4. **Prompts iniciales**
   - Carpeta: `prompts/`
   - `claude/requirements_interviewer.md`
   - Otros según se necesiten

5. **Orchestrator mínimo**
   - Archivo: `kernel/orchestrator.py`
   - Máquina de estados simple
   - Método `start_project(description)` 
   - Dispara fase de entrevista

6. **Test: flujo completo de entrevista**
   - Script que inicia proyecto
   - Responde interactivamente
   - Genera blueprint.json

**Puntos de conexión críticos:**
- Orchestrator consume ContextBuilder
- ContextBuilder consume Drivers y PromptLoader
- Todo pasa por UsageMonitor

**Verificación:** se puede hacer una entrevista completa desde CLI y obtener blueprint.json.

### FASE 3: Persistencia y Estado

**Objetivo:** los proyectos persisten entre sesiones, ChromaDB operativo.

**Orden:**

1. **ChromaDB Manager**
   - Archivo: `kernel/knowledge/chromadb_manager.py`
   - Abstracción sobre ChromaDB
   - Múltiples colecciones (project, skills, profiles)

2. **KnowledgeOrchestrator básico**
   - Archivo: `kernel/knowledge/knowledge_orchestrator.py`
   - Rutea consultas a la colección correcta
   - Solo Project RAG por ahora

3. **Project Manager**
   - Archivo: `kernel/projects/project_manager.py`
   - CRUD de proyectos
   - Carpeta `projects/` con estructura estándar

4. **GitManager**
   - Archivo: `kernel/git_manager.py`
   - `git init` en proyecto nuevo
   - Commits automáticos
   - Opcional: integración con GitHub

5. **Watchdog**
   - Archivo: `kernel/watchdog_mgr.py`
   - Monitor de archivos del proyecto activo
   - Backups atómicos antes de modificaciones

**Puntos de conexión críticos:**
- ProjectManager es llamado por Orchestrator al crear proyecto
- ChromaDB es consumida por KnowledgeOrchestrator
- Watchdog dispara eventos que Orchestrator puede consumir

**Verificación:** un proyecto iniciado puede cerrarse y reabrirse, el estado se mantiene.

### FASE 4: Goal Tree y Trazabilidad

**Objetivo:** árbol de objetivos funcional con anti-huérfanos.

**Orden:**

1. **Modelo de Goal Tree**
   - Archivo: `kernel/goals/goal_tree.py`
   - Estructura JSON serializable
   - Operaciones: add, modify, remove, query

2. **Metadata injector para código generado**
   - Archivo: `kernel/goals/metadata_injector.py`
   - Agrega headers de metadata a archivos generados
   - Patrón consistente

3. **GoalIntegrityValidator**
   - Archivo: `kernel/integrity/goal_integrity_validator.py`
   - Test bidireccional (todo archivo → goal, todo goal → archivo)
   - Pre-commit hook

4. **GitManager con validación**
   - Integrar validator en commits
   - Rechazar commits con huérfanos

**Puntos de conexión críticos:**
- Todo generador de código usa MetadataInjector
- GitManager consulta GoalIntegrityValidator antes de commit
- Orchestrator actualiza GoalTree cuando hay cambios

**Verificación:** no se pueden generar commits con código huérfano, el árbol refleja el estado real.

### FASE 5: Skills y Perfiles Base

**Objetivo:** asignación automática de capacidades funciona.

**Orden:**

1. **SkillManager**
   - Archivo: `kernel/capabilities/skill_manager.py`
   - Carga skills desde `skills/base/` y `skills/custom/`
   - Indexación básica

2. **ProfileManager**
   - Archivo: `kernel/capabilities/profile_manager.py`
   - Similar estructura

3. **Primeras skills base (crear 5-8)**
   - `skills/base/python_fundamentals/`
   - `skills/base/javascript_fundamentals/`
   - `skills/base/api_design/`
   - `skills/base/database_design/`
   - `skills/base/testing_basics/`

4. **Primeros perfiles base (crear 3-5)**
   - `profiles/base/general_developer/`
   - `profiles/base/web_fullstack/`
   - `profiles/base/backend_api/`

5. **SkillMatcher**
   - Archivo: `kernel/capabilities/skill_matcher.py`
   - Usa Gemini Pro para análisis
   - Retorna skills activas con scores

6. **ProfileMatcher**
   - Archivo: `kernel/capabilities/profile_matcher.py`
   - Similar, con Gemini Pro

7. **Integración en ContextBuilder**
   - ContextBuilder ahora carga skills/perfiles activos
   - Aplica filtrado por rol y load_level

**Puntos de conexión críticos:**
- ContextBuilder es el consumidor principal
- Orchestrator dispara matchers al iniciar proyecto
- Skills y perfiles son inputs del contexto

**Verificación:** al iniciar un proyecto, se asignan skills y perfiles automáticamente, el usuario ve qué equipo se asignó.

### FASE 6: Construcción de Proyectos Básica

**Objetivo:** desde blueprint se construye un CRUD simple end-to-end.

**Orden:**

1. **DockerSandbox**
   - Archivo: `kernel/execution/docker_sandbox.py`
   - Ejecuta tests en contenedores aislados
   - Captura stdout/stderr

2. **DependencyGraph**
   - Archivo: `kernel/orchestration/dependency_graph.py`
   - Construye DAG desde contratos
   - Calcula orden de ejecución

3. **Code Generator (Qwen)**
   - No es un componente separado, es un Task type
   - Usa Qwen 14B via OllamaDriver
   - Genera con metadata obligatoria

4. **Code Reviewer (Gemini Flash)**
   - Task type
   - Revisa código generado
   - Feedback estructurado

5. **Cascada de escalado**
   - Implementar en Orchestrator
   - Reintentos con modelos crecientes
   - Max 6 niveles antes de checkpoint humano

6. **Orchestrator enriquecido**
   - Flujo completo: blueprint → arquitectura → módulos → integración
   - Checkpoints en fases correctas

7. **Test: construcción de CRUD simple**
   - "Una app simple de tareas con FastAPI"
   - Debería generar todo el código funcional

**Puntos de conexión críticos:**
- Orchestrator coordina todo el flujo
- DockerSandbox valida cada módulo
- ContextBuilder sirve contextos para cada generación
- GoalIntegrityValidator verifica antes de commit

**Verificación:** el CRUD simple se genera, los tests pasan, el código es coherente.

### FASE 7: ProjectRunner y Verificación Real

**Objetivo:** los proyectos no solo se generan, sino que se ejecutan y verifican.

**Orden:**

1. **StackDetector**
   - Archivo: `kernel/execution/stack_detector.py`
   - Analiza archivos para determinar stack
   - Catalog en `profiles.yaml`

2. **PortManager**
   - Archivo: `kernel/execution/port_manager.py`
   - Asignación dinámica
   - Registro de puertos activos

3. **ServiceOrchestrator**
   - Archivo: `kernel/execution/service_orchestrator.py`
   - Genera docker-compose si hay múltiples servicios
   - Gestiona levantamiento coordinado

4. **ProjectRunner**
   - Archivo: `kernel/execution/project_runner.py`
   - Usa todos los anteriores
   - Ciclo completo: detect → prepare → run → verify → monitor

5. **LogMonitor**
   - Archivo: `kernel/execution/log_monitor.py`
   - Captura streaming de logs
   - Clasificación por severidad

6. **SmokeTester**
   - Archivo: `kernel/execution/smoke_tester.py`
   - Genera tests funcionales basándose en endpoints
   - Ejecuta y reporta

7. **Integración en Orchestrator**
   - Verificación continua durante construcción
   - No solo al final

**Puntos de conexión críticos:**
- ProjectRunner consume DockerSandbox para su infraestructura
- Orchestrator dispara ProjectRunner después de cada módulo integrado
- Alertas de LogMonitor pueden escalar tareas

**Verificación:** un proyecto construido se levanta automáticamente, las páginas responden, los smoke tests pasan.

### FASE 8: UI Básica

**Objetivo:** interfaz visual funcional para interactuar con SODA.

**Orden:**

1. **FastAPI server**
   - Archivo: `ui/server.py`
   - Endpoints REST básicos
   - Mount del directorio static

2. **WebSocket handler**
   - Archivo: `ui/websocket_handler.py`
   - Comunicación bidireccional
   - Broadcast de progreso

3. **Frontend HTML base**
   - Archivo: `ui/static/index.html`
   - Layout con paneles
   - Carga de Monaco desde CDN

4. **Frontend JS core**
   - Archivo: `ui/static/js/app.js`
   - WebSocket client
   - Event handlers

5. **pywebview launcher**
   - Archivo: `ui/launcher.py`
   - Arranca FastAPI + abre ventana

6. **Panel de progreso en vivo**
   - Módulos en curso
   - Estado de ejecución
   - Logs streaming

7. **Dashboard de consumo**
   - UsageMonitor + CostTracker visualizados
   - Alertas en UI

**Puntos de conexión críticos:**
- WebSocket es el bus de comunicación UI↔Kernel
- Todos los eventos del Orchestrator se emiten al WebSocket
- Frontend es reactivo al estado

**Verificación:** se puede iniciar SODA con un doble click, crear un proyecto, ver progreso, ver costos.

### FASE 9: Inteligencia Avanzada

**Objetivo:** WisdomAgent, GoalInterpreter, ContextHealthMonitor operativos.

**Orden:**

1. **GoalInterpreter**
   - Archivo: `kernel/intelligence/goal_interpreter.py`
   - Usa Claude Sonnet (máxima calidad)
   - Traduce pedidos a modificaciones estructuradas

2. **ImpactAnalyzer**
   - Archivo: `kernel/intelligence/impact_analyzer.py`
   - Analiza alcance de cambios
   - Sugiere branching cuando corresponde

3. **Branching básico**
   - Integración con GitManager
   - Crear ramas, ejecutar en paralelo
   - Comparación pragmática

4. **WisdomAgent**
   - Archivo: `kernel/intelligence/wisdom_agent.py`
   - Usa Gemini Pro
   - Preguntas proactivas en momentos clave

5. **ContextHealthMonitor**
   - Archivo: `kernel/integrity/context_health_monitor.py`
   - Señales objetivas de fatiga
   - Alertas escalonadas

**Puntos de conexión críticos:**
- GoalInterpreter es invocado por Orchestrator en modificaciones
- ImpactAnalyzer usa ProjectRunner para comparaciones
- WisdomAgent es consultado por Orchestrator en checkpoints
- ContextHealthMonitor escucha UsageMonitor y logs

**Verificación:** se pueden hacer modificaciones complejas, el sistema detecta ambigüedades, sugiere mejoras proactivamente.

### FASE 10: Capacidad Visual

**Objetivo:** las IAs pueden "ver" el proyecto ejecutándose.

**Orden:**

1. **Instalar Playwright**
   ```
   uv add playwright
   playwright install chromium
   ```

2. **VisionCapturer**
   - Archivo: `kernel/vision/vision_capturer.py`
   - Screenshots de páginas web
   - Captura de múltiples viewports
   - Almacenamiento temporal

3. **Modificar drivers para soporte de visión**
   - ClaudeDriver con imágenes
   - GeminiDriver con imágenes
   - Tracking de costo adicional

4. **VisualInspector**
   - Archivo: `kernel/vision/visual_inspector.py`
   - Usa Gemini Flash por defecto
   - Escalado a Pro/Claude si necesario
   - Reportes estructurados

5. **Integración en ProjectRunner**
   - Después de levantar proyecto con UI
   - Inspección automática
   - Feedback a generadores si hay problemas

**Puntos de conexión críticos:**
- VisionCapturer consume ProjectRunner (necesita URL corriendo)
- VisualInspector consume Drivers con visión
- Reportes van al Orchestrator que puede escalar issues

**Verificación:** cuando se construye una app web, SODA captura screenshots, detecta errores visibles, feedback a generadores.

### FASE 11: Comunicación Externa

**Objetivo:** Telegram integrado para uso remoto.

**Orden:**

1. **MessagingGateway abstracto**
   - Archivo: `kernel/communication/messaging_gateway.py`
   - Interfaz unificada para canales

2. **TelegramChannel**
   - Archivo: `kernel/communication/channels/telegram_channel.py`
   - Bot con python-telegram-bot
   - Autenticación de usuario
   - Mensajes tipados

3. **ProjectChat**
   - Archivo: `kernel/communication/project_chat.py`
   - Consultas en lenguaje natural
   - Usa KnowledgeOrchestrator del proyecto

4. **SystemActionsExecutor**
   - Archivo: `kernel/external/system_actions.py`
   - Catálogo cerrado
   - Validación de paths
   - Accesible desde Telegram

**Puntos de conexión críticos:**
- MessagingGateway es consumido por Orchestrator para enviar alertas
- TelegramChannel envía/recibe via MessagingGateway
- SystemActionsExecutor es invocado desde Telegram y UI

**Verificación:** se puede chatear con SODA por Telegram, aprobar checkpoints desde el celular, abrir proyectos.

### FASE 12: Perfiles Avanzados

**Objetivo:** los perfiles acumulan experiencia real.

**Orden:**

1. **ProfileEvolution**
   - Archivo: `kernel/capabilities/profile_evolution.py`
   - Captura aprendizajes post-proyecto
   - Consolidación de patrones

2. **WebResearcher**
   - Archivo: `kernel/external/web_researcher.py`
   - Perplexity API
   - Investigación bajo demanda

3. **ReferenceAnalyzer**
   - Archivo: `kernel/intelligence/reference_analyzer.py`
   - Detecta menciones a programas
   - Análisis bajo demanda

4. **Primeros perfiles especializados autogenerados**
   - Después de N proyectos similares, el sistema propone crear perfil especializado
   - Usuario aprueba

**Puntos de conexión críticos:**
- ProfileEvolution se dispara al completar proyectos
- WebResearcher es consumido por múltiples componentes
- ReferenceAnalyzer es invocado por GoalInterpreter

**Verificación:** después de 3+ proyectos similares, SODA propone crear un perfil especializado con el conocimiento acumulado.

### FASE 13: IntensityOrchestrator y Refinamiento

**Objetivo:** sistema maduro con paralelismo inteligente.

**Orden:**

1. **IntensityOrchestrator completo**
   - Archivo: `kernel/orchestration/intensity_orchestrator.py`
   - Clasificación automática de tareas
   - Ejecución en niveles 1-4

2. **Soporte para múltiples lenguajes**
   - Skills para Go, Rust, Java, PHP, etc.
   - Ajuste de modelos según lenguaje

3. **Capability Packs iniciales**
   - Auth completo
   - Payment processing (Stripe, MercadoPago)
   - Email notifications

4. **External Tool Registry**
   - Catálogo de APIs externas
   - Google Calendar, GitHub, etc.

5. **Refinamiento general**
   - Mejora de prompts con datos reales de uso
   - Calibración de umbrales
   - Testing exhaustivo

**Puntos de conexión críticos:**
- IntensityOrchestrator es invocado por Orchestrator en cada task
- Capability Packs son skills especializadas
- External Tools pueden usarse en SODA o integrarse en proyectos

**Verificación:** sistema maduro que puede construir apps complejas en múltiples lenguajes con alta calidad.

### FASE 14: SODA Multi-propósito

**Objetivo:** SODA sirve para más que desarrollo.

**Orden:**

1. **Generalización de ProjectType**
   - Archivo: `kernel/projects/project_types.py`
   - Software, analysis, marketing, finance, etc.

2. **Output generators**
   - PDF reports
   - Presentaciones
   - Modelos financieros en Excel

3. **Ciclos de vida específicos por tipo**
   - Cada project_type con sus checkpoints propios

4. **Skills de disciplinas no técnicas**
   - Marketing, finanzas, análisis, legal, UX

**Puntos de conexión críticos:**
- Orchestrator despacha según project_type
- Skills de disciplinas se activan según tipo
- Output generators son nuevos tipos de "generadores"

**Verificación:** SODA puede producir planes de marketing, modelos financieros, análisis, no solo código.

---

## 7. PUNTOS DE CONEXIÓN ENTRE MÓDULOS

Resumen de las interacciones críticas que deben respetarse:

### Conexión 1: Drivers ↔ Todo el sistema

Los drivers son la única forma de llamar a IAs. Todo pasa por ellos.

**Patrón de uso:**
```python
driver = ContextBuilder.select_driver(role, task)
context = ContextBuilder.build(role, task, project)
response = await driver.call(context.system, context.user)
UsageMonitor.record(driver.model, response.tokens_in, response.tokens_out)
```

**Invariante:** ningún componente llama directamente a APIs de IA. Siempre vía driver.

### Conexión 2: ContextBuilder es el único armador

Centralizar la construcción de contextos permite optimización global.

**Patrón:**
```python
# MAL
context = f"{system_prompt}\n\n{task_description}\n\n{extra_info}"

# BIEN
context = context_builder.build(role=role, task=task, project=project)
```

**Invariante:** nadie arma contextos "a mano". Todo pasa por ContextBuilder.

### Conexión 3: Orchestrator como coordinador central

El Orchestrator es quien despacha tareas. Los componentes no se llaman entre sí directamente.

**Patrón:**
```python
# MAL
reviewer.review(code_from_generator)

# BIEN
review_task = Task(type="review", inputs={"code": code})
result = await orchestrator.execute_task(review_task)
```

**Invariante:** comunicación horizontal entre componentes va vía Orchestrator.

### Conexión 4: GoalIntegrityValidator en cada commit

Antes de cualquier commit al código generado, validación automática.

**Patrón:**
```python
# En GitManager.commit()
integrity_result = goal_integrity_validator.check(project)
if not integrity_result.is_valid:
    raise IntegrityError(integrity_result.issues)
git.commit(message)
```

**Invariante:** no hay commits sin validación pasada.

### Conexión 5: UsageMonitor escucha todos los drivers

Cada llamada se registra automáticamente.

**Patrón:**
```python
# En BaseDriver.call()
response = await self._execute_call(context)
UsageMonitor.record(
    model=self.model_id,
    tokens_in=response.tokens_input,
    tokens_out=response.tokens_output,
    cost=self.calculate_cost(response),
    role=context.metadata.get("role"),
    project_id=context.metadata.get("project_id")
)
return response
```

**Invariante:** ninguna llamada a IA pasa sin ser registrada.

### Conexión 6: Eventos vía WebSocket al UI

Todo lo que pasa en el Kernel que el usuario debería ver, emite un evento.

**Patrón:**
```python
# En cualquier componente
await event_bus.emit(Event(
    type="module_completed",
    project_id=project.id,
    data={"module": "auth", "status": "success"}
))
```

**Invariante:** la UI no hace polling. Todo es reactivo a eventos.

### Conexión 7: Skills y perfiles vía ContextBuilder

Aplicados siempre al armar contextos, nunca consultados aparte.

**Patrón:**
```python
# En ContextBuilder.build()
active_skills = skill_matcher.get_active(project, role)
active_profile = profile_matcher.get_active(project, role)
knowledge_chunks = knowledge_orchestrator.query(
    task, active_skills, active_profile
)
# Todo se combina en el contexto final
```

**Invariante:** los agentes no "consultan skills" aparte del contexto. Todo viene pre-procesado.

### Conexión 8: ProjectRunner después de DockerSandbox

DockerSandbox valida unidades, ProjectRunner valida el proyecto completo.

**Patrón:**
```python
# Después de generar un módulo
await docker_sandbox.run_tests(module.tests)
# Cuando el módulo se integra al proyecto
await project_runner.verify_integration(project)
```

**Invariante:** ambos niveles deben pasar.

---

## 8. ESTRATEGIA DE TESTING POR FASE

### Fase 1: Tests de drivers individuales

- Test unitario por driver
- Verificar respuesta, tokens, costos
- Mock de APIs para tests rápidos

### Fase 2-3: Tests de flujo

- Test de entrevista end-to-end
- Test de persistencia (abrir, cerrar, reabrir proyecto)

### Fase 4-5: Tests de integridad

- Tests de Goal Tree operations
- Tests de Goal Integrity Validator
- Casos edge: modificar árbol, detectar huérfanos

### Fase 6-7: Tests de construcción

- Test con CRUD simple como proyecto estándar
- Verificar que se construye, pasa tests, corre
- Benchmark de tiempo y costo

### Fase 8: Tests de UI

- Tests de WebSocket
- Tests de eventos del Orchestrator llegando al frontend

### Fase 9-14: Tests de capacidades avanzadas

- Tests de modificaciones con GoalInterpreter
- Tests de branching (construir dos ramas, comparar)
- Tests de visión (con pages simuladas)
- Tests de Telegram (con bot de prueba)

### Testing continuo (todas las fases)

- GitHub Actions (si aplica) con tests en cada PR
- Tests de regresión en cada cambio
- Tests de integración con APIs reales (limitados, caros)

---

## 9. INTEGRACIÓN CON CLAUDE CODE

Claude Code te acompaña en el desarrollo. Algunas recomendaciones:

### Al empezar cada sesión

Claude Code debería:
1. Leer `CLAUDE.md` (contexto rápido)
2. Leer documentos en `docs/` relevantes
3. Inspeccionar estado actual del proyecto
4. Proponer próximo paso específico

### Durante el desarrollo

- Un componente completo antes de pasar al siguiente
- Commit después de cada componente
- Tests incluidos con la implementación
- Documentación en docstrings

### Cuando aparecen dudas

- Preguntar antes de asumir
- Proponer alternativas con trade-offs
- Esperar confirmación para cambios grandes

### Integración con este documento

Este documento funciona como guía maestra. Claude Code puede:
- Referenciarlo para saber qué toca en cada fase
- Verificar puntos de conexión al integrar componentes
- Validar que cumple contratos e interfaces
- Usarlo para explicar al usuario qué está haciendo

### Qué NO hacer

- No implementar fases adelantadas si las previas no están consolidadas
- No ignorar los principios P1-P10
- No romper contratos definidos en sección 4
- No saltar testing

---

## 10. CHECKPOINTS DE VALIDACIÓN

Al terminar cada fase, validar explícitamente:

### Checkpoint Fase 1
- [ ] Los 3 drivers responden
- [ ] UsageMonitor registra llamadas
- [ ] CostTracker calcula costos correctamente
- [ ] Tests unitarios pasan

### Checkpoint Fase 2
- [ ] Se puede hacer entrevista completa
- [ ] Blueprint.json se genera
- [ ] ContextBuilder arma contextos correctos
- [ ] Orchestrator tiene máquina de estados funcional

### Checkpoint Fase 3
- [ ] Proyectos persisten entre sesiones
- [ ] ChromaDB operativo
- [ ] Git inicializa correctamente en proyectos nuevos
- [ ] Watchdog detecta cambios

### Checkpoint Fase 4
- [ ] Goal Tree se crea y modifica correctamente
- [ ] Metadata se inyecta en código generado
- [ ] GoalIntegrityValidator detecta huérfanos
- [ ] Commits con huérfanos se rechazan

### Checkpoint Fase 5
- [ ] Skills se cargan desde filesystem
- [ ] SkillMatcher asigna automáticamente
- [ ] ProfileMatcher asigna automáticamente
- [ ] ContextBuilder incluye skills/perfiles en contextos

### Checkpoint Fase 6
- [ ] Un CRUD simple se construye end-to-end
- [ ] Tests unitarios del proyecto pasan
- [ ] Cascada de escalado funciona (probar haciendo fallar Qwen)
- [ ] Costos se mantienen bajos (mayoría tareas gratis)

### Checkpoint Fase 7
- [ ] ProjectRunner detecta stack correctamente
- [ ] Proyectos se levantan automáticamente
- [ ] Smoke tests detectan problemas funcionales
- [ ] Docker containers se limpian correctamente

### Checkpoint Fase 8
- [ ] UI se abre con doble click
- [ ] Se puede crear proyecto desde UI
- [ ] Progress llega en tiempo real vía WebSocket
- [ ] Dashboard de costos muestra data real

### Checkpoint Fase 9
- [ ] Modificaciones complejas se procesan correctamente
- [ ] Branching crea rama, ejecuta ambas, compara
- [ ] WisdomAgent genera preguntas proactivas útiles
- [ ] ContextHealthMonitor detecta fatiga

### Checkpoint Fase 10
- [ ] VisionCapturer toma screenshots correctamente
- [ ] VisualInspector detecta errores visibles
- [ ] Loop: screenshot → feedback → regeneración funciona

### Checkpoint Fase 11
- [ ] Telegram bot responde
- [ ] Aprobar checkpoints desde Telegram funciona
- [ ] SystemActionsExecutor abre archivos con validación

### Checkpoint Fase 12
- [ ] Perfil se enriquece con experiencia después de proyectos
- [ ] WebResearcher trae info actualizada
- [ ] ReferenceAnalyzer analiza programas correctamente

### Checkpoint Fase 13
- [ ] IntensityOrchestrator asigna niveles correctamente
- [ ] Paralelismo real funciona sin conflictos
- [ ] Soporte de lenguajes múltiples activo

### Checkpoint Fase 14
- [ ] SODA produce outputs no-código (reportes, análisis)
- [ ] Skills no técnicas se aplican correctamente
- [ ] ProjectTypes funcionan con ciclos de vida propios

---

## APÉNDICE: DECISIONES CLAVE TOMADAS

Estas decisiones son vinculantes durante el desarrollo. No proponerse cambios sin razón fuerte.

1. Windows 11 nativo (no WSL2)
2. uv como gestor de Python
3. Python 3.11+ async
4. FastAPI + WebSocket + pywebview + Monaco
5. Ollama para modelos locales, APIs para cloud
6. ChromaDB para vectorial, SQLite para estructural
7. Metadata obligatoria en código generado (anti-huérfanos)
8. Goal Tree como single source of truth
9. ContextBuilder centralizado
10. UsageMonitor desde Fase 1
11. Claude Sonnet sin compromiso para: GoalInterpreter, Auditores
12. Gemini como workhorse gratis
13. Qwen 14B como generador principal
14. Claude Haiku como primer nivel pago
15. Cascada de escalado de 6 niveles
16. Telegram antes de WhatsApp
17. Perplexity API antes que scraping para web research
18. Skills y perfiles asignados por IA (no por usuario)
19. Perfiles acumulan experiencia vía ProfileEvolution
20. Branching pragmático para cambios grandes

---

## FINAL

Este documento es la guía operativa completa. Con esto tenés:

- El mapa completo del sistema
- El orden correcto de construcción
- Los puntos de conexión críticos
- Las verificaciones en cada fase
- Las decisiones vinculantes

Cuando surjan dudas específicas, volvé a la sección relevante. Cuando quieras avanzar, seguí la secuencia de fases. Cuando integres componentes, respetá los contratos de la sección 4.

La clave del desarrollo eficiente es no saltar fases, no romper contratos, y no agregar complejidad innecesaria. Fase por fase, componente por componente, con tests y commits frecuentes.

Suerte con la construcción.
