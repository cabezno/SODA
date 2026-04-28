# Como Funciona SODA Paso A Paso

## Objetivo De Este Documento

Este documento explica como funciona SODA a nivel operativo:

- cual es el flujo completo desde que entra un pedido hasta que sale una aplicacion,
- que hace cada modulo principal del sistema,
- como se comunican entre si,
- que artefactos va generando en disco,
- y cuales son las fases donde hoy hay mas automatizacion o mas riesgo.

No describe el contenido de `projects/` como producto final generado por cada proyecto,
sino el funcionamiento interno de la propia aplicacion SODA.

## Que Es SODA

SODA es un sistema multiagente de generacion de software. La interfaz de usuario entra por FastAPI,
el nucleo de orquestacion esta en Python, y el trabajo de analisis y generacion se reparte entre varios proveedores de IA:

- Gemini para seleccion de capacidades, ambiguedades, arquitectura y evolucion,
- Claude para requerimientos, revisiones y tareas de mayor precision,
- Ollama o Qwen como generador local primario de codigo,
- y varios modulos deterministas de Python para planificacion, persistencia, validacion y ejecucion.

La idea central es esta: SODA no le pide a un solo modelo que escriba todo de una vez. Primero interpreta el pedido, luego lo convierte en blueprint, despues lo transforma en arquitectura modular, arma un DAG de ejecucion y por ultimo genera el codigo por modulos con validaciones intermedias.

## Entradas Reales Del Sistema

### 1. UI y API

El punto de entrada principal es `ui/server.py`.

Desde ahi SODA expone:

- endpoints HTTP para lanzar el pipeline,
- WebSocket para emitir eventos en tiempo real,
- integracion opcional con CopilotKit,
- y bridge hacia Telegram para notificaciones.

Las dos rutas conceptuales mas importantes son:

- `POST /api/run` para arrancar un proyecto nuevo,
- acciones de CopilotKit como `create_project` y `resume_project`.

### 2. Desktop launcher

`ui/launcher.py` levanta la aplicacion de escritorio con pywebview, pero el backend real sigue siendo `ui/server.py`.

### 3. Reanudacion e importacion

Una vez iniciado un proyecto, el sistema tambien puede entrar por:

- `SodaOrchestrator.resume(project_id)` para retomar un pipeline existente,
- `SodaOrchestrator.import_from_code(...)` para arrancar desde codigo que ya existe,
- `SodaOrchestrator.modify(project, request)` para evolucionar un proyecto generado,
- `SodaOrchestrator.refound(project)` para rehacer el proyecto desde un resumen del estado actual.

## Vista General Del Flujo

El flujo principal de generacion sigue esta secuencia:

```text
Usuario o UI
  -> ui/server.py
  -> SodaOrchestrator.run()
  -> CAPABILITIES
  -> WISDOM
  -> REQUIREMENTS
  -> ARCHITECTURE
  -> PLANNING
  -> DESIGN
  -> DEVELOPMENT
  -> VERIFY
  -> VALIDATION / SECURITY / TESTS / API CONTRACT / AUDIT
  -> BOOT AGENT
  -> DOCS
  -> SETUP_AND_VERIFY
  -> EVOLUTION
  -> DONE o FAILED
```

La comunicacion no es solo lineal. Entre esas fases tambien hay:

- lectura y escritura de archivos en el workspace del proyecto,
- broadcast de eventos a la UI por WebSocket,
- avisos a Telegram,
- consultas a base vectorial,
- y rondas de regeneracion cuando algo falla.

## Flujo Paso A Paso Del Pipeline Principal

## Paso 1 - La UI recibe el pedido

`ui/server.py` recibe descripcion, nombre de proyecto y nivel de `copilot_temperature`.

En ese punto hace tres cosas importantes:

- valida que no haya otro pipeline corriendo,
- crea una tarea asincronica para no bloquear la API,
- instancia `SodaOrchestrator` y llama `run()`.

Tambien inicializa servicios auxiliares que viven alrededor del pipeline:

