================================================================================
  SODA — Software On-Demand Assembler
  by BlackMagicBox
================================================================================

  Sistema multi-agente de generación automática de software.
  Describe lo que querés construir. SODA lo genera.

================================================================================
  INDICE
================================================================================

  1. ¿Qué es SODA?
  2. Requisitos del sistema
  3. Instalación paso a paso
  4. Configuración de API Keys
  5. Cómo usar SODA
  6. Explicación del pipeline (fases)
  7. Funciones implementadas
  8. Tecnologías soportadas
  9. Estructura del proyecto
 10. Solución de problemas frecuentes
 11. Notas de arquitectura

================================================================================
  1. ¿QUÉ ES SODA?
================================================================================

SODA es una plataforma de generación automática de software que orquesta
múltiples modelos de inteligencia artificial para producir proyectos completos
y funcionales a partir de una descripción en lenguaje natural.

No es un chatbot. Es un sistema de producción que:

  - Interpreta tu descripción y detecta qué tecnologías necesita
  - Genera un blueprint de requerimientos
  - Diseña una arquitectura modular con dependencias
  - Ordena los módulos en un grafo de ejecución
  - Genera el código fuente archivo por archivo
  - Valida la sintaxis con Docker
  - Audita el código según normas del lenguaje
  - Notifica por Telegram cuando termina

El sistema usa tres niveles de modelos:

  LOCAL   → Qwen2.5-Coder:7b (Ollama) — generación rápida y barata
  CLOUD   → Claude Sonnet 4.6 (Anthropic) — escalación en fallos
  CLOUD   → Gemini 2.5 Pro/Flash (Google) — arquitectura e inteligencia

================================================================================
  2. REQUISITOS DEL SISTEMA
================================================================================

  Sistema operativo:  Windows 11 (nativo, NO WSL2)
  Python:             3.11.9 exactamente (se rompe con 3.12+)
  Node.js:            18+ (para el frontend React)
  Docker Desktop:     Cualquier versión reciente con Windows containers
  Ollama:             Última versión (para modelos locales)
  RAM:                16 GB mínimo recomendado
  Espacio en disco:   10 GB libres (modelos Ollama + proyectos generados)

  Conexión a internet requerida para: Claude, Gemini, Google Fonts

================================================================================
  3. INSTALACIÓN PASO A PASO
================================================================================

  PASO 1 — Clonar o descomprimir el proyecto
  -------------------------------------------
  Colocar la carpeta SODA-PROJECT en el directorio que prefieras.
  Ejemplo: D:\Desktop\iacomp\SODA-PROJECT

  PASO 2 — Instalar dependencias Python
  --------------------------------------
  Abrir una terminal en la raíz del proyecto y ejecutar:

    pip install -r requirements.txt

  Si requirements.txt no existe, instalar manualmente:

    pip install fastapi uvicorn anthropic google-generativeai httpx
    pip install python-dotenv pywebview websockets python-telegram-bot==22.*
    pip install pytest pytest-asyncio

  PASO 3 — Instalar Ollama y el modelo local
  -------------------------------------------
  1. Descargar Ollama desde https://ollama.com
  2. Instalarlo en Windows
  3. Abrir terminal y ejecutar:

       ollama pull qwen2.5-coder:7b

  4. Verificar que está disponible:

       ollama list

  PASO 4 — Instalar Docker Desktop
  ---------------------------------
  1. Descargar Docker Desktop desde https://docker.com
  2. Instalarlo (requiere reinicio)
  3. Abrirlo y esperar a que esté en estado "Running"
  4. Verificar en terminal:

       docker --version

  PASO 5 — Construir el frontend React (opcional)
  -------------------------------------------------
  Solo si se quiere usar la interfaz CopilotKit (/copilot):

    cd ui\soda-react-ui
    npm install
    npm run build

  PASO 6 — Crear el archivo .env
  --------------------------------
  En la raíz del proyecto (misma carpeta que server.py o que kernel/),
  crear el archivo  .env  con el siguiente contenido:

    ANTHROPIC_API_KEY=sk-ant-...
    GEMINI_API_KEY=AIza...
    OLLAMA_BASE_URL=http://localhost:11434
    TELEGRAM_BOT_TOKEN=           (opcional)

  Ver sección 4 para obtener las keys.

  PASO 7 — Iniciar SODA
  ----------------------
  Desde la raíz del proyecto:

    python ui/server.py

  Abrir el navegador en:

    http://localhost:8000          ← Interfaz principal (launcher)
    http://localhost:8000/copilot  ← Interfaz CopilotKit (asistente IA)

