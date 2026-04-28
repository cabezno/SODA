# Plan de Auditoría Profunda: SODA Project

Este documento establece un plan estructurado para analizar sistemáticamente el proyecto SODA. Debido a la gran envergadura de la aplicación, la auditoría se dividirá en **Fases** temáticas, agrupando módulos interrelacionados para mantener el contexto.

## Metodología de Auditoría por Módulo
Para cada módulo, se evaluarán los siguientes 4 pilares:
1. **Control de Errores (Error Handling):** Manejo seguro de excepciones, fallos de APIs externas, y recuperación de caídas (graceful degradation).
2. **Redundancias (DRY):** Detección de código repetido, funciones duplicadas, y refactorización hacia clases base o utilidades.
3. **Fallas de Lógica:** Condiciones de carrera, lógica circular (ej. en el orquestador), estados inconsistentes y asincronía mal gestionada.
4. **Acoplamiento e Inyección:** Evaluar qué tan acoplados están los componentes y si se pueden mejorar con inyección de dependencias o interfaces.

---

## Fases de la Auditoría

### 🏗️ Fase 1: Motor Principal y Orquestación (Core Engine)
Esta es la columna vertebral de SODA. Los errores lógicos aquí paralizan toda la generación.
- [ ] `kernel/orchestrator.py` y `kernel/code_generator.py`
- [ ] `kernel/orchestration/` (Ej. `contract_refinement_loop.py`, `intensity_orchestrator.py`)
- [ ] `kernel/execution/` (Ej. `project_runner.py`, `service_orchestrator.py`, `terminal_session.py`, `docker_sandbox.py`)
- [ ] *Foco especial:* Ciclos infinitos durante reintentos, fugas de recursos en el sandbox, y dependencias circulares.

### 🧠 Fase 2: Drivers de IA y Capacidades (AI Layer)
La capa de comunicación con LLMs. Ya hemos visto que es susceptible a cambios sutiles en los payloads.
- [ ] `kernel/drivers/` (Gemini, Claude, Ollama, OpenAI, Provider Hub)
- [ ] `kernel/context/` (Constructores de prompts)
- [ ] `kernel/capabilities/` (Match de perfiles y skills)
- [ ] *Foco especial:* Estabilidad en el parseo de JSONs, timeouts, gestión de Rate Limits (429), y fallback entre drivers.

### 🕵️ Fase 3: Inteligencia y Agentes Cognitivos
Los cerebros especializados que analizan, diseñan y clasifican.
- [ ] `kernel/intelligence/` (Architect, Project Analyzer, Complexity Router, Wisdom Agent, Copilot Consultant)
- [ ] `kernel/design/` (UI Design Agent)
- [ ] *Foco especial:* Redundancia en el parseo de Blueprints, prompts demasiado frágiles, y dependencias directas en vez de inyección de interfaces.

### 🛡️ Fase 4: Integridad, Validación y Auditoría
Los guardianes de la calidad del código generado.
- [ ] `kernel/integrity/` (Validadores de contratos, auditor principal)
- [ ] `kernel/validation/` (Dependencias, arquitecturas, APIs)
- [ ] `kernel/audit/` (Auditor de lenguaje)
- [ ] *Foco especial:* Optimización de búsquedas en el AST (árbol sintáctico), expresiones regulares pesadas o propensas a errores, y manejo de paths relativos vs absolutos.

### 📚 Fase 5: Memoria, Aprendizaje y Estado
El conocimiento persistente de la herramienta.
- [ ] `kernel/learning/` (Behavior Observer, AI Coach)
- [ ] `kernel/knowledge/` (ChromaDB Manager)
- [ ] `kernel/goals/` y `kernel/lineage/` (Árbol de metas y ramas)
- [ ] *Foco especial:* Gestión de conexiones a ChromaDB, serialización JSON (evitar errores de encoding), concurrencia al escribir metadatos o estados en logs.

### 📡 Fase 6: Periféricos y Utilidades Extras
Los componentes de soporte.
- [ ] `kernel/communication/` (Telegram, Interacciones UI)
- [ ] `kernel/vision/` (Visual QA)
- [ ] `kernel/monitoring/`, `kernel/security/`, `kernel/logging/`
- [ ] `kernel/testing/` y utilidades generales.
- [ ] *Foco especial:* Credenciales expuestas, timeouts en red, y fugas de memoria por listeners asíncronos en Telegram o WebSockets.

---

## Flujo de Trabajo Sugerido para cada Fase
1. **Ejecutar linters locales (Flake8 / Pylint):** Para descubrir errores de sintaxis o variables no usadas antes de leer a fondo.
2. **Revisión estática con Roo (Architect/Code):** Escanear el código buscando patrones peligrosos (`except Exception: pass`, `print()` en lugar de logs, lecturas en memoria de archivos gigantes).
3. **Refactorización estructurada:** Aplicar los parches encontrados, asegurando mantener la compatibilidad y testeando el flujo básico de SODA.
4. **Marcar la tarea como lista.**