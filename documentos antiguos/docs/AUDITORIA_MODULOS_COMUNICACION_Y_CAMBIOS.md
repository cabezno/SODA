# Auditoria De Modulos, Comunicacion Y Cambios Seguros

## Alcance

Esta auditoria cubre el funcionamiento interno de SODA como aplicacion, con foco en:

- como se comunican sus modulos,
- si esa comunicacion es efectiva,
- que funciones y skills estan disponibles hoy,
- y que cambios conviene hacer sin romper el codigo existente.

No se audita el contenido de proyectos generados dentro de la carpeta projects, sino la aplicacion que los crea, valida y opera.

## Resumen Ejecutivo

El sistema tiene una arquitectura centralizada y entendible:

- la entrada principal es la UI y API en ui/server.py,
- el control real del pipeline vive en kernel/orchestrator.py,
- la ejecucion de fases vive en kernel/orchestration/phase_mixin.py,
- la generacion de codigo se apoya en ContextBuilder, DependencyGraph y CodeGenerator,
- la persistencia del proyecto se guarda en projects/<id>/,
- y la observabilidad viaja por WebSocket y Telegram.

La comunicacion entre capas es funcional en el camino principal run -> phases -> notify -> UI, pero no es homogénea en todos los entry points. El pipeline principal esta razonablemente coordinado; las rutas alternativas y de proyecto externo son hoy el punto mas fragil.

## Hallazgos Prioritarios

## Criticos

### 1. El sistema puede marcar FAILED internamente y aun asi emitir DONE hacia la UI

Impacto:

- la UI y cualquier consumidor externo pueden interpretar exito donde el estado guardado del proyecto ya es FAILED,
- eso rompe el contrato de comunicacion mas importante del sistema: el estado final.

Evidencia:

- en kernel/orchestrator.py, dentro de run(), primero se decide entre DONE o FAILED con _can_reach_done(), pero despues igualmente se emite un evento DONE al final del flujo,
- en resume() pasa el mismo patron: puede dejar project.state en FAILED y aun asi emitir "Pipeline reanudado y completado" como DONE.

Consecuencia:

- la comunicacion orquestador -> UI no es confiable en el cierre final.

### 2. La ruta de proyecto externo open_project/run esta rota por contrato

Impacto:

- una de las superficies publicas del servidor puede fallar antes de ejecutar el flujo real,
- y aunque superara ese punto, intenta llamar fases que no existen.

Evidencia:

- ui/server.py instancia SodaOrchestrator con notify_fn, pero la firma publica del constructor en kernel/orchestrator.py solo acepta copilot_temperature,
- open_and_process() llama _phase_arch(), _phase_plan() y _phase_dev(), pero esas funciones no existen en kernel/orchestrator.py ni en kernel/orchestration/phase_mixin.py.

Consecuencia:

- la comunicacion UI -> orchestrator para proyectos externos no es efectiva; es una superficie inconsistente o directamente rota.

## Altos

### 3. Hay una ventana de carrera real con _pipeline_running

Impacto:

- dos requests concurrentes pueden pasar el check de "pipeline ocupado" antes de que el flag se marque,
- eso puede disparar ejecuciones simultaneas no deseadas.

Evidencia:

- en rutas como /api/run, /api/run_from_code y /api/open_project/run el check se hace antes de crear una tarea async,
- pero _pipeline_running se setea dentro de la coroutine _run(), no antes de programarla.

Consecuencia:

- la comunicacion entre el servidor HTTP y el lifecycle del pipeline no es atomica.

### 4. Los entry points no comparten exactamente el mismo criterio de cierre runtime

Impacto:

- distintos caminos de entrada pueden declarar exito con distinta evidencia,
- eso hace que el significado de DONE cambie segun la ruta usada.

Evidencia:

- run() usa _can_reach_done(validation_result, boot_report),
- resume() usa _can_reach_done(validation_result) sin volver a evaluar boot_report,
- import_from_code() decide estado antes de setup_and_verify(),
- open_and_process() en action run_and_test marca DONE despues de _phase_validation() sin un cierre runtime equivalente.

Consecuencia:

- la comunicacion entre validacion, arranque y cierre final sigue desalineada fuera del flujo principal.

## Medios

### 5. Validacion, BootAgent y ProjectRunner siguen solapando responsabilidades

Impacto:

- el mismo fallo puede aparecer como install, build, boot o smoke en distintas capas,
- la explicacion del error se vuelve mas dificil para la UI y para el usuario.

Estado actual:

- hay una mejora puntual: _phase_setup_and_verify() ya intenta reutilizar la instalacion de BootAgent,
- aun asi ProjectValidator, BootAgent y ProjectRunner siguen tocando install, chequeo y runtime.

Consecuencia:

- la comunicacion entre capas es parcialmente efectiva, pero todavia no tiene una sola fuente de verdad por etapa.

### 6. ui/server.py concentra demasiadas responsabilidades en un solo archivo

Impacto:

- cuesta validar contratos y side effects,
- es mas facil que aparezcan entry points desalineados,
- bajar bugs de comunicacion a pruebas unitarias se vuelve mas costoso.

Estado actual:

- server.py mezcla API publica, arranque de pipeline, bridge Telegram, CopilotKit, runtime launch, chat, research, tools, env, config, vision y terminales.

Consecuencia:

- la arquitectura funciona, pero la comunicacion se vuelve fragile por exceso de acoplamiento en el borde HTTP.

## Evaluacion De La Comunicacion Entre Modulos

| Canal | Estado | Evaluacion |
| --- | --- | --- |
| UI -> server.py | Efectivo | La aplicacion entra bien por HTTP y WebSocket y expone una superficie muy rica. |
| server.py -> SodaOrchestrator | Parcialmente efectivo | El camino principal funciona, pero rutas alternativas tienen contratos rotos o desalineados. |
| Orchestrator -> PhaseMixin | Efectivo | La separacion de fases es clara y legible. |
| PhaseMixin -> Validators / Execution | Parcialmente efectivo | Hay buen encadenamiento, pero se pisan responsabilidades entre validacion, boot y runtime. |
| Orchestrator -> UI via _notify | Efectivo con una falla critica | El bus de eventos esta bien normalizado con event_type, pero el evento final puede mentir sobre el estado real. |
| Orchestrator -> Telegram | Efectivo | El gateway esta desacoplado y usa envio asincronico con cola rate-limited. |
| ContextBuilder -> Drivers IA | Efectivo | La construccion de contexto esta centralizada y soporta skills, profiles, RAG y few-shot. |
| Architecture -> Planning -> Code generation | Efectivo | El flujo blueprint -> architecture -> DAG -> code esta bien definido. |
| Persistence -> Resume / Modify | Parcialmente efectivo | Metadata y lineage funcionan, pero el criterio final de cierre no esta unificado en todas las rutas. |

## Como Funciona El Sistema, En Detalle

## 1. Entrada Y Control

La aplicacion entra por ui/server.py.

Ese archivo hace de borde de sistema y concentra:

- endpoints REST,
- WebSocket principal,
- websocket de terminal,
- acciones CopilotKit,
- config de IA,
- integracion Telegram,
- apertura de proyectos existentes,
- runtime launch y autofix,
- research y vision.

El control de negocio real no vive ahi. Vive en SodaOrchestrator.

## 2. Orquestacion

kernel/orchestrator.py es el centro del sistema.

Sus responsabilidades principales son:

- crear el proyecto y su workspace,
- inicializar drivers y servicios del kernel,
- decidir que fases corren,
- construir y enviar eventos a UI y Telegram,
- persistir estado,
- y decidir si el proyecto llega a DONE o FAILED.

Es una arquitectura de coordinador fuerte: casi todos los submodulos se conectan a traves del orquestador.

## 3. Fases Reales Del Pipeline

La implementacion concreta de las fases esta en kernel/orchestration/phase_mixin.py.

Fases principales disponibles:

- _phase_capabilities
- _phase_wisdom
- _phase_requirements
- _phase_architecture
- _phase_planning
- _phase_design
- _phase_development
- _phase_verify
- _phase_import_validation
- _phase_security_review
- _phase_test_generation
- _phase_api_contract
- _phase_audit
- _phase_validation
- _phase_boot_agent
- _phase_setup_and_verify
- _phase_visual_inspection
- _phase_docs
- _phase_evolution
- _phase_iteration
- _phase_feedback_loop
- _phase_targeted_regeneration
- _phase_master_contract

La comunicacion orquestador -> fases esta bien resuelta. El problema no esta ahi, sino en como algunos entry points laterales reutilizan o evitan ese camino.

## 4. Requerimientos Y Arquitectura

El flujo conceptual principal es:

- CAPABILITIES: skills, profile y capability packs,
- WISDOM: aclaracion de ambiguedades,
- REQUIREMENTS: genera blueprint.json,
- ARCHITECTURE: genera architecture.json,
- PLANNING: arma ExecutionPlan topologico.

