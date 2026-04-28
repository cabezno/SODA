# Hoja De Ruta: Validacion, Instalacion Y Arranque

## Objetivo

Corregir el tramo final del pipeline donde hoy se mezclan validacion estatica,
instalacion de dependencias, arranque del proyecto y smoke checks, sin convertir
errores de entorno en falsos bloqueos ni romper el cierre actual del pipeline.

## Estado Actual Del Repo

- `_phase_validation` en `kernel/orchestration/phase_mixin.py` delega en
  `kernel/project_validator.py`.
- `ProjectValidator` instala dependencias y corre un check de build o compilacion
  segun stack.
- `_validate_and_maybe_regen` en `kernel/orchestrator.py` ya existe y puede disparar
  regeneracion dirigida si los errores quedan concentrados por modulo.
- El orquestador ya no cierra siempre en `DONE`: `run()` y `resume()` usan
  `_can_reach_done(...)`, pero ese guard aun es conservador y solo mira ciertos
  patrones estructurales de error.
- `BootAgent` intenta instalar, arrancar, capturar logs y corregir con IA.
- `ProjectRunner` vuelve a instalar, lanzar y hacer smoke HTTP.
- `DockerSandbox` existe, pero hoy no debe asumirse como prueba fuerte de ejecucion
  real del proyecto.

## Problema Real A Corregir

No es que SODA no mire nada. Mira muchas cosas, pero las mira desde varias capas
distintas y no todas tienen autoridad para bloquear `DONE`.

Hoy el riesgo principal es este:

- un mismo fallo de dependencias puede aparecer en `ProjectValidator`, `BootAgent` y
  `ProjectRunner`;
- el smoke HTTP puede avisar fallo pero no necesariamente bloquear el pipeline;
- `DockerSandbox` puede dar una falsa sensacion de cobertura;
- el criterio de cierre mezcla errores del codigo generado con problemas del entorno.

## Principio Rector

Primero separar evidencia de ejecucion real de evidencia estatica.
Despues definir que tipos de error bloquean `DONE`.
Recien al final endurecer el cierre del pipeline.

## Regla De Seguridad Critica

No endurecer `DONE` antes de clasificar los errores.
Si se hace al reves, se van a bloquear proyectos validos por:

- Docker no disponible,
- dependencias externas no presentes en el host,
- servicios o API keys ausentes,
- stacks donde el smoke HTTP no es la senal correcta.

## Fase R0 - Baseline De Observabilidad

### Objetivo

Confirmar exactamente que capa detecta cada fallo sin cambiar aun el comportamiento.

### Archivos A Revisar Primero

- `kernel/orchestration/phase_mixin.py`
- `kernel/project_validator.py`
- `kernel/execution/boot_agent.py`
- `kernel/execution/project_runner.py`
- `kernel/orchestrator.py`

### Cambios Permitidos En Esta Fase

- Solo mejoras de trazabilidad y reportes.
- No cambiar el criterio de `DONE`.
- No cambiar el timeout critico de `_notify()`.

### Resultado Esperado

Cada intento debe dejar claro:

1. si fallo install,
2. si fallo build/check,
3. si fallo boot,
4. si fallo smoke,
5. en que capa se detecto.

### Validacion Minima Inmediata

- Extender tests cercanos para asegurar que los reportes incluyen `phase`, `reason` y origen.

### Condicion De Cierre

- Ya no hay que inferir a ojo si un fallo vino de `ProjectValidator`, `BootAgent` o `ProjectRunner`.

## Fase R1 - Definir Taxonomia De Errores

### Objetivo

Separar errores bloqueantes del codigo generado de errores tolerables del entorno.

### Salida Esperada

Crear una clasificacion pequena y explicita, por ejemplo:

- `BLOQUEANTES DEL CODIGO`
  - `SyntaxError`
  - `IndentationError`
  - `NameError`
  - `ImportError` sobre simbolos internos del proyecto
  - errores de compilacion que prueban codigo roto del repo generado

- `TOLERABLES DEL ENTORNO`
  - Docker no disponible
  - comando no encontrado en host
  - dependencias opcionales o externas ausentes
  - API keys no configuradas
  - servicios remotos no accesibles
  - smoke HTTP no aplicable al stack

- `ADVISORY RUNTIME`
  - la app arranca pero responde `404` o `500` en un probe inicial
  - warnings de startup sin crash

### Regla De Esta Fase

No cambiar aun `_can_reach_done()`.
Primero escribir tests de decision con fixtures pequenos de errores.

### Condicion De Cierre

- Existe una tabla de decision verificable para "bloquea `DONE`" versus "solo advierte".

## Fase R2 - Hacer De `_can_reach_done()` Una Decision Explicita Y Testeada

### Objetivo

Reemplazar el guard actual por una decision basada en la taxonomia definida.

### Archivo Objetivo

- `kernel/orchestrator.py`
- `tests/test_unit.py`

### Cambios Esperados

- Mantener la firma pequena y local.
- Basar la decision en clasificacion, no solo en substrings sueltos.
- Seguir permitiendo `skipped` cuando el problema es del entorno.

### Orden Correcto

1. tests de decision,
2. helper de clasificacion,
3. adaptacion de `_can_reach_done()`,
4. rerun de tests cercanos.

### Condicion De Cierre

- `DONE` solo se alcanza cuando:
  - `validation_result.fixed` es `True`, o
  - el fallo restante es tolerable segun la clasificacion.

## Fase R3 - Eliminar Doble O Triple Responsabilidad Sin Cambiar Aun El Resultado Final

### Objetivo