================================================================================
  4. CONFIGURACIÓN DE API KEYS
================================================================================

  ANTHROPIC (Claude)
  ------------------
  1. Ir a https://console.anthropic.com
  2. Crear cuenta o ingresar
  3. Ir a "API Keys" → "Create Key"
  4. Copiar la key (empieza con sk-ant-)
  5. Pegar en .env como: ANTHROPIC_API_KEY=sk-ant-...

  GOOGLE GEMINI
  -------------
  1. Ir a https://aistudio.google.com
  2. Crear cuenta con Google
  3. Ir a "Get API Key"
  4. Copiar la key (empieza con AIza)
  5. Pegar en .env como: GEMINI_API_KEY=AIza...

  TELEGRAM BOT (opcional — para notificaciones)
  ----------------------------------------------
  1. Abrir Telegram y buscar @BotFather
  2. Enviar /newbot y seguir las instrucciones
  3. Guardar el token que entrega
  4. Pegar en .env como: TELEGRAM_BOT_TOKEN=...
  5. En la interfaz SODA, ir a Config → Telegram → Parear

  Verificar que las keys funcionan desde la interfaz:
  Config → Proveedores de IA → Botón "Test"

================================================================================
  5. CÓMO USAR SODA
================================================================================

  CREAR UN PROYECTO NUEVO
  -----------------------
  1. Abrir http://localhost:8000
  2. Ir a la pestaña "Nuevo Proyecto"
  3. Escribir la descripción del software que querés crear.
     Ejemplos:
       "API REST con FastAPI y SQLite para gestionar tareas"
       "App web React con autenticación JWT y PostgreSQL"
       "Juego en C++ con SDL2 para Windows"
       "Bot de Telegram en Python para recordatorios"

  4. Elegir la temperatura del Copilot:
       baja  → 1 revisión, rápido, menos tokens
       media → 3 revisiones, equilibrado (recomendado)
       alta  → revisiones ilimitadas, más refinado

  5. Hacer clic en "Generar"
  6. Observar el progreso en tiempo real en la pestaña "Estado"

  El proyecto generado aparece en:
    SODA-PROJECT\projects\<nombre_proyecto>\source\

  MODIFICAR UN PROYECTO EXISTENTE
  --------------------------------
  1. Seleccionar el proyecto en el historial
  2. Ir a "Modificar"
  3. Describir el cambio: "agregar autenticación", "cambiar base de datos"
  4. SODA detecta el impacto y regenera solo los módulos afectados

  REFUNDAR UN PROYECTO
  --------------------
  Si el proyecto tiene problemas estructurales, se puede refundar:
  1. Seleccionar el proyecto
  2. Ir a "Refundar"
  3. SODA lee el código existente, resume el objetivo y lo regenera desde cero

  EJECUTAR EL PROYECTO GENERADO
  ------------------------------
  En la pestaña "Estado", cuando el pipeline termina aparece el panel de launch:
  1. El comando de ejecución se detecta automáticamente
  2. Hacer clic en "Lanzar"
  3. SODA abre una terminal con el proyecto corriendo

================================================================================
  6. EXPLICACIÓN DEL PIPELINE (FASES)