- `ProjectRunner`,
- `ProjectManager`,
- `UsageMonitor`,
- `AlertManager`,
- `ProjectChat`,
- `WebResearcher`,
- `VisionCapturer`,
- `VisualInspector`,
- `IntensityOrchestrator`,
- `TelegramGateway`.

## Paso 2 - El orquestador crea el proyecto interno

`kernel/orchestrator.py` es el centro del sistema.

Cuando se instancia `SodaOrchestrator` arma casi todo el grafo de dependencias en memoria:

- drivers de IA,
- `ContextBuilder`,
- `CodeGenerator`,
- matchers y managers de skills y perfiles,
- agentes de inteligencia,
- conocimiento vectorial,
- `ProjectRunner`,
- `BootAgent`,
- validadores,
- auditores,
- monitoreo y aprendizaje.

Cuando se llama `run()`:

1. resetea metricas de performance,
2. crea el objeto `Project`,
3. crea el workspace en `projects/<id>/`,
4. notifica `START` a UI y Telegram,
5. aplica intensidad, tipo de proyecto y capability packs,
6. empieza a ejecutar fases.

## Paso 3 - CAPABILITIES

Fase implementada en `_phase_capabilities()` dentro de `kernel/orchestration/phase_mixin.py`.

Objetivo:

- decidir skills base,
- elegir un perfil base,
- enriquecer el contexto antes de pedir blueprint o arquitectura.

Modulos implicados:

- `kernel/capabilities/skill_matcher.py`,
- `kernel/capabilities/profile_matcher.py`,
- `kernel/capabilities/skill_manager.py`,
- `kernel/capabilities/profile_manager.py`,
- `kernel/capabilities/capability_packs.py`.

Comunicacion:

- el orquestador llama a Gemini por medio de los matchers,
- los resultados se guardan en `project.skills`, `project.profile` y `project.capability_packs`,
- luego esos datos vuelven a entrar en `ContextBuilder` cuando se construyen prompts.

Salida de esta fase:

- lista de skills activas,
- perfil activo,
- packs de capacidad sugeridos.

## Paso 4 - WISDOM

Fase `_phase_wisdom()`.

Objetivo:

- detectar ambiguedades en la descripcion del usuario,
- pedir aclaraciones cuando hace falta,
- refinar el pedido antes de generar requerimientos.

Modulos implicados:

- `kernel/intelligence/wisdom_agent.py`,
- `kernel/communication/user_interaction.py`,
- `_ask_user_clarification()` del orquestador.

Comunicacion:

- el WisdomAgent analiza el texto,
- si necesita mas precision, el orquestador emite un evento `USER_QUESTION`,
- la UI responde mediante el gateway de interaccion,
- la respuesta se reincorpora al flujo.

Esta fase evita que las siguientes trabajen con un requerimiento ambiguo.

## Paso 5 - REQUIREMENTS

Fase `_phase_requirements()`.

Objetivo:

- transformar la descripcion en `blueprint.json`.

Como funciona:

1. toma la descripcion del proyecto,
2. consulta memoria vectorial para buscar proyectos similares,
3. arma el prompt con `ContextBuilder`,
4. llama al rol `requirements_interviewer`, normalmente en Claude,
5. intenta parsear JSON,
6. valida el blueprint con `BlueprintValidator`,
7. si Copilot detecta problemas, puede regenerar segun la temperatura configurada,
8. persiste el resultado en disco.

Artefacto principal generado:

- `projects/<id>/blueprint.json`

Comunicacion entre modulos:

- `ContextBuilder` carga prompt base desde `prompts/claude/requirements_interviewer.md`,
- `CopilotConsultant` revisa el resultado,
- `BlueprintValidator` limpia y valida la estructura,
- `ProjectManager` y `_save_state()` persisten el estado.

## Paso 6 - ARCHITECTURE

Fase `_phase_architecture()`.

Objetivo:

- convertir el blueprint en `architecture.json`.

Como funciona:

1. serializa el blueprint,
2. agrega restricciones del `RequirementsStore` si existen,
3. llama a Gemini con el rol `global_architect`,
4. parsea JSON,
5. valida con `ArchitectureValidator`,
6. vuelve a pasar por Copilot para revisar si conviene regenerar,
7. escribe `architecture.json`,
8. construye el goal tree,
9. en paralelo genera tambien un `master_contract` para una migracion futura.

Artefactos generados:

- `projects/<id>/architecture.json`
- `projects/<id>/goal_tree.json` o equivalente derivado

Punto importante:

`architecture.json` define `modulos`, responsabilidades, dependencias y contratos.
Ese archivo no es solo documentacion. Es el contrato operativo que despues consume el planificador.

## Paso 7 - PLANNING

Fase `_phase_planning()`.

Objetivo:

- convertir la arquitectura en un plan de ejecucion topologico.

Modulo principal:

- `kernel/dependency_graph.py`

Como funciona:

1. toma la lista de modulos de `architecture.json`,
2. filtra dependencias invalidas o autoreferencias,
3. construye el grafo,
4. detecta ciclos,
5. rompe back-edges si hace falta,
6. aplica Kahn para obtener niveles ejecutables,
7. produce un `ExecutionPlan`.

Salida:

- `levels`: grupos de modulos que se pueden generar en paralelo,
- `order`: orden plano topologico,
- `broken_edges`: aristas removidas si habia ciclos.

Esta es una de las partes mas deterministas del sistema: aca no decide la IA, decide Python.

## Paso 8 - DESIGN

Fase `_phase_design()`.

Objetivo:

- inyectar contexto de diseno antes de generar codigo.

Modulos implicados:

- `kernel/design/ui_design_agent.py`,
- `kernel/design/design_context_injector.py`,
- `kernel/execution/html_template_injector.py`.

Uso real:

- sirve para que el generador tenga una direccion visual y de UI,
- preinyecta plantillas HTML o contexto de diseno,
- deja insumos listos para que la fase de desarrollo no arranque desde cero.

## Paso 9 - DEVELOPMENT

Fase `_phase_development()`.

Esta es la fase donde SODA realmente genera archivos.

Como funciona a alto nivel:

1. toma el `ExecutionPlan`,
2. crea o asegura `projects/<id>/source/`,
3. carga contexto de skills y perfil,
4. recorre cada nivel del DAG,
5. genera los modulos de ese nivel en paralelo,
6. al terminar un nivel corre verificacion de sintaxis,
7. persiste estado y goal tree.

El trabajo fino lo hace `CodeGenerator`.

### Como genera `CodeGenerator`

`kernel/code_generator.py` transforma cada modulo de arquitectura en tareas por archivo.

Su flujo interno es este:

1. arma un task JSON con:
   - archivo a generar,
   - modulo,
   - responsabilidad,
   - stack,
   - dependencias del modulo,
   - contratos relevantes,
   - endpoints,
   - feedback de Copilot si existe,
   - codigo ya generado de modulos dependientes,
   - contexto de diseno si corresponde.
2. selecciona el modelo de forma escalonada,
3. intenta generar con Qwen u Ollama,
4. si falla, escala a Gemini y despues a Claude,
5. limpia fences Markdown,
6. corrige `package.json` si encuentra dependencias rotas o versiones inventadas,
7. inyecta metadata de goal en archivos Python,
8. valida sintaxis cuando aplica,
9. devuelve `GeneratedFile` con contenido, goal y estado de validacion.

### Como decide el orden de generacion

El generador no trabaja en vacio. Usa el `dependency_context` para pasarle a cada modulo el codigo real de los modulos de los que depende.

Eso sirve para que el modelo pueda:

- respetar nombres de variables ya generadas,
- usar rutas de import correctas,
- alinear contratos y endpoints,
- evitar inventar schemas incompatibles.

### Como interviene Copilot

Despues de la generacion base, el sistema puede entrar en loops de revision segun intensidad y temperatura:

- mas pasadas de codigo,
- mas regeneracion por fase,
- mas revision de conformidad.