Esto esta bien diseñado porque cada fase produce un artefacto intermedio que la siguiente consume.

El pipeline no salta directamente de idea a codigo. Primero arma contratos.

## 5. Generacion De Codigo

La generacion se apoya sobre tres piezas:

- ContextBuilder para armar prompts ricos,
- DependencyGraph para ordenar modulos,
- CodeGenerator para escribir archivos.

CodeGenerator es eficaz por tres razones:

- genera por modulo y por archivo, no de forma monolitica,
- inyecta codigo ya generado de dependencias para mantener consistencia,
- y usa escalamiento de modelos en lugar de depender de un solo proveedor.

## 6. Validacion Y Runtime

Despues de generar, el sistema pasa por varias capas:

- ProjectValidator para setup y build check,
- BootAgent para instalar y arrancar con fix loop,
- ProjectRunner para install, launch, smoke y logs,
- DockerSandbox como chequeo advisory,
- VisualInspector para surfaces visuales.

Esta parte es la mas poderosa del sistema, pero tambien la que mas necesita limpieza de responsabilidades.

## 7. Persistencia, Lineage Y Evolucion

ProjectManager administra el workspace del proyecto.

Lineage y BranchManager cubren:

- historial de proyectos,
- branching en cambios estructurales,
- y trazabilidad de evolución.

KnowledgeOrchestrator, ProfileEvolution y los modulos de learning permiten que el sistema acumule experiencia y contexto reutilizable.

## Mapa De Modulos Y Comunicacion

| Area | Funcion | Comunicacion principal | Evaluacion |
| --- | --- | --- | --- |
| ui | borde HTTP, WebSocket y desktop | llama al orquestador y emite eventos | Buena, pero demasiado concentrada |
| orchestrator | coordinador central | llama fases, drivers, runtime y persistencia | Buena en el camino principal |
| orchestration | implementacion de fases | organiza el pipeline real | Buena |
| context | armado de prompts | alimenta drivers y generadores | Buena |
| drivers | acceso a IA | reciben payloads del context builder | Buena |
| capabilities | match de skills y profiles | alimenta contexto y diseño | Buena |
| intelligence | interpretacion, impacto, referencias y salud | apoya decisiones del orquestador | Buena |
| design | direccion visual y UI hints | apoya desarrollo | Correcta |
| dependency_graph | orden topologico de modulos | puente entre arquitectura y desarrollo | Muy buena |
| code_generator | genera archivos | consume arquitectura, contexto y dependencias | Muy buena |
| validation | valida blueprint, architecture, imports, contratos | puentea dev y runtime | Parcial por solapamientos |
| execution | install, boot, smoke, logs y autofix | puente entre codigo generado y evidencia runtime | Parcial por duplicacion |
| communication | Telegram y preguntas al usuario | canal externo y de interacción | Buena |
| projects | metadata y lifecycle del workspace | persistencia base | Buena |
| lineage | historial y ramas | ligado a modify y refound | Buena |
| knowledge / learning | RAG y evolucion de perfiles | realimenta futuras corridas | Correcta |
| monitoring | perf, uso y alertas | soporte transversal | Correcta |
| vision | captura e inspeccion visual | soporte de calidad de UI | Correcta |
| external | research, system actions y tools | soporte de integraciones | Correcta |

## Funciones Disponibles Hoy

## 1. Acciones CopilotKit

Disponibles en ui/server.py:

- create_project
- resume_project

## 2. Funciones Principales Del Orquestador

Disponibles en kernel/orchestrator.py:

- run
- resume
- import_from_code
- modify
- refound
- open_and_process

## 3. Endpoints HTTP Y WebSocket Principales

### Pipeline y proyectos

- GET /
- GET /copilot
- POST /api/run
- GET /api/status
- POST /api/modify
- GET /api/lineage
- GET /api/lineage/{project_id}/branches
- POST /api/refound
- POST /api/analyze_code
- POST /api/run_from_code
- GET /api/project/{project_id}
- GET /api/projects/{project_id}/files
- GET /api/projects/{project_id}/goal_tree
- GET /api/projects/{project_id}/runtime_health
- GET /api/projects/{project_id}/runtime_smoke

### Runtime, procesos y correccion

- POST /api/launch
- GET /api/processes
- POST /api/kill/{project_id}
- GET /api/execution_errors
- GET /api/execution_errors/{project_id}
- POST /api/autofix
- GET /api/execution_precedents/{stack}

### Proyecto abierto desde disco