================================================================================

  CAP  → Detección de capacidades
         Gemini analiza la descripción y selecciona qué skills y perfil usar.
         Ejemplo: "FastAPI + SQLite" → skill_fastapi + skill_sqlite + profile_backend_api

  WISDOM → Detección de ambigüedades
           Gemini revisa si hay puntos poco claros antes de generar requerimientos.
           Si hay ambigüedad, pregunta al usuario antes de continuar.

  REQ  → Generación de blueprint
         Claude genera blueprint.json con:
         nombre, descripción, funcionalidades, stack, comandos de instalación/ejecución.
         BlueprintValidator verifica campos obligatorios.

  ARCH → Generación de arquitectura
         Gemini genera architecture.json con módulos, dependencias y contratos.
         ArchitectureValidator verifica rutas, dependencias cruzadas y build infra.
         Si hay errores, intenta auto-reparar. Si falla 3 veces, escala a Claude.

  PLAN → Construcción del grafo de ejecución
         DependencyGraph construye un DAG con Kahn topological sort.
         Los módulos se agrupan en niveles de ejecución paralela.

  DEV  → Generación de código
         Por cada módulo, por cada archivo:
           Intento 1-3: Qwen2.5-Coder local (Ollama)
           Intento 4:   Claude Sonnet
           Intento 5:   Gemini Pro
           Intento 6:   Claude Haiku
         Si todos fallan: guarda el archivo con validated=False y continúa.
         La sintaxis se valida con Docker entre intentos.

  AUDIT → Auditoría de normas por lenguaje
          LanguageAuditor detecta el lenguaje y aplica reglas específicas.
          Si hay violaciones, pide fixes a Claude o Gemini.
          Genera audit_report.json en el workspace.

  DONE → Notificación y entrega
         Notifica por WebSocket a la UI y opcionalmente por Telegram.
         El proyecto queda en projects/<nombre>/source/

================================================================================
  7. FUNCIONES IMPLEMENTADAS