### Artefacto de esta fase

El producto principal es:

- `projects/<id>/source/` con todos los archivos del proyecto generado.

## Paso 10 - VERIFY

Fase `_phase_verify()`.

Objetivo:

- revisar conformidad arquitectonica del codigo generado.

Modulos implicados:

- `kernel/intelligence/conformance_verifier.py`,
- `kernel/integrity/goal_integrity_validator.py`,
- `kernel/goals/`.

Que valida:

- que los archivos generados sigan la arquitectura definida,
- que no aparezca codigo huerfano o fuera del diseno,
- que se mantenga trazabilidad entre goals y archivos.

Esta fase no es la ejecucion real del proyecto. Es una validacion de alineacion entre diseño y salida.

## Paso 11 - VALIDACIONES TECNICAS

Despues de development, el pipeline encadena varias validaciones especializadas.

### 11.1 Import validation

`_phase_import_validation()` usa `ImportDependencyValidator` para detectar problemas de imports y dependencias internas.

### 11.2 Security review

`_phase_security_review()` llama a `SecurityReviewer` para revisar riesgos obvios del codigo generado.

### 11.3 Test generation

`_phase_test_generation()` usa `TestGenerator` para producir tests base cuando aplica.

### 11.4 API contract

`_phase_api_contract()` usa `APIContractEnforcer` para alinear frontend y backend segun el contrato definido.

### 11.5 Audit

`_phase_audit()` usa auditores de lenguaje y consistencia general.

Estas capas no todas bloquean igual. Algunas son mas estrictas y otras funcionan hoy como warning o advisory.

## Paso 12 - VALIDATION Y REGENERACION DIRIGIDA

Fase `_phase_validation()` y helper `_validate_and_maybe_regen()`.

Objetivo:

- instalar dependencias si hace falta,
- correr checks de build o compilacion,
- intentar fixes automáticos,
- decidir si conviene regenerar modulos puntuales.

Modulo principal:

- `kernel/project_validator.py`

Como funciona:

1. detecta si el stack necesita herramientas externas,
2. emite eventos `ENV_CHECK`,
3. pregunta permiso al usuario salvo que haya auto confirm,
4. arma `ProjectValidator`,
5. corre `validate_and_fix()` sobre `source/`,
6. si encuentra errores concentrados en pocos modulos, el orquestador puede llamar `_phase_targeted_regeneration()`,
7. vuelve a validar.

Resultado:

- `fixed`,
- `rounds`,
- `failed_modules`,
- `errors_final`,
- y criterio intermedio para decidir si todavia puede llegar a `DONE`.

Este tramo es importante porque separa fallo estructural de codigo versus fallo de entorno.

## Paso 13 - DOCKER SANDBOX

El orquestador intenta ejecutar `docker_sandbox.run_tests(...)`.

Rol actual:

- ejecutar una validacion en contenedor,
- pero hoy debe tratarse como una senal advisory,
- no como la evidencia mas fuerte de calidad.

Esto es importante para entender el sistema real: Docker existe en el pipeline, pero no debe leerse como garantia total de ejecucion correcta.

## Paso 14 - BOOT AGENT

Fase `_phase_boot_agent()`.

Modulo principal:

- `kernel/execution/boot_agent.py`

Objetivo:

- instalar dependencias,
- arrancar la aplicacion,
- capturar los primeros errores reales de runtime,
- reparar automaticamente errores tipicos,
- y reintentar.

Flujo interno de `BootAgent`:

1. bootstrappea `.env` desde `.env.example` si hace falta,
2. detecta comandos de install y run segun el stack,
3. ejecuta instalacion,
4. intenta boot,
5. parsea errores de stdout y stderr,
6. mapea esos errores a archivo y linea cuando puede,
7. llama a Claude o Gemini con el error y los archivos relevantes,
8. aplica fixes,
9. repite hasta `MAX_ROUNDS`.

Artefacto generado:

- `projects/<id>/boot_report.json`

Ese archivo resume:

- stack detectado,
- cantidad de intentos,
- si la fase finalizo bien,
- ultimo conjunto de errores.

## Paso 15 - VISUAL INSPECTION

Fase `_phase_visual_inspection()`.

Objetivo:

- capturar o inspeccionar la UI generada,
- detectar problemas visibles,
- y eventualmente corregirlos.

Modulos implicados:

- `kernel/vision/vision_capturer.py`,
- `kernel/vision/visual_inspector.py`.

Esta parte tiene mas sentido en proyectos con interfaz web o visual.

## Paso 16 - DOCS

Fase `_phase_docs()`.

Objetivo:

- generar documentacion del proyecto generado,
- por ejemplo README o documentacion funcional minima.

No es solo cosmetica. Esta fase deja un entregable mas util para continuar luego el trabajo.

## Paso 17 - SETUP AND VERIFY

Fase `_phase_setup_and_verify()` que delega en `ProjectRunner.setup_and_verify()`.

Modulo principal:

- `kernel/execution/project_runner.py`

Objetivo:

- hacer una verificacion operativa final del runtime.

Flujo de `ProjectRunner`:

1. `install()` corre el comando de instalacion en el directorio correcto,
2. `launch()` arranca el proyecto y registra el proceso en `_PROCESS_REGISTRY`,
3. se escriben logs a `_soda_launch.log`,
4. `setup_and_verify()` espera unos segundos de readiness,
5. ejecuta `smoke_check_with_retry()`,
6. resume errores de log si los hay.

Salida:

- `install` result,
- `launch` result,
- `smoke` result,
- `log_summary`.

Observacion importante:

el smoke actual considera OK cualquier respuesta HTTP entre 200 y 499. Eso detecta que hay algo escuchando, pero no significa salud funcional completa.

## Paso 18 - DECISION FINAL DE DONE O FAILED

La decision final pasa por `_can_reach_done(...)` dentro del orquestador.

El pipeline no marca `DONE` solo por haber generado archivos. Antes mira al menos:

- resultado de validacion,
- evidencia del `boot_report`,
- errores criticos del codigo generado.

Si quedan errores estructurales, el proyecto puede pasar a `FAILED`.

Si la evidencia es suficiente:

- se persiste el estado,
- se registra en lineage,
- se emite evento `DONE` hacia UI,
- y se ejecuta la fase de evolucion.

## Paso 19 - EVOLUTION Y MEMORIA

Fase `_phase_evolution()`.

Objetivo:

- capturar aprendizajes del proyecto terminado,
- actualizar el perfil o experiencia acumulada,
- enriquecer proyectos futuros.

Modulos implicados:

- `kernel/capabilities/profile_evolution.py`,
- `kernel/knowledge/chromadb_manager.py`,
- `kernel/learning/behavior_observer.py`,
- `kernel/learning/knowledge_base.py`,
- `kernel/learning/local_ai_coach.py`.

En otras palabras: SODA no solo genera. Tambien intenta aprender del resultado para las proximas corridas.

## Como Se Comunican Los Modulos

La comunicacion del sistema ocurre por cinco canales principales.

## 1. Llamadas Python directas

Es el canal principal.

Ejemplos:

- `ui/server.py` instancia `SodaOrchestrator`,
- `SodaOrchestrator` llama fases del `PhaseMixin`,
- las fases llaman validadores, generadores, runners y agentes especializados.

## 2. Construccion de prompts y respuestas de IA

`ContextBuilder` es el punto donde se arma el payload que va a cada modelo.

Toma como entradas:

- prompt base de `prompts/<provider>/<role>.md`,
- skills activas,
- perfil activo,
- contexto aprendido,
- memoria vectorial,
- contexto extra o few shot.

Devuelve un `BuiltContext` con:

- `system`,
- `user`,
- provider y role,
- skill y profile activos,
- fuentes de conocimiento usadas,
- estimacion de tokens.

Eso luego viaja a los drivers:

- `ClaudeDriver`,
- `GeminiDriver`,
- `OllamaDriver`,
- y `AIProviderHub` si hay routing o fallback.