Reducir chequeos redundantes para que cada capa tenga una responsabilidad clara.

### Distribucion Recomendada

- `ProjectValidator`
  - fuente de verdad para `install + build/check` estatico.

- `BootAgent`
  - fuente de verdad para `install + boot + captura de errores de arranque + fix loop`.

- `ProjectRunner`
  - fuente de verdad para `launch final + smoke HTTP + smoke suite`.

### Regla De Esta Fase

No borrar una capa completa en el primer cambio.
Primero marcar una como autoritativa y convertir las otras en advisory donde corresponda.

### Slice Sugerido

- Evitar que `ProjectRunner` vuelva a instalar si `BootAgent` ya dejo evidencia valida
  de install para ese intento.
- Evitar que el orquestador interprete tres veces el mismo fallo como tres problemas distintos.

### Condicion De Cierre

- install, boot y smoke ya no aparecen duplicados como si fueran fallos independientes.

## Fase R4 - Endurecer El Smoke Para Que La Senal Sea Util

### Objetivo

Hacer que el smoke represente mejor "la app esta viva" sin romper stacks no HTTP.

### Problema Actual

- El smoke de `ProjectRunner` acepta cualquier HTTP entre `200` y `499`.
- Eso sirve para detectar que hay algo escuchando, pero no prueba salud funcional.

### Estrategia Segura

- No volver el smoke mas estricto para todos los stacks de una vez.
- Introducir primero un modo por stack o por tipo de proyecto.
- Mantener "probe basico" como fallback.

### Orden Recomendado

1. agregar metadata de probe esperada,
2. soportar excepciones por stack,
3. endurecer solo donde haya evidencia clara de endpoint raiz esperable.

### Condicion De Cierre

- El smoke deja de ser enganoso sin pasar a ser una fuente masiva de falsos negativos.

## Fase R5 - Tratar Docker Sandbox Como Advisory Hasta Que Sea Confiable

### Objetivo

Evitar que una capa incompleta se perciba como validacion fuerte.

### Regla De Esta Fase

- Si `DockerSandbox` no ejecuta realmente el test suite esperado, no usarlo como criterio
  de bloqueo ni como evidencia principal de calidad.
- Mientras tanto, degradarlo a chequeo advisory y dejarlo claro en logs y reportes.

### Dos Opciones Validas

- Opcion A: dejarlo explicitamente como advisory hasta completarlo.
- Opcion B: completarlo de verdad y recien entonces promoverlo en el pipeline.

### Condicion De Cierre

- Docker deja de vender una garantia que hoy no puede sostener.

## Fase R6 - Cierre Final Del Pipeline Basado En Evidencia Minima Suficiente

### Objetivo

Definir la condicion final de exito del tramo runtime.

### Propuesta De Cierre Seguro

Marcar `DONE` solo si se cumple esta evidencia minima:

1. Validation no deja errores bloqueantes del codigo generado.
2. BootAgent no reporta crash estructural del arranque.
3. El smoke aplicable al stack pasa, o el stack esta explicitamente marcado como no HTTP.

### Marcar FAILED O Estado Equivalente Si

- hay error bloqueante del codigo,
- el arranque rompe de forma estructural,
- o el smoke obligatorio del stack falla de forma persistente.

### Mantener HEALTH_WARN Si

- el problema es de entorno,
- el proyecto requiere configuracion externa,
- o la verificacion disponible no alcanza para una conclusion mas fuerte.

### Condicion De Cierre

- El `DONE` final deja de ser "compilo algo" y pasa a significar "hay evidencia minima suficiente de que el proyecto generado es ejecutable".

## Tests Minimos Recomendados Para Esta Hoja

### 1. Tests De Clasificacion

- errores estructurales del codigo bloquean `DONE`.
- errores de entorno no bloquean `DONE`.

### 2. Tests De Decision Final

- `run()` no marca `DONE` cuando `_can_reach_done()` devuelve `False`.
- `resume()` mantiene el mismo criterio.
- `import_from_code()` no queda desalineado.

### 3. Tests De Smoke

- un stack HTTP con `connection_error` queda en warning o fail segun clasificacion.
- un stack no HTTP no se penaliza por no tener probe HTTP valido.

### 4. Tests De No Regresion

- la validacion comun sigue pasando.
- no se rompe el loop de targeted regeneration.
- no se toca el timeout critico de `_notify()`.

## Orden Exacto De Implementacion

### Paso R1

Baseline de observabilidad del tramo `validation -> boot -> smoke`.

### Paso R2

Definir taxonomia de errores con tests pequenos.

### Paso R3

Adaptar `_can_reach_done()` para usar esa taxonomia.

### Paso R4

Reducir duplicacion de responsabilidades entre `ProjectValidator`, `BootAgent` y `ProjectRunner`.

### Paso R5

Mejorar el smoke solo donde el stack lo soporte.

### Paso R6

Degradar `DockerSandbox` a advisory o completarlo de verdad.

### Paso R7

Recien entonces endurecer el cierre final a `DONE` o `FAILED` segun evidencia minima suficiente.

## Criterio Final De Aceptacion

Esta correccion se considera bien hecha solo si:

- ya no hay ambiguedad sobre donde fallo install, build, boot o smoke,
- los errores del entorno no bloquean proyectos validos,
- los errores estructurales del codigo si bloquean `DONE`,
- el runtime smoke deja de ser ornamental,
- `DockerSandbox` deja de ser una senal enganosa,
- `run()`, `resume()` e `import_from_code()` cierran con el mismo criterio,
- y los tests cercanos siguen verdes despues de cada slice.