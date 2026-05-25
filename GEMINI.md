# SODA — Gemini Context & Knowledge Base

Este documento centraliza el conocimiento del proyecto SODA para facilitar la asistencia técnica, el mantenimiento y la evolución del sistema.

## 🚀 Visión General
SODA (Software Orchestration & Development Agency) es un sistema multi-agente determinístico diseñado para transformar requerimientos en lenguaje natural en aplicaciones funcionales, auditadas y mantenibles.

## 🏗️ Arquitectura del Kernel (V4 Hardened)

### Nuevo Pipeline Principal (Zero-Failure Roadmap)
Para evitar la generación de código "deforme", SODA debe seguir estrictamente este flujo:
1. **Definición de Objetivo (WISDOM):** Interrogatorio exhaustivo.
2. **Recursive Planning Council (RPC):** DeepSeek-R1, Gemini y Claude negocian un checklist atómico.
3. **Desarrollo Soberano (DEV):** Cada paso es auditado físicamente contra el disco.
4. **Modo Inquisidor (RIGOR):** Si hay mentiras o desalineación, se baja la temperatura a 0.0 y se bloquean paradigmas ajenos.
5. **Autocuración AST:** Reparación automática de sintaxis antes de la entrega.
6. **Meta-Análisis Forense:** Informe de Gemini 3.5 sobre el kernel y el proyecto.

### Reglas de Ingeniería Inamovibles:
- **Physical Truth:** Ninguna tarea se da por terminada sin un `os.path.exists` exitoso y un AST Parse válido.
- **Contextual Glue:** Siempre inyectar el código de los archivos vecinos antes de una reparación o generación.
- **Paradigm Isolation:** Prohibido importar `flask/http` en CLI, o `gui` en APIs de backend.

---

## 🏗️ Arquitectura del Kernel

### Orquestación Central (`kernel/orchestrator.py`)
El `SodaOrchestrator` es el "cerebro" determinístico. Gestiona la máquina de estados del proyecto y coordina todos los agentes especializados.

### Agentes de Inteligencia (`kernel/intelligence/`)
- **WisdomAgent:** Detecta ambigüedades y genera preguntas proactivas.
- **GoalInterpreter:** Traduce intenciones del usuario a nodos en el árbol de objetivos.
- **Architect:** Diseña la estructura de módulos y define contratos.
- **ImpactAnalyzer:** Calcula el impacto de cambios y sugiere regeneraciones.
- **ContextHealthMonitor:** Monitorea la fatiga de tokens y sugiere refundaciones.

### Generación y Validación (`kernel/`)
- **CodeGenerator:** Genera código usando Qwen (local) con fallback a Claude (cloud).
- **DependencyGraph:** Calcula el orden de ejecución óptimo (Topological Sort).
- **DockerSandbox:** Valida código en entornos aislados.
- **GoalIntegrityValidator:** Garantiza que no exista código "huérfano" sin un objetivo asociado.

### Drivers de IA (`kernel/drivers/`)
- SOPORTE: Claude, Gemini, Ollama (Qwen), OpenAI.
- **AIProviderHub:** Gestiona el routing y fallback entre modelos.

---

## 🛠️ Stack Técnico
- **Lenguaje:** Python 3.11+ (Asyncio)
- **UI:** FastAPI + WebSocket + pywebview (Monaco Editor integrado).
- **Modelos:** Qwen 2.5 Coder (14B/7B), Claude 3.5 Sonnet, Gemini 1.5 Pro/Flash.
- **Persistencia:** ChromaDB (Vectorial), SQLite (Estructural), Git (Código).

---

## 📂 Convenciones del Proyecto
- **Goal ID:** Todo archivo generado debe contener un `goal_id` en sus metadatos para trazabilidad.
- **Contracts:** Los módulos se comunican mediante contratos JSON definidos en la fase ARCH.
- **Branching:** Los cambios estructurales disparan la creación automática de ramas en `projects/<id>/branches/`.

---

## 🧠 Instrucciones para Gemini (Yo)
1. **Prioriza el Determinismo:** Antes de sugerir un cambio de IA, verifica si puede resolverse con lógica en Python en el Orchestrator.
2. **Integridad Primero:** Cualquier modificación de código debe respetar la estructura de `goal_id` y pasar por el `GoalIntegrityValidator`.
3. **Contexto Mínimo:** Genera prompts que sigan el principio de "Contexto Mínimo y Aislado" de SODA.
4. **Validación Pragmática:** Siempre sugiere ejecutar los tests en el `DockerSandbox` tras una modificación.

---

## 📝 Estado Actual y Roadmap Interno
- [x] Pipeline end-to-end básico.
- [x] Multi-driver con fallback.
- [x] UI nativa con editor.
- [x] Sistema de Skills y Perfiles.
- [x] Sistema de Plantillas Escalables (Blueprints).
- [ ] Implementar integración con TypeSpec.
- [ ] Refinar "Refundación" de contexto.
- [ ] Optimizar "Impact Analyzer" para proyectos grandes.
- [ ] Integración completa de Stt/Tts/Vision (en desarrollo).