## 3. Eventos UI por WebSocket

`ui/websocket_handler.py` mantiene una lista de conexiones activas.

El orquestador usa `_notify()` para emitir mensajes con esta forma:

- `event_type`,
- `message`,
- `data`.

Esos eventos se ven en tiempo real en la interfaz y sirven para seguir el pipeline sin bloquearlo.

## 4. Persistencia en disco

`ProjectManager` y el propio orquestador escriben el estado del proyecto en el workspace.

Archivos clave que va dejando el sistema:

- `metadata.json`,
- `blueprint.json`,
- `architecture.json`,
- `source/` con el codigo generado,
- `boot_report.json`,
- `_soda_launch.log`,
- reportes auxiliares de validacion y correccion.

## 5. Notificaciones externas

`TelegramGateway` envia eventos relevantes fuera de la app.

Se usa para:

- `START`,
- `DONE`,
- `FAILED`,
- checkpoints o eventos importantes.

## Mapa De Modulos Principales Y Su Funcion

La palabra modulo en SODA puede significar dos cosas:

- modulo de arquitectura del proyecto generado,
- o modulo interno del propio sistema SODA.

En este documento, el mapa siguiente se refiere a los modulos internos de SODA, agrupados por paquete.

| Paquete | Funcion principal | Se comunica sobre todo con |
| --- | --- | --- |
| `ui/` | API, UI, WebSocket y launcher | `kernel/orchestrator.py`, `ui/websocket_handler.py` |
| `kernel/orchestrator.py` | coordina el pipeline completo | casi todos los paquetes del kernel |
| `kernel/orchestration/` | implementa las fases reales del pipeline | `code_generator`, `validation`, `execution`, `design`, `vision` |
| `kernel/drivers/` | adaptadores hacia Claude, Gemini, Ollama y otros | `ContextBuilder`, `SodaOrchestrator`, `CodeGenerator` |
| `kernel/context/` | arma prompts con skills, perfil, RAG y memoria | `drivers`, `capabilities`, `knowledge` |
| `kernel/capabilities/` | elige skills, perfiles y capability packs | `context`, `intelligence`, `orchestrator` |
| `kernel/intelligence/` | interpreta metas, impacto, ambiguedades y salud del contexto | `orchestrator`, `lineage`, `communication` |
| `kernel/design/` | agrega direccion de UI y contexto de diseno | `phase_mixin`, `code_generator` |
| `kernel/goals/` | construye trazabilidad entre objetivos y archivos | `architecture`, `development`, `integrity` |
| `kernel/integrity/` | detecta codigo huerfano o desalineado | `goals`, `orchestrator`, `validation` |
| `kernel/validation/` | valida blueprint, arquitectura, imports y contratos | `phase_mixin`, `project_validator` |
| `kernel/testing/` | genera tests base | `phase_mixin`, `drivers` |
| `kernel/security/` | revisa riesgos del codigo | `phase_mixin`, `drivers` |
| `kernel/execution/` | instala, lanza, monitorea y hace smoke | `orchestrator`, `project_runner`, `boot_agent` |
| `kernel/project_validator.py` | build check y auto fix por rondas | `phase_mixin`, `drivers`, `architecture` |
| `kernel/knowledge/` | memoria vectorial y orquestacion de conocimiento | `requirements`, `evolution`, `context` |
| `kernel/learning/` | observacion y coaching local | `code_generator`, `evolution` |
| `kernel/lineage/` | historial, branching y cambios estructurales | `orchestrator`, `modify`, `refound` |
| `kernel/communication/` | Telegram y preguntas al usuario | `ui`, `orchestrator` |
| `kernel/monitoring/` | performance, uso y alertas | `ui`, `orchestrator`, `code_generator` |
| `kernel/vision/` | captura e inspeccion visual | `phase_mixin`, `execution` |
| `kernel/external/` | investigacion web y acciones externas | `ui`, `orchestrator` |
| `kernel/projects/` | gestion de metadata y ciclo de vida del workspace | `ui/server.py`, `orchestrator` |