================================================================================

  NÚCLEO DEL PIPELINE
  --------------------
  ✓ Orquestador principal (orchestrator.py)
    Ejecuta el pipeline completo CAP→REQ→ARCH→PLAN→DEV→AUDIT→DONE
    Maneja estados, notificaciones y errores en cada fase.

  ✓ Generador de código multi-escalada (code_generator.py)
    6 niveles de escalación: Qwen×3 → Claude → Gemini → Claude Haiku
    Validación de sintaxis Docker entre intentos.
    Continúa sin abortar si todos los modelos fallan.

  ✓ Grafo de dependencias (dependency_graph.py)
    Construye DAG desde architecture.json
    Kahn topological sort con agrupación por niveles paralelos
    Detección y ruptura de ciclos

  ✓ Interpretador de objetivos (goal_interpreter.py)
    Clasifica cambios del usuario en: bug_fix, feature, refactor, structural, scope
    Determina módulos afectados y si requiere rama nueva

  ✓ Analizador de impacto (impact_analyzer.py)
    Calcula dependencias transitivas de los cambios
    Determina nivel de riesgo (low/medium/high/critical)

  ✓ Motor de refundación (refoundation.py)
    Lee código existente, resume en descripción condensada
    Reinicia pipeline desde cero con contexto del proyecto anterior

  VALIDACIÓN MECÁNICA
  --------------------
  ✓ Validador de arquitectura (architecture_validator.py)
    Verifica: campos obligatorios, rutas de archivo normalizadas,
    dependencias cross-referenciadas, contratos inter-módulo,
    coherencia del stack, infraestructura de build.
    Auto-inyecta módulo infraestructura_build en C++/Rust/Go.

  ✓ Validador de blueprint (blueprint_validator.py)
    Verifica: nombre_proyecto, descripcion, funcionalidades.
    Auto-convierte funcionalidades string → lista.

  ✓ Auditor de lenguajes (language_auditor.py)
    11 lenguajes soportados: Python, Node/TS, React, C#, Java/Spring,
    Go, Rust, PHP/Laravel, Flutter, Android/Kotlin, C++/CMake.
    Reglas mecánicas por lenguaje + solicitud de fixes a IA.
    Score 0-100 por proyecto.

  INTELIGENCIA Y ANÁLISIS
  ------------------------
  ✓ Agente de sabiduría (wisdom_agent.py)
    Detecta ambigüedades, riesgos y observaciones en el proyecto.
    Genera sugerencias antes de comprometer la generación.

  ✓ Consultor Copilot (copilot_consultant.py)
    Revisa blueprint, arquitectura, skills, plan y código generado.
    Configurable en temperatura: baja/media/alta.

  ✓ Monitor de salud del contexto (context_health_monitor.py)
    Monitorea tokens, latencia y tasa de error en tiempo real.
    Umbrales calibrados para Qwen local (15-25s normal).

  ✓ Profiling y evolución (profile_evolution.py)
    Aprende de los proyectos generados para mejorar perfiles.

  DRIVERS DE IA
  --------------
  ✓ ClaudeDriver   — Anthropic Claude Sonnet 4.6
  ✓ GeminiDriver   — Google Gemini 2.5 Pro/Flash
    Manejo especial de thinking parts (Gemini 2.5 Pro)
    thinkingBudget:0 para llamadas JSON
    responseMimeType: application/json para forzar JSON válido
  ✓ OllamaDriver   — Qwen2.5-Coder:7b local
  ✓ OpenAIDriver   — GPT-4 / GPT-4o
  ✓ GenericOpenAIDriver — Proveedores compatibles con OpenAI
  ✓ AIProviderHub  — Registro central de proveedores
  ✓ DriverFactory  — Instanciación dinámica por nombre

  HABILIDADES Y PERFILES
  -----------------------
  ✓ SkillMatcher   — Selecciona technology packs relevantes por descripción
  ✓ ProfileMatcher — Selecciona perfil de desarrollador (fullstack, backend, etc.)
  ✓ CapabilityPacks — Packs prearmados: auth_complete, payment_processing, etc.
  ✓ ProfileEvolution — Adapta perfiles a los resultados de generación

  Skills disponibles (32):
    Backend:    FastAPI, Node.js, NestJS, Java Spring, C#/.NET, Go, Rust, PHP/Laravel
    Frontend:   React, Angular, Vue, Next.js, Electron
    Mobile:     Flutter, React Native, Android Kotlin
    Sistemas:   C++/CMake
    Datos:      PostgreSQL, MongoDB, SQLite
    Auth:       JWT Auth
    IA:         Anthropic, OpenAI, LangChain
    Dominio:    Finance, Legal, Marketing, UX

  Perfiles disponibles (7):
    profile_web_fullstack, profile_backend_api, profile_frontend_dev,
    profile_fullstack_js, profile_java_dev, profile_dotnet_dev, profile_general_dev

  LINAJE Y RAMAS
  ---------------
  ✓ ProjectLineage — Log append-only de todos los proyectos y ramas
  ✓ BranchManager  — Crea ramas cuando hay cambios estructurales
    Copia workspace completo antes de modificar
    Permite comparar versiones alternativas

  EJECUCIÓN Y RUNTIME
  --------------------
  ✓ ProjectRunner  — Instala dependencias y lanza proyectos generados
  ✓ SmokeTester    — Prueba endpoints HTTP post-lanzamiento
  ✓ DockerSandbox  — Ejecuta validaciones en contenedor aislado (npipe Windows)
  ✓ ServiceOrchestrator — Docker Compose para proyectos multi-servicio
  ✓ StackDetector  — Detecta stack por comandos de ejecución
  ✓ PortManager    — Registra y libera puertos TCP

  COMUNICACIÓN
  -------------
  ✓ TelegramGateway — Notificaciones y comandos remotos
    Comandos: /status, /projects, /pair
    Pareado por código de verificación único
  ✓ ProjectChat     — Q&A sobre el proyecto generado (usa blueprint+arquitectura)
  ✓ UserInteraction — Preguntas al usuario durante el pipeline (timeout configurable)

  MONITORING Y COSTOS
  --------------------
  ✓ UsageMonitor   — SQLite: registra cada llamada IA con tokens, latencia, costo
  ✓ CostTracker    — Estima costo por proveedor/modelo
  ✓ AlertManager   — Alertas por umbral de gasto o tasa de error
  ✓ ResourceMonitor — Monitorea VRAM, CPU y recomienda modelo óptimo

  INTERFAZ WEB (FastAPI + WebSocket)
  ------------------------------------
  ✓ Interfaz principal (ui/static/index.html)
    Tema: negro puro con tipografía blanco/amarillo/cian/magenta
    Tabs: Nuevo Proyecto, Estado en tiempo real, Historial, Config
    Visualización del pipeline fase por fase
    Log de generación en vivo vía WebSocket
    Panel de launch con comando auto-detectado

  ✓ Interfaz CopilotKit (/copilot)
    React + CopilotKit para chat con acciones de creación de proyectos
    Mismo tema negro/magenta/cian
    Acción create_project integrada al pipeline

  ✓ 35+ endpoints REST (ver sección anterior del pipeline)
  ✓ WebSocket /ws — stream de eventos en tiempo real

  ÁRBOL DE OBJETIVOS
  -------------------
  ✓ GoalTree       — Árbol jerárquico: proyecto → módulos → archivos
  ✓ MetadataInjector — Inserta goal_id y goal_hash en código Python
  ✓ GoalIntegrityValidator — Verifica que el código cumple sus objetivos

  CONOCIMIENTO BASE
  ------------------
  ✓ ContextBuilder — Construye prompts desde plantillas en prompts/
  ✓ ChromaDBManager — Índice vectorial para búsqueda semántica en skills/profiles
  ✓ WebResearcher  — Fetch y parsing HTML para investigación