- GET /api/open_project/browse
- POST /api/open_project/analyze
- POST /api/open_project/run
- GET /api/open_project/migration_targets

### IA, configuracion y entorno

- GET /api/health
- GET /api/ai/status
- GET /api/ai/test/{provider}
- GET /api/config
- POST /api/config
- GET /api/env
- POST /api/env
- GET /api/ai/providers
- POST /api/ai/providers
- GET /api/ai/known-providers
- GET /api/ai/test-custom/{name}
- GET /api/tokens

### Interaccion, chat y soporte

- GET /api/telegram/pair
- GET /api/telegram/status
- POST /api/answer
- POST /api/answer/extend
- GET /api/question
- POST /api/chat
- POST /api/open_in_editor

### Research, referencias y vision

- POST /api/research
- POST /api/references/analyze
- POST /api/vision/capture
- POST /api/vision/inspect
- POST /api/intensity
- POST /api/system/action
- GET /api/tools/registry
- GET /api/tools/registry/{tool_key}
- GET /api/capability_packs
- GET /api/capability_packs/{pack_key}
- GET /api/project_types
- GET /api/project_types/{project_type_key}

### Monitoreo y observabilidad

- GET /api/stats
- GET /api/ram_total
- GET /api/usage/summary
- GET /api/usage/recent
- GET /api/alerts

### WebSockets

- GET /ws
- GET /ws/terminal/{session_id}

## 4. Comandos Telegram Disponibles

Disponibles en kernel/communication/telegram_gateway.py:

- /start
- /pair
- /status
- /projects
- /crear
- /abrir
- /aprobar
- /rechazar
- /cancel
- /fin
- /terminar
- /mas_tiempo

## 5. Skills Base Disponibles

Skills encontrados en skills/base:

- skill_android_kotlin
- skill_angular
- skill_anthropic
- skill_cpp_cmake
- skill_csharp_dotnet
- skill_electron
- skill_fastapi
- skill_finance
- skill_flutter
- skill_golang
- skill_java_spring
- skill_jwt_auth
- skill_langchain
- skill_legal
- skill_marketing
- skill_mongodb
- skill_nestjs
- skill_nextjs
- skill_nodejs
- skill_openai
- skill_php_laravel
- skill_postgresql
- skill_react
- skill_react_native
- skill_rest_api
- skill_rust
- skill_sqlite
- skill_typescript
- skill_ui_design
- skill_ux
- skill_vue

Estado actual:

- skills/custom esta vacio,
- no hay skills custom activas hoy.

## 6. Profiles Base Disponibles

Profiles encontrados en profiles/base:

- profile_backend_api
- profile_dotnet_dev
- profile_frontend_dev
- profile_fullstack_js
- profile_general_dev
- profile_java_dev
- profile_web_fullstack

## 7. Capability Packs Disponibles

Disponibles en kernel/capabilities/capability_packs.py:

- auth_complete
- payment_processing
- email_notifications

## 8. Project Types Disponibles

Disponibles en kernel/projects/project_types.py:

- software
- analysis
- marketing
- finance

## 9. External Tools Registrados

Disponibles en kernel/external/tool_registry.py:

- google_calendar
- github
- telegram_bot

## 10. Como Se Cargan Las Skills

SkillMatcher hace esto:

- recorre skills/*/*/manifest.yaml,
- construye un resumen de skills disponibles,
- le pide a Gemini la seleccion,
- hace fallback por keywords si la IA falla,
- y luego SkillManager carga el contexto real de cada skill segun role y load_level.

Esto esta bien resuelto y es una parte efectiva del sistema.

## Todo Lo Que Cambiaria Y Como Lo Cambiaria Sin Romper El Codigo

## Cambio 1 - Arreglar el contrato final de estado y eventos

Que cambiaria:

- unificaria la emision final de eventos DONE, FAILED y HEALTH_WARN para que salgan de una sola funcion,
- prohibiria emitir DONE si project.state ya quedo en FAILED.

Como lo haria sin romper:

1. crear un helper local de cierre final en kernel/orchestrator.py,
2. hacer que run, resume, import_from_code y open_and_process usen ese helper,
3. escribir tests de regresion para asegurar que FAILED nunca emite DONE.

Beneficio:

- la comunicacion UI y Telegram vuelve a ser confiable.

## Cambio 2 - Corregir la ruta open_project/run sin tocar el camino principal

Que cambiaria:

- eliminaria el notify_fn inexistente al construir SodaOrchestrator,
- reemplazaria _phase_arch, _phase_plan y _phase_dev por _phase_architecture, _phase_planning y _phase_development,
- y haria que open_and_process reutilice _validate_and_maybe_regen y el mismo criterio de cierre que run.