## Como SODA Genera Aplicaciones En La Practica

La generacion real de aplicaciones se puede resumir asi:

1. el usuario describe la app,
2. SODA decide skills y perfil,
3. SODA detecta ambiguedades,
4. Claude genera un blueprint estructurado,
5. Gemini convierte el blueprint en arquitectura modular,
6. Python arma un DAG de ejecucion,
7. el sistema prepara contexto de diseno, skills, perfil y RAG,
8. `CodeGenerator` genera archivos modulo por modulo,
9. el codigo se revisa, valida, corrige y regenera si hace falta,
10. `BootAgent` intenta que el proyecto arranque de verdad,
11. `ProjectRunner` hace install, launch y smoke,
12. el orquestador decide si la evidencia alcanza para `DONE`.

Lo importante es esto: SODA no genera una aplicacion con un solo prompt monolitico. Genera artefactos intermedios que actuan como contratos entre fases.

Esos contratos son, sobre todo:

- `blueprint.json`,
- `architecture.json`,
- `ExecutionPlan`,
- `goal_tree`,
- archivos generados en `source/`,
- reportes de validacion y boot.

## Workspace Que Crea SODA Para Cada Proyecto

De forma simplificada, por cada proyecto SODA crea algo de este estilo:

```text
projects/<project_id>/
  metadata.json
  blueprint.json
  architecture.json
  goal_tree.json
  source/
    ...codigo generado...
  boot_report.json
  _soda_launch.log
  ...reportes adicionales...
```

`ProjectManager` es el responsable de crear, listar, cargar, guardar y borrar ese workspace.

## Flujos Secundarios Importantes

## Resume

`resume(project_id)` carga el metadata existente y retoma el pipeline desde el estado guardado.

## Import from code

`import_from_code(...)` salta Wisdom y Requirements clasicos, construye un blueprint desde el codigo existente y luego sigue con arquitectura, planning, development y validacion.

## Modify

`modify(project, request)` usa:

- `GoalInterpreter` para clasificar el cambio,
- `ImpactAnalyzer` para calcular impacto transitivo,
- `BranchManager` para ramificar si el cambio es estructural,
- y despues vuelve a ejecutar las fases necesarias.

## Refound

`refound(project)` resume el proyecto actual y vuelve a correr `run()` con una descripcion condensada.

## Zonas Del Sistema Que Requieren Precaucion

Estas son las areas que hoy conviene leer con cautela al mantener o extender el sistema:

- `_notify()` no debe volverse bloqueante porque conecta con UI y Telegram.
- `load_dotenv()` se carga explicitamente en entry points y no conviene simplificarlo sin revisar impacto.
- `DockerSandbox` existe, pero no hay que tratarlo como la prueba mas confiable del runtime.
- `ProjectValidator`, `BootAgent` y `ProjectRunner` se solapan en algunos tramos de install, boot y smoke.
- el smoke HTTP actual es util como senal de vida, pero no equivale a salud funcional completa.
- la continuidad del pipeline tolera ciertos fallos de entorno, por lo que `DONE` no significa siempre perfeccion operativa total.

## Resumen Ejecutivo Del Funcionamiento

Si hubiera que explicar SODA en una sola secuencia corta, seria esta:

1. entra un pedido por la UI,
2. el orquestador arma contexto y decide capacidades,
3. Claude convierte el pedido en blueprint,
4. Gemini lo convierte en arquitectura modular,
5. Python transforma eso en un DAG,
6. `CodeGenerator` genera el codigo por niveles y por modulo,
7. varias capas validan, corrigen y reintentan,
8. `BootAgent` y `ProjectRunner` intentan instalar y arrancar la app real,
9. el orquestador decide si el proyecto llega a `DONE`,
10. el sistema guarda artefactos, reportes y aprendizaje para la siguiente corrida.

Ese es el funcionamiento real de la aplicacion: una orquestacion determinista en Python que usa IA en puntos concretos, pero no delega todo el control a un solo modelo.