================================================================================
  8. TECNOLOGÍAS SOPORTADAS PARA GENERACIÓN
================================================================================

  BACKEND
    Python (FastAPI, Flask, Django)
    Node.js (Express, NestJS)
    Java (Spring Boot)
    C# (.NET, ASP.NET Core)
    Go
    Rust
    PHP (Laravel)

  FRONTEND
    React (Vite, CRA)
    Angular
    Vue.js
    Next.js
    Electron (apps de escritorio)

  MOBILE
    Flutter (iOS + Android)
    React Native
    Android nativo (Kotlin)

  SISTEMAS / EMBEBIDO
    C++ con CMake (Win32, SDL2, OpenGL)

  BASE DE DATOS
    PostgreSQL, MySQL
    MongoDB
    SQLite

  INFRAESTRUCTURA
    Docker / Docker Compose
    GitHub Actions (CI/CD básico)

================================================================================
  9. ESTRUCTURA DEL PROYECTO
================================================================================

  SODA-PROJECT/
  ├── kernel/                    ← Motor central
  │   ├── orchestrator.py        ← Entry point del pipeline
  │   ├── code_generator.py      ← Generación con escalación 6 niveles
  │   ├── dependency_graph.py    ← DAG + topological sort
  │   ├── drivers/               ← Adaptadores de IA (Claude, Gemini, Ollama…)
  │   ├── intelligence/          ← GoalInterpreter, WisdomAgent, ImpactAnalyzer…
  │   ├── validation/            ← ArchitectureValidator, BlueprintValidator
  │   ├── audit/                 ← LanguageAuditor (11 lenguajes)
  │   ├── capabilities/          ← SkillMatcher, ProfileMatcher, CapabilityPacks
  │   ├── execution/             ← ProjectRunner, SmokeTester, DockerSandbox…
  │   ├── lineage/               ← ProjectLineage, BranchManager
  │   ├── communication/         ← Telegram, ProjectChat, UserInteraction
  │   ├── monitoring/            ← UsageMonitor, CostTracker, AlertManager
  │   ├── goals/                 ← GoalTree, MetadataInjector
  │   ├── context/               ← ContextBuilder (carga prompts/)
  │   ├── vision/                ← VisionCapturer, VisualInspector
  │   ├── knowledge/             ← ChromaDB vector store
  │   └── orchestration/         ← IntensityOrchestrator (baja/media/alta)
  │
  ├── ui/
  │   ├── server.py              ← FastAPI + WebSocket + CopilotKit
  │   ├── static/
  │   │   ├── index.html         ← Interfaz principal (launcher)
  │   │   └── js/app.js          ← Lógica frontend del launcher
  │   └── soda-react-ui/         ← App React para /copilot
  │       ├── src/App.jsx
  │       ├── src/App.css
  │       └── dist/              ← Build compilado (servido por FastAPI)
  │
  ├── skills/base/               ← 32 packs de tecnología
  │   └── skill_*/
  │       ├── manifest.yaml      ← Keywords de activación
  │       ├── system_prompt.md   ← Contexto especializado para IA
  │       └── knowledge/         ← Documentación técnica del skill
  │
  ├── profiles/base/             ← 7 perfiles de desarrollador
  │   └── profile_*/
  │       ├── identity.yaml
  │       ├── experience/
  │       └── style/
  │
  ├── prompts/                   ← Plantillas de prompt por proveedor y rol
  │   ├── claude/
  │   ├── gemini/
  │   └── ollama/
  │
  ├── projects/                  ← Proyectos generados
  │   └── <nombre_proyecto>/
  │       ├── source/            ← Código fuente generado
  │       ├── blueprint.json
  │       ├── architecture.json
  │       ├── audit_report.json  ← Resultado de auditoría
  │       └── metadata.json
  │
  ├── tests/
  │   ├── test_pipeline.py       ← 19 tests de pipeline con mocks
  │   └── test_unit.py           ← 28 tests unitarios
  │
  ├── .env                       ← API keys (NO subir a git)
  └── README.txt                 ← Este archivo