Como lo haria sin romper:

1. corregir solo esa ruta y su metodo asociado,
2. agregar pruebas de smoke de endpoint para open_project/run,
3. no tocar la firma publica de run ni de resume.

Beneficio:

- se recupera una superficie publica hoy inconsistente sin mover el core del pipeline.

## Cambio 3 - Hacer atomico el lock de pipeline

Que cambiaria:

- moveria la adquisicion del estado ocupado antes de crear la tarea async,
- idealmente con un helper o lock asincronico central en server.py.

Como lo haria sin romper:

1. introducir un wrapper pequeño de lanzamiento seguro,
2. migrar primero /api/run, /api/run_from_code y /api/open_project/run,
3. luego el resto de rutas mutantes que compartan el mismo lifecycle.

Beneficio:

- se evita doble ejecucion concurrente con un cambio local en el borde HTTP.

## Cambio 4 - Unificar el criterio DONE entre todas las entradas

Que cambiaria:

- haria que run, resume, import_from_code y open_and_process pasen por la misma combinacion:
  validation_result + boot_report + setup_result.

Como lo haria sin romper:

1. no cambiar _can_reach_done de golpe,
2. extraer un helper que recolecte siempre la misma evidencia minima,
3. migrar cada entry point uno por uno con tests cercanos.

Beneficio:

- DONE deja de significar cosas distintas segun la ruta.

## Cambio 5 - Separar autoridad entre ProjectValidator, BootAgent y ProjectRunner

Que cambiaria:

- ProjectValidator seria la fuente de verdad para install y build check estatico,
- BootAgent seria la fuente de verdad para arranque y fix loop de boot,
- ProjectRunner quedaria como verificacion final de launch, smoke y logs.

Como lo haria sin romper:

1. mantener comportamiento actual pero marcar en reportes que capa es autoritativa,
2. desactivar reinstalaciones redundantes una por una,
3. consolidar primero logging y reportes antes de endurecer decisiones.

Beneficio:

- los errores dejan de verse triplicados y mejora la trazabilidad.

## Cambio 6 - Partir ui/server.py por dominios, sin cambiar la API publica

Que cambiaria:

- separaria server.py en routers o modulos por dominio:
  pipeline, runtime, ai_config, communication, research, vision, project_management.

Como lo haria sin romper:

1. mantener exactamente las mismas rutas,
2. mover solo implementacion, no contratos externos,
3. introducir pruebas de endpoint por grupo antes de mover el siguiente bloque.

Beneficio:

- baja el acoplamiento en la capa HTTP sin afectar a la UI.

## Cambio 7 - Endurecer pruebas de entry points, no solo del core

Que cambiaria:

- agregaria tests para:
  run,
  resume,
  import_from_code,
  open_and_process,
  cierre final de estado,
  y lock de concurrencia.

Como lo haria sin romper:

1. primero testear el comportamiento actual en run y resume,
2. despues agregar casos que fallen hoy en open_project/run,
3. recien despues cambiar codigo productivo.

Beneficio:

- se reduce mucho el riesgo de corregir una ruta y romper otra.

## Orden Seguro De Implementacion

Si tuviera que corregir esto sin romper el sistema, lo haria en este orden:

1. tests del estado final y eventos,
2. fix del lock _pipeline_running,
3. fix de open_project/run y open_and_process,
4. unificacion del cierre final en todos los entry points,
5. clarificacion de autoridad entre validation, BootAgent y ProjectRunner,
6. refactor interno de server.py por dominios,
7. endurecimiento progresivo del smoke y del criterio DONE.

## Veredicto Final

La arquitectura general de SODA es buena y el flujo principal esta bien pensado.

Lo mejor del sistema hoy es:

- la orquestacion por fases,
- la separacion blueprint -> architecture -> planning -> development,
- la integracion de skills y perfiles,
- el ContextBuilder,
- el CodeGenerator con dependencia contextual,
- y la observabilidad por WebSocket y Telegram.

Lo que mas necesita correccion no es la idea general, sino la consistencia de comunicacion entre entry points y el cierre final del pipeline.

Dicho de otra forma:

- el core principal es solido,
- la comunicacion interna es mayormente efectiva,
- pero hay rutas secundarias y contratos finales que hoy pueden mentir o romperse.

La prioridad no deberia ser reescribir el sistema, sino consolidar los contratos de estado, runtime y entrada publica sin tocar el corazon de generacion.