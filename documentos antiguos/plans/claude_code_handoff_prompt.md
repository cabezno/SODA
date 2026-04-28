PROMPT PARA CLAUDE CODE

Contexto
--------
Estás trabajando dentro del repo SODA-PROJECT.
Tu objetivo es implementar las correcciones del ciclo Copilot de forma incremental,
sin introducir regresiones y sin reabrir bugs que hoy ya parecen resueltos.

Antes de hacer cualquier cambio, lee completo el archivo:
- correcciones copilot.txt

No uses un diagnostico viejo como fuente de verdad. Tu fuente de verdad es:
1. el estado actual del repo,
2. la hoja correcciones copilot.txt,
3. los tests cercanos al cambio.

Contexto tecnico minimo del repo
--------------------------------
- El entry point principal sigue siendo SodaOrchestrator en kernel/orchestrator.py.
- Varias fases reales no viven ya solo en orchestrator.py: requirements, architecture,
  planning y validation viven en kernel/orchestration/phase_mixin.py.
- El consultor de Copilot esta en kernel/intelligence/copilot_consultant.py y hoy su
  contrato sigue siendo principalmente compatible con has_suggestion, message y changes.
- El orquestador sigue usando _copilot_suggest(...) como punto comun de evaluacion,
  pero Development tiene el loop mas fuerte del sistema.
- Ya existe red de seguridad en tests/test_unit.py para fallbacks async,
  rama non-software, override por fase y /api/config.

Restricciones obligatorias
--------------------------
- No tocar contenido de projects/.
- No editar .soda_backups/.
- No editar .webview_cache/.
- No reimplementar fixes viejos salvo que una validacion actual demuestre regresion real.
- No mezclar fix funcional, rediseño de contrato y limpieza de providers/config en un mismo slice.
- No abrir un segundo frente si el slice actual todavia no quedo verde.

Precauciones criticas
---------------------
1. Si el cambio afecta requirements, architecture, planning o validation, revisa tanto
   kernel/orchestrator.py como kernel/orchestration/phase_mixin.py antes de editar.
2. Si cambias la salida de CopilotConsultant, manten compatibilidad hacia atras.
3. Si tocas validation, no corrijas solo run() o solo resume(): ambos deben quedar alineados.
4. No uses Development como primer lugar de experimentacion del contrato enriquecido.
5. No tomes el repo sucio como señal de fallo del slice; valida por archivo, test cercano y comportamiento.

Protocolo de trabajo obligatorio
--------------------------------
1. Lee el archivo objetivo y el test mas cercano.
2. Formula una hipotesis local falsable.
3. Elige la validacion minima que puede romper esa hipotesis.
4. Haz el cambio mas pequeno posible.
5. Ejecuta primero la validacion minima del slice.
6. Si pasa, ejecuta la regresion relacionada del subsistema.
7. Si falla, corrige ese mismo slice antes de seguir.

Orden de implementacion
-----------------------
Sigue el orden de correcciones copilot.txt.
No saltes directamente a Development ni a providers/config.

Primer slice que debes ejecutar
-------------------------------
Empieza por FASE 1: alinear validation entre run() y resume().

Superficie probable del cambio inicial
--------------------------------------
- kernel/orchestrator.py
- kernel/orchestration/phase_mixin.py
- tests/test_unit.py o tests/test_pipeline.py

Puntos a revisar primero
------------------------
- run()
- resume()
- review_validation(...)
- _should_regenerate_after_validation(...)
- _phase_targeted_regeneration(...)

Objetivo del primer slice
-------------------------
Hacer que la decision post-validation deje de depender de si el flujo vino de run() o de resume().
No abras todavia el rediseño completo del contrato Copilot en ese mismo cambio.

Validacion esperada para el primer slice
----------------------------------------
- Primero un test o regresion puntual que compruebe que run() y resume() pasan por la misma decision
  cuando validation encuentra errores.
- Despues una regresion del subsistema afectado.
- Solo despues, si hace falta, una corrida mas amplia.

Fases posteriores
-----------------
Cuando FASE 1 quede verde, continua asi:
1. Ampliar el contrato estructurado de Copilot en kernel/intelligence/copilot_consultant.py,
   manteniendo compatibilidad hacia atras.
2. Crear un manejador comun de reviews Copilot compartido entre orchestrator.py y phase_mixin.py.
3. Integrar primero en Requirements y Validation.
4. Integrar despues en Architecture y Planning.
5. Ajustar Development al final.
6. Revisar providers/config solo si siguen teniendo comportamiento decorativo real.

Tests base a conservar
----------------------
- TestSkillMatcherAsyncFallback
- TestProfileMatcherAsyncFallback
- TestNonSoftwarePipelineSkillContext
- TestNoDuplicateApiConfigRoutes
- TestAIPhaseProviderSelection

Definicion de verde
-------------------
Un slice queda verde solo si:
1. no introduce errores nuevos,
2. pasa el test mas cercano,
3. la regresion relevante del subsistema sigue pasando.

Formato de entrega esperado
---------------------------
Al cerrar cada slice, informa:
1. que archivos tocaste,
2. que bug concreto resolviste,
3. que test corriste,
4. si el slice quedo verde o no.

Regla final
-----------
No optimices por amplitud. Optimiza por seguridad, trazabilidad y validacion.
Haz primero el cambio minimo que deje evidencia ejecutable de que no rompiste el codigo.