================================================================================
  10. SOLUCIÓN DE PROBLEMAS FRECUENTES
================================================================================

  PROBLEMA: La interfaz sigue mostrando fondo azul
  -------------------------------------------------
  Causa: El navegador cachea el HTML antiguo.
  Solución: Hacer Ctrl+Shift+R (hard refresh) o borrar caché del navegador.

  PROBLEMA: "No module named anthropic" u otro paquete
  -----------------------------------------------------
  Solución: pip install anthropic google-generativeai httpx

  PROBLEMA: Qwen no responde / timeout
  -------------------------------------
  1. Verificar que Ollama está corriendo:
       ollama serve
  2. Verificar el modelo instalado:
       ollama list
  3. Si no aparece qwen2.5-coder:7b:
       ollama pull qwen2.5-coder:7b

  PROBLEMA: Error en arquitectura "tras 3 intentos"
  --------------------------------------------------
  Causa común: Gemini 2.5 Pro retorna partes de "pensamiento" antes del JSON.
  Estado: Corregido en gemini_driver.py (se omiten las partes con thought=True).
  Si persiste: verificar GEMINI_API_KEY en .env

  PROBLEMA: Docker no valida sintaxis
  ------------------------------------
  1. Verificar que Docker Desktop está abierto y en estado Running
  2. Verificar acceso npipe:
       docker run --rm hello-world
  3. Si falla, el sistema continúa sin validación de sintaxis (no aborta)

  PROBLEMA: El pipeline se queda en fase ARCH
  --------------------------------------------
  1. Revisar logs en la pestaña Estado
  2. Si dice "Gemini×3 + Claude fallback": problema con las API keys
  3. Verificar las keys en Config → Proveedores → Test

  PROBLEMA: No llegan notificaciones de Telegram
  -----------------------------------------------
  1. Verificar TELEGRAM_BOT_TOKEN en .env
  2. En la interfaz: Config → Telegram → Generar código de pareo
  3. Enviar el código al bot en Telegram
  4. Verificar que el bot no está bloqueado en Telegram

  PROBLEMA: Falla "port already in use"
  --------------------------------------
  El servidor usa el puerto 8000 por defecto.
  Solución: matar el proceso anterior o cambiar el puerto en server.py

  EJECUTAR TESTS
  --------------
    python -m pytest tests/ -v

  Los tests usan mocks para todas las APIs externas.
  No requieren API keys ni Docker ni Ollama para correr.
  ~47 tests, tiempo esperado ~7 segundos.

================================================================================
  11. NOTAS DE ARQUITECTURA
================================================================================

  DECISIONES IMPORTANTES (no cambiar sin analizar impacto)
  ---------------------------------------------------------

  1. _notify() usa timeout=0.05s (fire-and-forget)
     → Si se aumenta, bloquea el pipeline completo

  2. load_dotenv() se llama explícitamente en server.py y orchestrator.py
     → Sin esto, las API keys no se cargan cuando se inicia desde la UI

  3. DockerSandbox usa npipe (Windows)
     → No usar unix socket en esta plataforma

  4. thinkingBudget:0 en llamadas JSON a Gemini 2.5
     → Gemini 2.5 Pro en modo pensamiento retorna múltiples parts[]
     → parts[0] tiene "thought":true (razonamiento interno, no es el output)
     → El output real está en la primera parte sin ese flag
     → Con thinkingBudget:0 y responseMimeType:"application/json" se evita

  5. Escalación Qwen×3 → Claude:
     → Error rate normal en Qwen puede llegar al 50% por burst de 3 intentos
     → ERROR_RATE_WARN está calibrado en 0.50 para evitar falsos positivos

  UMBRALES CALIBRADOS
  --------------------
    TOKEN_WARN_THRESHOLD:  80,000  (~80% del límite 100k)
    SLOW_CALL_S:           30s     (Qwen normal: 15-25s)
    ERROR_RATE_WARN:       0.50    (evita falso positivo en burst Qwen×3)
    ROLLING_WINDOW:        15      (suaviza ráfagas de escalación)

================================================================================
  BLACKMAGICBOX © 2026 — SODA v1.0
================================================================================
