# SODA v3
## Software Orchestration & Development Agency
### Documento Consolidado Definitivo

---

## Índice

1. [Visión y Filosofía](#1-visión-y-filosofía)
2. [Arquitectura General del Sistema](#2-arquitectura-general-del-sistema)
3. [Hardware y Entorno](#3-hardware-y-entorno)
4. [Componentes del Kernel](#4-componentes-del-kernel)
5. [Modelos de IA y Asignación por Rol](#5-modelos-de-ia-y-asignación-por-rol)
6. [Sistema de Skills y Perfiles](#6-sistema-de-skills-y-perfiles)
7. [Gestión de Contextos](#7-gestión-de-contextos)
8. [Conocimiento y Memoria](#8-conocimiento-y-memoria)
9. [Árbol de Objetivos](#9-árbol-de-objetivos)
10. [Ciclo de Vida del Proyecto](#10-ciclo-de-vida-del-proyecto)
11. [Sistema de Checkpoints y UX](#11-sistema-de-checkpoints-y-ux)
12. [Modificaciones y Branching](#12-modificaciones-y-branching)
13. [Integridad y Monitoreo](#13-integridad-y-monitoreo)
14. [Comunicación Externa](#14-comunicación-externa)
15. [Interfaz de Usuario](#15-interfaz-de-usuario)
16. [Stack Técnico Completo](#16-stack-técnico-completo)
17. [Estructura de Archivos](#17-estructura-de-archivos)
18. [Roadmap de Implementación](#18-roadmap-de-implementación)
19. [Paso a Paso de Ejecución](#19-paso-a-paso-de-ejecución)
20. [Criterios de Éxito y Riesgos](#20-criterios-de-éxito-y-riesgos)

---

# 1. Visión y Filosofía

## 1.1 Qué es SODA

SODA (Software Orchestration & Development Agency) es un sistema de desarrollo de software semi-autónomo que combina **múltiples agentes de IA especializados** con **orquestación determinística en Python**. Construye aplicaciones completas a partir de descripciones en lenguaje natural, manteniendo al usuario en control a través de checkpoints estratégicos.

No es un generador de código. Es una **agencia de desarrollo virtual** donde perfiles especializados (que acumulan experiencia con el uso) colaboran bajo coordinación determinística para producir software funcional, auditado y mantenible.

## 1.2 Principios Fundamentales

**Principio 1: Coordinación por código, juicio por IA**

Las decisiones de routing, dependencias, control de flujo, y orquestación son Python puro. Las IAs solo intervienen donde se requiere juicio real. No hay "agentes coordinadores" porque la coordinación no requiere inteligencia, requiere determinismo.

**Principio 2: Contextos mínimos y aislados**

Cada IA recibe solo la información estrictamente necesaria para su tarea. Más contexto no es mejor contexto: dispersa la atención, aumenta costo y latencia, y aumenta riesgo de alucinación.

**Principio 3: Paralelismo con aislamiento**

Múltiples instancias del mismo modelo pueden trabajar simultáneamente en módulos distintos, cada una con contexto independiente. El modelo es el motor compartido; los contextos son sesiones aisladas.

**Principio 4: Escalado gradual por necesidad**

Los modelos locales resuelven volumen. Los modelos de pago intervienen solo cuando los locales fallan o cuando se requiere juicio de alto nivel. Escalado automático con umbrales claros.

**Principio 5: El código es consecuencia, no causa**

El usuario nunca modifica código directamente. Modifica **objetivos** e **intenciones**. El sistema traduce cambios de intención a cambios de código, manteniendo trazabilidad bidireccional.

**Principio 6: Validación estructural antes que limpieza reactiva**

No se "limpian huérfanos después", se diseña para que sean estructuralmente imposibles de crear. Integridad por construcción, no por remediación.

**Principio 7: Asignación automática de capacidades**

El sistema decide qué skills y perfiles activar para cada proyecto. El usuario no navega catálogos ni elige configuraciones. SODA analiza el proyecto y ensambla el equipo adecuado.

**Principio 8: Aprendizaje acumulativo**

Cada proyecto mejora el sistema. Los perfiles ganan experiencia, las skills se refinan, los patrones probados se consolidan. El SODA del proyecto #10 es notablemente mejor que el del proyecto #1.

---

# 2. Arquitectura General del Sistema

## 2.1 Vista de Capas

```
┌─────────────────────────────────────────────────────────────┐
│                   CAPA DE INTERFAZ                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Ventana nativa (pywebview)                          │    │
│  │ - Monaco Editor                                     │    │
│  │ - Árbol de objetivos interactivo                    │    │
│  │ - Panel de progreso                                 │    │
│  │ - Project Chat                                      │    │
│  │ - Gestión de perfiles                               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Canales externos (planificado)                      │    │
│  │ - Telegram Bot (inicial)                            │    │
│  │ - WhatsApp (futuro)                                 │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              ↕ WebSocket
┌─────────────────────────────────────────────────────────────┐
│                     CAPA DE KERNEL                          │
│                   (FastAPI + asyncio)                       │
│                                                             │
│  Orquestación           Inteligencia           Integridad   │
│  ─────────────          ─────────────          ──────────   │
│  - Orchestrator         - ContextBuilder       - GoalValid  │
│  - DependencyGraph      - KnowledgeOrch        - HealthMon  │
│  - DockerSandbox        - WisdomAgent          - Lineage    │
│  - Watchdog             - GoalInterpreter                   │
│  - GitManager           - ImpactAnalyzer                    │
│                         - ReferenceAnalyzer                 │
│                                                             │
│  Capacidades            Comunicación           Aprendizaje  │
│  ────────────           ─────────────          ──────────   │
│  - SkillManager         - MessagingGateway     - ProfileEv  │
│  - SkillMatcher         - ProjectChat          - HeuristMg  │
│  - ProfileManager                                           │
│  - ProfileMatcher                                           │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                   CAPA DE MODELOS DE IA                     │
│                                                             │
│  Locales (Ollama)                Cloud (APIs)               │
│  ────────────────                ────────────               │
│  - Qwen 2.5-Coder 14B            - Claude Sonnet 4.5        │
│  - Qwen 2.5-Coder 7B             - Gemini 2.5 Pro           │
│  - DeepSeek Coder V2 Lite        - Gemini 2.5 Flash         │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                   CAPA DE PERSISTENCIA                      │
│                                                             │
│  Memoria Semántica       Memoria Estructural    Código      │
│  ─────────────────       ──────────────────     ───────     │
│  - ChromaDB (Project)    - SQLite (proyectos)   - Git       │
│  - ChromaDB (Profiles)   - JSON (goals tree)    - Files     │
│  - ChromaDB (Skills)     - YAML (skills/prof)               │
│  - ChromaDB (Docs)                                          │
└─────────────────────────────────────────────────────────────┘
```

## 2.2 Flujo de Información

Cuando el usuario interactúa con SODA, la información fluye así:

1. **Input del usuario** → UI/Canal externo → Kernel
2. **Kernel analiza** intención → Goal Interpreter, Skill/Profile Matcher
3. **Kernel ensambla equipo** → selecciona modelos, perfiles, skills
4. **ContextBuilder arma contextos** mínimos para cada agente
5. **Agentes ejecutan** tareas en paralelo (con aislamiento)
6. **Validadores verifican** integridad (huérfanos, contratos, tests)
7. **Sandbox Docker ejecuta** código generado en aislamiento
8. **Resultados consolidados** → Kernel integra
9. **UI muestra** progreso y solicita checkpoints cuando corresponde
10. **Aprendizajes se capturan** → Profile Evolution actualiza perfiles

## 2.3 Jerarquía Anidada de Ejecución

SODA opera en niveles anidados, todos coordinados por el mismo Kernel:

```
NIVEL PROYECTO
├── Decisiones de arquitectura global
├── Contratos entre módulos
└── Integración final

    NIVEL MÓDULO (múltiples, paralelos cuando se puede)
    ├── Diseño interno del módulo
    ├── Código del módulo
    ├── Tests del módulo
    └── Validación del módulo

        NIVEL SUBMÓDULO (cuando se justifica)
        ├── Funciones complejas con estructura propia
        └── Componentes internos específicos
```

La profundidad de anidamiento se decide según complejidad. Un CRUD simple tiene 2 niveles. Un sistema complejo puede tener 3-4.

---

# 3. Hardware y Entorno

## 3.1 Hardware Objetivo

**Configuración de referencia:**
- **CPU:** Intel i9 13900 (24 núcleos, ~5.8 GHz boost)
- **RAM:** 64 GB DDR5
- **GPU:** NVIDIA GTX 5070 Ti (16 GB VRAM)
- **Almacenamiento:** SSD NVMe (necesario para velocidad de I/O)
- **SO base:** Windows 11

## 3.2 Entorno de Desarrollo

**WSL2 con Ubuntu 22.04 LTS**

SODA corre dentro de WSL2, no en Windows nativo. Razones:
- Docker funciona sustancialmente mejor en Linux
- Librerías Python con compilación C tienen menos problemas
- Watchdog es más estable en Linux
- GPU passthrough de NVIDIA funciona en WSL2

**Gestión de Python: `uv`**

Gestor ultra-rápido de Astral. Reemplaza a pip + venv + pyenv con una sola herramienta 10-100x más rápida.

**Editor: Cursor**

Editor basado en VS Code con integración nativa de IA. Configurado con:
- API key propia de Anthropic (evita suscripción Cursor Pro)
- Conexión a Ollama local para completado con modelos propios
- Extensiones preservadas de VS Code

**Runtime de modelos locales: Ollama**

Sirve modelos locales vía API HTTP. Configurado con:
- `OLLAMA_NUM_PARALLEL=3` para permitir paralelismo real
- Modelos precargados para minimizar latencia en swap

## 3.3 Uso de Recursos Estimado

Durante ejecución típica de SODA:

| Recurso | Uso | Detalle |
|---------|-----|---------|
| RAM | 15-25 GB | IDE + WSL2 + Docker + FastAPI + Ollama + buffers |
| VRAM | 10-14 GB | Qwen 14B cargado + 3 contextos paralelos |
| CPU | 40-70% | Orquestación asyncio + Docker validación |
| Disco | 10-50 GB/proy | Dependiendo del proyecto |
| Red | Variable | APIs externas + git + Docker pulls |

Queda margen significativo para operación simultánea con otras aplicaciones.

---

# 4. Componentes del Kernel

Esta sección describe cada componente del Kernel con su responsabilidad específica.

## 4.1 Componentes de Orquestación

### Orchestrator

Corazón del sistema. Coordina el flujo general de cada proyecto.

**Responsabilidades:**
- Dirigir el flujo del ciclo de vida del proyecto
- Gestionar el estado global del proyecto actual
- Enrutar tareas a los agentes apropiados
- Consolidar resultados y manejar fallos
- Disparar checkpoints cuando corresponde
- Manejar timeouts y reintentos

**No tiene IA.** Es Python puro con máquinas de estado.

### Dependency Graph

Construye y mantiene el grafo dirigido acíclico (DAG) de dependencias entre módulos.

**Responsabilidades:**
- Analizar contratos para inferir dependencias
- Detectar ciclos (y rechazarlos)
- Calcular orden de ejecución óptimo
- Identificar módulos paralelizables vs secuenciales
- Recalcular el grafo cuando hay modificaciones

**Algoritmo:** Topological sort con identificación de niveles paralelos.

### Docker Sandbox

Ejecuta código generado en contenedores aislados.

**Responsabilidades:**
- Crear contenedores efímeros por validación
- Montar código a validar sin comprometer el host
- Ejecutar tests y capturar resultados
- Limpiar contenedores después de uso
- Manejar timeouts de ejecución
- Reportar errores con stderr/stdout capturado

**Configuración por defecto:**
- Imagen base: `python:3.11-slim`
- Memory limit: 512 MB
- CPU limit: 1 core
- Network: none (a menos que se requiera)
- Timeout: 30 segundos

### Watchdog

Monitorea el sistema de archivos del workspace.

**Responsabilidades:**
- Detectar cambios en archivos del proyecto
- Crear backups atómicos antes de modificaciones
- Disparar revalidaciones cuando corresponde
- Mantener el lock de escritura (solo el Kernel escribe)
- Recuperar estado si el sistema se reinicia

### Git Manager

Integración con Git y GitHub.

**Responsabilidades:**
- Crear repos nuevos en GitHub vía API
- Commit automático por hito alcanzado
- Branch management para variantes
- Push al remoto con mensajes descriptivos
- Tag de versiones al completar proyectos

## 4.2 Componentes de Inteligencia

### Context Builder

El único componente en todo SODA que construye contextos para agentes.

**Responsabilidades:**
- Ensamblar contextos mínimos por rol y tarea
- Aplicar filtrado según skills y perfiles activos
- Inyectar conocimiento relevante vía RAG
- Aplicar caché de prompts de Claude cuando aplique
- Logear tamaño de cada contexto para monitoreo
- Comprimir contextos que superen umbrales

**Centralización intencional:** tener UN solo componente armando contextos permite optimizar todo el sistema desde un punto.

### Knowledge Orchestrator

Gestiona las cuatro capas de conocimiento del sistema.

**Responsabilidades:**
- Rutear consultas de conocimiento a la fuente correcta
- Fusionar resultados de múltiples fuentes
- Mantener embeddings actualizados
- Indexar nuevos documentos
- Priorizar fuentes según relevancia

**Capas que gestiona:**
1. Project RAG (proyecto actual)
2. Profile Knowledge (perfil activo)
3. Skill Knowledge (skills activas)
4. Document Knowledge (docs del usuario)
5. Reference Knowledge (programas de referencia cuando aplique)

### Wisdom Agent

Genera preguntas proactivas y observaciones al usuario basándose en experiencia.

**Responsabilidades:**
- Analizar pedidos del usuario contra corpus de conocimiento
- Detectar ambigüedades y complejidades ocultas
- Generar preguntas clarificadoras con ejemplos
- Advertir sobre decisiones con consecuencias importantes
- Sugerir consideraciones del dominio

**Modelo:** Gemini 2.5 Pro (contexto largo permite procesar múltiples fuentes simultáneamente).

**Modo:** Sugerencias, no bloqueante. Usuario puede ignorar.

### Goal Interpreter

Traduce pedidos del usuario a modificaciones del árbol de objetivos.

**Responsabilidades:**
- Parsear pedidos en lenguaje natural
- Identificar qué nodos del árbol afecta el pedido
- Detectar intenciones de referencia ("como X")
- Clasificar tipo de modificación (parámetro, comportamiento, estructural, alcance, dirección)
- Generar plan de modificación estructurado

**Modelo:** Claude Sonnet 4.5 (razonamiento fino sobre intención).

### Impact Analyzer

Calcula impacto pragmático de cambios propuestos.

**Responsabilidades:**
- Identificar módulos afectados por un cambio
- Generar plan de modificación
- Crear rama alternativa del proyecto (branching)
- Ejecutar ambas versiones para comparación real
- Medir benchmarks comparativos
- Detectar incompatibilidades con objetivos previos

**Ejecución pragmática:** no análisis estático puro, sino comparación de comportamiento real entre versiones.

### Reference Analyzer

Se activa cuando el usuario menciona un programa como referencia.

**Responsabilidades:**
- Detectar menciones de programas (Calendly, Notion, etc.)
- Clasificar tipo de referencia (réplica, mejora, inspiración)
- Obtener información del programa referenciado
  - Si open source: git clone y análisis
  - Si cerrado: conocimiento del LLM + material del usuario
- Generar ficha estructurada del programa
- Guiar selección de alcance con el usuario

**Activación:** solo cuando el Goal Interpreter detecta referencia, no como biblioteca permanente.

## 4.3 Componentes de Integridad

### Goal Integrity Validator

Garantiza las barreras anti-huérfanos.

**Responsabilidades:**
- Validar que todo archivo tenga `goal_id` válido
- Validar que todo goal del árbol tenga implementación
- Bloquear commits con código huérfano
- Ejecutar test bidireccional (árbol ↔ código)
- Detectar "casi huérfanos" (goal actualizado sin regenerar código)

**Barreras que implementa:**
1. Barrera de generación (código sin goal_id no se genera)
2. Barrera de validación (test bidireccional pre-commit)
3. Barrera de modificación (cleanup transaccional)

### Context Health Monitor

Monitorea señales de fatiga del contexto.

**Responsabilidades:**
- Medir tamaño de contexto vs límite del modelo
- Detectar degradación en tasa de éxito
- Identificar respuestas incoherentes con estado actual
- Detectar ciclos de reescritura
- Medir tiempo de respuesta de modelos

**Niveles de alerta:**
- Nivel 1 (observación): log interno
- Nivel 2 (auto-optimización): resuelve solo
- Nivel 3 (sugerencia al usuario): ofrece limpieza o refundación
- Nivel 4 (intervención obligada): cuando contexto excede límite técnico

### Project Lineage

Registro histórico de proyectos refundados.

**Responsabilidades:**
- Guardar snapshots pre-refundación
- Vincular proyecto hijo a proyecto padre
- Permitir ver genealogía completa
- Recuperar estado antes de refundación si se solicita

## 4.4 Componentes de Capacidades

### Skill Manager

Catálogo central de skills.

**Responsabilidades:**
- Mantener skills base (vienen con SODA)
- Gestionar skills generadas automáticamente
- Indexar skills para búsqueda semántica
- Resolver dependencias entre skills
- Versionar skills
- Validar skills nuevas antes de activarlas

### Skill Matcher

Asigna skills automáticamente a proyectos.

**Responsabilidades:**
- Analizar descripción del proyecto
- Detectar dominios, tecnologías, regiones
- Matchear contra catálogo de skills
- Calcular scores de relevancia
- Aplicar skills por rol (cada skill define a qué roles aplica)
- **No requiere intervención del usuario**

**Modelo:** Gemini 2.5 Pro para análisis, lógica determinística para asignación final.

### Profile Manager

Gestiona perfiles especializados.

**Responsabilidades:**
- CRUD de perfiles
- Almacenar perfiles como estructuras de archivos + índices
- Versionar perfiles (rollback posible)
- Export/import
- Estadísticas de uso por perfil

### Profile Matcher

Asigna perfiles a proyectos **automáticamente**.

**Responsabilidades:**
- Analizar proyecto y seleccionar perfiles más relevantes
- Puede asignar múltiples perfiles (primario + secundarios)
- Distribuir perfiles por rol (qué rol usa qué perfil)
- Detectar cuando ningún perfil existente aplica bien
- Iniciar creación de perfil nuevo si se requiere
- **Usuario no navega catálogos ni elige**

**Modelo:** Gemini 2.5 Pro.

### Profile Evolution Engine

Hace crecer los perfiles con la experiencia.

**Responsabilidades:**
- Capturar aprendizajes de cada proyecto completado
- Consolidar patrones repetidos en "knowledge core" del perfil
- Detectar anti-patterns (cosas que siempre fallan)
- Detectar preferencias implícitas del usuario
- Sugerir mejoras al perfil (con aprobación del usuario)
- Generar nuevos perfiles desde proyectos cuando corresponde

**Ciclo de consolidación:** al completar cada proyecto + revisión periódica automática.

## 4.5 Componentes de Comunicación

### Messaging Gateway

Abstracción de canales de mensajería externa.

**Responsabilidades:**
- Enviar notificaciones a canales configurados
- Recibir respuestas y rutearlas al proyecto correspondiente
- Adaptar formato según canal
- Autenticación de usuario por canal
- Rate limiting para no saturar

**Canales soportados:**
- UI web (siempre activo)
- Telegram (primera integración externa)
- WhatsApp (planificado, fase posterior)

### Project Chat

Interfaz conversacional para consultar el proyecto.

**Responsabilidades:**
- Recibir consultas en lenguaje natural sobre el proyecto
- Consultar el Knowledge Orchestrator
- Responder con información estructurada
- Mantener contexto de conversación dentro del proyecto

**Implementación:** pestaña en la UI principal (no ventana flotante).

**Modelo:** Gemini 2.5 Flash (rápido, barato, suficiente para consultas).

## 4.6 Componentes de Aprendizaje

### Heuristics Manager

Gestiona las "Reglas de Oro" del sistema.

**Responsabilidades:**
- Capturar heurísticas candidatas durante ejecución
- Validar heurísticas contra múltiples proyectos antes de promoverlas
- Mantener heurísticas con scores de confianza
- Aplicar decay a heurísticas poco usadas
- Detectar heurísticas contradictorias y resolverlas

---

# 5. Modelos de IA y Asignación por Rol

## 5.1 Modelos Utilizados

### Modelos Locales (vía Ollama)

| Modelo | Tamaño | VRAM | Uso principal |
|--------|--------|------|---------------|
| Qwen 2.5-Coder 14B | 9 GB | 10 GB | Generación de código principal |
| Qwen 2.5-Coder 7B | 5 GB | 6 GB | Revisión, tareas secundarias |
| DeepSeek Coder V2 Lite | 10 GB | 11 GB | Generación de tests, casos edge |

### Modelos Cloud (APIs)

| Modelo | Vía | Uso principal |
|--------|-----|---------------|
| Claude Sonnet 4.5 | Anthropic API | Juicio crítico, debugging, auditoría |
| Gemini 2.5 Pro | Google AI API | Contexto amplio, arquitectura, integración |
| Gemini 2.5 Flash | Google AI API | Tareas rápidas, resumen, routing |

## 5.2 Asignación por Rol

**Roles de Nivel Proyecto (llamadas puntuales, alto valor):**

| Rol | Modelo | Justificación |
|-----|--------|---------------|
| Entrevistador de requerimientos | Claude Sonnet 4.5 | Juicio fino para entrevista técnica |
| Arquitecto global | Gemini 2.5 Pro | Contexto 1M para visión completa |
| Auditor de arquitectura | Claude Sonnet 4.5 | Segunda opinión crítica |
| Integrador final | Gemini 2.5 Pro | Análisis cross-módulo |
| Auditor de integración | Claude Sonnet 4.5 | Crítica experta final |
| Debugger escalado | Claude Sonnet 4.5 | Cuando locales fallan 3 veces |

**Roles de Nivel Módulo (llamadas de alto volumen):**

| Rol | Modelo | Justificación |
|-----|--------|---------------|
| Generador de código | Qwen 2.5-Coder 14B | Volumen, gratis, calidad cerca de SOTA |
| Revisor de código | Qwen 2.5-Coder 7B | Rápido, suficiente para revisión |
| Generador de tests | DeepSeek Coder V2 Lite | Fuerte en casos edge |
| Optimizador | Qwen 2.5-Coder 14B | Refactoring y performance |

**Roles Transversales:**

| Rol | Modelo | Uso |
|-----|--------|-----|
| Goal Interpreter | Claude Sonnet 4.5 | Juicio sobre intenciones |
| Skill Matcher | Gemini 2.5 Pro | Análisis de proyecto completo |
| Profile Matcher | Gemini 2.5 Pro | Análisis de proyecto completo |
| Wisdom Agent | Gemini 2.5 Pro | Preguntas proactivas informadas |
| Reference Analyzer | Gemini 2.5 Pro | Análisis de programas referenciados |
| Project Chat | Gemini 2.5 Flash | Consultas rápidas al proyecto |
| Resumen de contextos | Gemini 2.5 Flash | Compresión inteligente |

**Lo que NO es IA (Python puro):**

Orchestrator, DependencyGraph, DockerSandbox, Watchdog, GitManager, ContextBuilder (aunque consulta IAs, su lógica es determinística), GoalIntegrityValidator, ContextHealthMonitor, ProjectLineage, SkillManager, ProfileManager, MessagingGateway, HeuristicsManager.

## 5.3 Estrategia de Escalado

Cuando una tarea falla, escalado automático:

```
Intento 1: Qwen local genera código
   ↓ si tests fallan
Intento 2: Qwen revisa su propio código con el error como contexto
   ↓ si tests fallan
Intento 3: Qwen regenera desde cero con contexto ampliado
   ↓ si tests fallan
Intento 4: Escalado a Claude Sonnet con historial completo
   ↓ si tests fallan
Intento 5: CHECKPOINT HUMANO OBLIGATORIO
```

Esto mantiene ~90% del trabajo en modelos locales. Solo casos difíciles llegan a Claude.

## 5.4 Paralelismo

**Configuración Ollama:**
```bash
OLLAMA_NUM_PARALLEL=3
```

Con Qwen 14B (9GB) + 3 contextos concurrentes, uso estimado: ~13 GB VRAM. Margen para operación estable.

**Modos de ejecución:**
- **Secuencial** (default para proyectos nuevos): módulos uno tras otro
- **Paralelo** (activable): orquestador lanza todo lo independiente según DAG, máx 3 workers

**Aislamiento:** cada instancia recibe contexto independiente. Aunque sean "el mismo Qwen", no comparten información entre sí.

---

# 6. Sistema de Skills y Perfiles

## 6.1 Diferencia Conceptual

**Skill:** unidad atómica de capacidad. "Sabe X".
Ejemplo: `skill_mercadopago_integration` tiene conocimiento sobre integrar MP.

**Perfil:** conjunto coherente de skills + conocimiento acumulado + estilo.
Ejemplo: `profile_fintech_latam` es un "especialista" que agrupa skills fintech + experiencia de N proyectos + preferencias consolidadas.

Los perfiles **contienen** skills. Las skills son bloques, los perfiles son profesionales.

## 6.2 Estructura de una Skill

```
skill_mercadopago_integration/
├── manifest.yaml
├── system_prompt.md
├── knowledge/
│   ├── api_reference.md
│   ├── best_practices.md
│   └── common_errors.md
├── examples/
│   ├── subscription.py
│   ├── webhook.py
│   └── refund.py
├── tests/
│   └── validation.py
└── checklist.yaml
```

**manifest.yaml define:**
- Categoría de la skill
- Dependencias con otras skills
- A qué roles aplica (y con qué nivel de detalle)
- Condiciones de activación (cuándo matchear)
- Versión y metadata

## 6.3 Estructura de un Perfil

```
profile_fintech_latam/
├── identity.yaml
├── skills_included/
│   └── [referencias a skills]
├── knowledge_base/
│   ├── regulatory_overview.md
│   ├── common_patterns.md
│   └── regional_considerations.md
├── experience/
│   ├── project_001_learnings.md
│   ├── project_002_learnings.md
│   └── accumulated_wisdom.md
├── style/
│   ├── code_conventions.md
│   ├── preferred_patterns.md
│   └── architectural_biases.md
├── references/
│   └── documentation_links.yaml
└── manifest.yaml
```

## 6.4 Asignación Automática

**Momento 1: Al iniciar proyecto**

Skill Matcher y Profile Matcher analizan la descripción del proyecto y automáticamente seleccionan qué skills y perfiles activar. **El usuario no participa en esta decisión.**

El usuario ve el resultado final (qué se aplicó) pero no navega catálogos ni elige.

**Momento 2: Ejecución**

Skills y perfiles activos se cargan en los agentes según el rol. Cada agente tiene su contexto enriquecido con el conocimiento relevante.

**Momento 3: Finalización**

Profile Evolution Engine captura aprendizajes y los consolida en el perfil activo.

## 6.5 Ciclo de Vida de un Perfil

**Fase 1: Génesis**

SODA arranca con un conjunto de **perfiles base genéricos** similares a los skills de Claude:
- General Software Developer
- Web Full-Stack Developer
- Backend API Developer
- Data Engineer
- Mobile App Developer

Estos perfiles son **genéricos al inicio**. No tienen especialización en dominios específicos.

**Fase 2: Especialización emergente**

A medida que el usuario ejecuta proyectos, el Profile Evolution Engine detecta dominios recurrentes. Después de 2-3 proyectos con características similares, propone:

```
💡 OBSERVACIÓN DEL SISTEMA

Detecté que tus últimos 3 proyectos tuvieron características
similares (sistemas de pagos, integración con MercadoPago,
facturación AFIP).

Propongo crear un perfil especializado:
"Especialista Fintech LATAM"

Este perfil acumulará conocimiento específico de este dominio,
haciendo futuros proyectos similares más eficientes y de mayor
calidad.

[✓ Crear perfil] [Ver qué contendría] [No, gracias]
```

Si el usuario aprueba, SODA genera el perfil automáticamente a partir de la experiencia de esos 3 proyectos.

**Fase 3: Maduración**

Con cada nuevo proyecto usando el perfil, este acumula:
- Patrones validados
- Anti-patterns identificados
- Decisiones consolidadas
- Preferencias del usuario
- Conocimiento técnico refinado

**Fase 4: Mastería**

Después de 10+ proyectos, un perfil puede:
- Tomar decisiones de diseño consistentes sin preguntar
- Anticipar problemas del dominio antes de que ocurran
- Tener su propia "personalidad" de código
- Ser exportable para compartir con otros usuarios

## 6.6 Asignación Automática por la IA

Este punto es central: **la IA decide, no el usuario**.

**Flujo:**

1. Usuario describe proyecto
2. Profile Matcher (Gemini Pro) analiza la descripción
3. Consulta el catálogo de perfiles existentes
4. Score cada perfil por relevancia
5. Selecciona perfiles por encima del umbral
6. Distribuye perfiles a roles específicos
7. Informa al usuario de la decisión (no pregunta)

**Cuando no hay match:**

Si ningún perfil existente matchea bien, SODA usa perfiles base genéricos y marca el proyecto como "candidato a génesis de perfil nuevo". Al completar, evalúa si crear perfil nuevo.

**El usuario puede:**
- Ver qué perfiles se asignaron
- Aceptar la asignación (default, no requiere acción)
- Excepcionalmente, sobreescribir la asignación si no está de acuerdo

**Pero por default, SODA decide y ejecuta.**

---

# 7. Gestión de Contextos

## 7.1 Principio Central

**Menos es más.** Más contexto no es mejor contexto. Dispersión, costo, alucinación.

## 7.2 Técnicas Aplicadas

### System prompts específicos por rol

Cada rol tiene su prompt minimalista, enfocado. No hay prompts genéricos enormes que intenten cubrir todo.

### Contratos en vez de código completo

Cuando un módulo necesita saber cómo interactuar con otro, recibe el **contrato de interfaz**, no el código completo del módulo vecino.

### RAG agresivo

ChromaDB con búsqueda semántica. Solo los N resultados más relevantes llegan al contexto.

### Ventanas deslizantes

En ciclos iterativos (error → corrección), solo se mantiene:
- El mensaje original
- Resumen de intentos previos
- El error actual

No se acumula el historial completo.

### Resumen incremental

Gemini 2.5 Flash resume historiales largos cuando corresponde. Barato, rápido.

### Prompt caching de Claude

Contenido repetido en múltiples llamadas se cachea. 90% ahorro en los tokens cacheados.

### Skills y perfiles filtrados por load_level

Cada skill define cuánto detalle inyectar por rol. Un rol revisor no recibe ejemplos de código extensos, solo el checklist.

## 7.3 Metas de Eficiencia

| Tipo de llamada | Contexto meta |
|-----------------|---------------|
| Qwen local generador | < 4k tokens |
| Qwen local revisor | < 3k tokens |
| Claude Sonnet (con caché) | < 8k tokens nuevos |
| Gemini Pro arquitectura | < 50k tokens |
| Gemini Pro integración final | < 200k tokens |
| Gemini Flash consultas | < 2k tokens |

## 7.4 Monitoreo Continuo

Cada llamada logea tamaño de contexto. El ContextHealthMonitor observa tendencias. Contextos creciendo dispara optimizaciones automáticas (Nivel 2) o sugerencias al usuario (Nivel 3).

---

# 8. Conocimiento y Memoria

## 8.1 Cuatro Capas de Conocimiento

**Capa 1: Project RAG**
- Scope: proyecto actual
- Contiene: árbol de objetivos, decisiones, código con metadata, logs de errores
- Uso: agentes consultan contexto de su propio proyecto
- También expuesto como Project Chat al usuario

**Capa 2: Profile Knowledge**
- Scope: por perfil
- Contiene: conocimiento especializado del perfil, experiencia acumulada, preferencias
- Uso: agentes operando bajo un perfil consultan esta base

**Capa 3: Skill Knowledge**
- Scope: por skill
- Contiene: documentación específica, ejemplos, checklists de cada skill
- Uso: agentes consultan según las skills activas

**Capa 4: Document Knowledge**
- Scope: documentos cargados por el usuario para un proyecto
- Contiene: PDFs, docs, specs que el usuario aportó
- Uso: cuando el usuario sube "la documentación de la API de mi cliente", esta capa la sirve

## 8.2 Orquestación

El Knowledge Orchestrator decide dinámicamente qué capas consultar según la tarea:

```python
# Pseudocódigo conceptual
def get_relevant_knowledge(task, agent_role, active_profile, active_skills):
    results = []
    
    # Siempre consultar el proyecto actual
    results += project_rag.query(task)
    
    # Consultar perfil activo
    if active_profile:
        results += profile_kb[active_profile].query(task)
    
    # Consultar skills activas
    for skill in active_skills:
        if skill.applies_to_role(agent_role):
            results += skill_kb[skill].query(task)
    
    # Consultar documentos si son relevantes
    if has_uploaded_docs():
        results += document_kb.query(task)
    
    return merge_and_rank(results, max_tokens=budget)
```

## 8.3 Referencias bajo Demanda

Adicional a las capas permanentes, cuando el usuario menciona un programa como referencia, el Reference Analyzer crea una capa **temporal** para ese proyecto específico. No se agrega a la biblioteca permanente.

## 8.4 Heurísticas (Reglas de Oro)

Capturadas durante ejecución, validadas contra múltiples proyectos antes de promoverse. Forma parte del Profile Knowledge del perfil activo.

**Ciclo:**
1. Patrón detectado en 1 proyecto → candidato
2. Patrón confirmado en 2-3 proyectos → heurística con score bajo
3. Patrón confirmado en 5+ proyectos → heurística consolidada con score alto
4. Patrón no usado en 10+ proyectos → decay, se archiva

---

# 9. Árbol de Objetivos

## 9.1 Estructura

Todo proyecto tiene un árbol de objetivos jerárquico:

```
Proyecto
├── Categoría 1 (Gestión de usuarios)
│   ├── Objetivo (Autenticación)
│   │   ├── Decisión (Login con email/password)
│   │   ├── Decisión (Password mínimo 8 caracteres)
│   │   └── Código: [files con goal_id]
│   └── Objetivo (Perfiles)
├── Categoría 2 (Gestión de tareas)
│   └── ...
```

## 9.2 Metadata de cada Nodo

```yaml
node_id: ath-001-login
type: objective
parent: users-mgmt
description: "Autenticación de usuarios con email y contraseña"
status: implemented  # planned | in_progress | implemented | orphaned
decisions:
  - ath-001-d1: "Email y password"
  - ath-001-d2: "Mínimo 8 caracteres"
  - ath-001-d3: "Bcrypt para hashing"
implemented_by_files:
  - modules/auth/login.py
  - modules/auth/password_validator.py
  - modules/auth/session_manager.py
created: 2026-04-19T10:00:00
last_modified: 2026-04-19T14:30:00
hash: a3f9c2...  # para detectar cambios semánticos
```

## 9.3 Trazabilidad Bidireccional

**Del árbol al código:** cada nodo sabe qué archivos lo implementan.

**Del código al árbol:** cada archivo tiene metadata con `goal_id`.

```python
# Ejemplo de archivo generado
# --- METADATA SODA (no editar manualmente) ---
# goal_id: ath-001-login
# goal_path: Gestión de usuarios → Autenticación → Login
# contract_version: 1.2
# generated: 2026-04-19T10:15:00
# goal_hash: a3f9c2...
# --- FIN METADATA ---

def authenticate_user(email, password):
    ...
```

## 9.4 Interactividad

El árbol es la interfaz principal de navegación del proyecto. El usuario puede:

- **Ver:** estructura completa, estado de cada nodo, dependencias
- **Click en nodo:** detalles, archivos que lo implementan, historia
- **Click derecho en decisión:** modificarla (dispara flujo de modificación)
- **Arrastrar nodos:** reestructurar (dispara análisis de impacto)
- **Click en ➕:** agregar funcionalidad nueva
- **Hover:** tooltip con resumen de impacto
- **Filtros:** ver solo nodos "planificados", "desincronizados", etc.

## 9.5 Vistas Alternativas

El mismo árbol puede mostrarse reorganizado:
- **Por objetivos** (default): intención del usuario
- **Por módulos:** estructura técnica
- **Por dependencias:** grafo de relaciones
- **Temporal:** cuándo se agregó cada cosa

---

# 10. Ciclo de Vida del Proyecto

## 10.1 Fase 0: Inicialización

**Sistema hace:**
- Crea workspace del proyecto (estructura de directorios)
- Inicializa ChromaDB local para el proyecto
- Prepara repo Git (local + remoto si configurado)
- Crea árbol de objetivos vacío

**Usuario hace:**
- Nada aún (o nombra el proyecto)

## 10.2 Fase 1: Requerimientos

**Sistema hace:**
- **Skill Matcher** analiza la descripción inicial y preselecciona skills
- **Profile Matcher** analiza y selecciona perfiles aplicables
- **Wisdom Agent** genera preguntas proactivas basadas en perfil
- **Claude Sonnet** (como Entrevistador) conduce entrevista técnica
- Genera `blueprint.json` con especificaciones

**Usuario hace:**
- Responde preguntas de la entrevista
- Valida el resumen del proyecto (Checkpoint 1)

**Output:** blueprint.json validado

## 10.3 Fase 2: Arquitectura

**Sistema hace:**
- **Gemini Pro** (como Arquitecto Global) diseña la arquitectura
  - Usa perfiles asignados
  - Usa skills activas
  - Considera referencias si se mencionaron
- **Claude Sonnet** (como Auditor) revisa críticamente
- Genera diagramas, contratos, estructura de módulos
- Python genera estructura de directorios, Dockerfile, contracts.json

**Usuario hace:**
- Revisa diagrama y descripción (Checkpoint 2)
- Aprueba o pide ajustes

**Output:** arquitectura validada + árbol de objetivos inicial

## 10.4 Fase 3: Planificación

**Sistema hace:**
- **DependencyGraph** construye DAG de módulos
- Identifica módulos paralelizables
- Genera plan de construcción con estimaciones

**Usuario hace:**
- Ve plan (Checkpoint informativo)
- Puede pausar o ajustar si quiere

## 10.5 Fase 4: Desarrollo

**Sistema hace (por cada módulo, paralelo cuando aplica):**

1. **Qwen Arquitecto de Módulo** diseña interior
2. **Qwen Generador** escribe código
   - Con skills cargadas según el módulo
   - Con perfil activo
   - Con metadata de goal_id obligatoria
3. **DeepSeek Tester** genera tests
4. **Docker Sandbox** ejecuta tests
5. Si pasa → commit parcial + siguiente módulo
6. Si falla:
   - Reintentos automáticos con Qwen
   - Escalado a Claude si falla 3 veces
   - Checkpoint humano si Claude también falla

**Goal Integrity Validator** corre en cada commit para evitar huérfanos.

**Context Health Monitor** observa señales de fatiga.

**Usuario hace:**
- Ve progreso en tiempo real
- Solo interviene si el sistema lo pide (ambigüedades, errores escalados)

## 10.6 Fase 5: Integración

**Sistema hace:**
- **Gemini Pro** revisa sistema completo (aprovecha contexto 1M)
- Ejecuta tests end-to-end en Docker
- **Claude Sonnet** audita integración final
- Genera documentación automática

**Usuario hace:**
- Revisa reporte de integración (Checkpoint 3)
- Prueba la app en vivo
- Aprueba o pide ajustes

## 10.7 Fase 6: Entrega

**Sistema hace:**
- Commit final a GitHub
- Tag de versión
- Documentación final (README, API docs, etc.)
- Preparación para deploy si aplica

**Usuario hace:**
- Aprueba entrega (Checkpoint 4)
- Decide si desplegar ahora o después

## 10.8 Fase 7: Aprendizaje Post-Proyecto

**Sistema hace:**
- **Profile Evolution Engine** analiza el proyecto
- Captura patrones exitosos
- Identifica anti-patterns
- Actualiza perfiles activos
- Si corresponde, propone crear perfil nuevo

**Usuario hace:**
- Valida aprendizajes propuestos (Checkpoint 5)
- Decide si guardar o descartar cada uno

---

# 11. Sistema de Checkpoints y UX

## 11.1 Principios de UX

1. **Progreso siempre visible.** Nunca preguntarse "¿está haciendo algo?"
2. **Lenguaje humano por defecto, técnico opcional.**
3. **El tiempo del usuario se respeta.** Checkpoints solo en momentos clave.
4. **Decisiones con opciones claras.** Nunca input de texto complejo obligatorio.
5. **Reversibilidad.** Siempre se puede volver atrás.
6. **Estimaciones honestas.** Tiempo y costo antes de comprometerse.

## 11.2 Los 5 Checkpoints Principales

**Checkpoint 1: Validación de requerimientos**

Después de la entrevista, antes de arquitectura.

Se muestra: **Ficha del proyecto** (nombre, qué hace, funcionalidades, tecnologías, estimaciones).

Acciones: Aprobar | Ajustar | Rechazar

**Checkpoint 2: Validación de arquitectura**

Después del diseño arquitectónico, antes del desarrollo.

Se muestra: **Diagrama visual** de módulos con explicación en lenguaje humano + árbol de objetivos inicial.

Acciones: Aprobar y construir | Ajustar | Ver alternativa

**Checkpoint 3: Validación de integración**

Después del desarrollo, antes de la entrega.

Se muestra: **Reporte de entrega** (módulos creados, líneas, tests, advertencias) + app en vivo para probar.

Acciones: Probar | Aceptar | Pedir ajustes

**Checkpoint 4: Confirmación de entrega**

Antes de deploy (si aplica).

Se muestra: **Resumen final** + opciones de deploy.

Acciones: Finalizar | Desplegar | Ajustes finales

**Checkpoint 5: Aprendizajes**

Al finalizar el proyecto.

Se muestra: **Patrones aprendidos y consolidaciones propuestas** al perfil.

Acciones: Guardar todo | Revisar individualmente | Descartar

## 11.3 Interrupciones Controladas

Además de los checkpoints principales, SODA puede interrumpir en:

- **Ambigüedades detectadas:** preguntas con opciones + ejemplos de impacto
- **Escalado de errores:** cuando Claude también falla, requiere decisión humana
- **Cambios grandes propuestos:** cuando el Impact Analyzer detecta impacto significativo
- **Contexto en Nivel 3:** cuando el Health Monitor detecta fatiga

## 11.4 Formato de Preguntas de Ambigüedad

Cada opción presentada incluye:

1. **Ejemplo concreto** con datos ficticios (no abstracto)
2. **Consecuencias prácticas** para el usuario final
3. **Trade-offs honestos** (pros y contras)
4. **Sugerencia contextual** (cuando el sistema tiene evidencia)
5. **Opción "hablar más"** siempre disponible

## 11.5 Preguntas Proactivas del Wisdom Agent

**Modo: sugeridas, no bloqueantes.**

El Wisdom Agent puede interrumpir con observaciones:

```
💡 Observación del sistema

En proyectos similares, estas decisiones suelen importar:

- Pregunta A con ejemplo
- Pregunta B con ejemplo  
- Pregunta C con ejemplo

[Responder] [Ignorar] [Recordármelo después]
```

El usuario puede ignorar sin consecuencias. Las preguntas no bloquean el flujo.

---

# 12. Modificaciones y Branching

## 12.1 Principio

El usuario nunca modifica código directamente. Modifica **intenciones**.

## 12.2 Flujo de Modificación

**Paso 1: Usuario expresa intención en lenguaje natural**

"Una tarea debería poder tener varios asignados"

**Paso 2: Goal Interpreter clasifica el cambio**

1. Ajuste de parámetro (simple)
2. Cambio de comportamiento (localizado)
3. Cambio estructural (múltiples módulos)
4. Cambio de alcance (nueva funcionalidad grande)
5. Cambio de dirección (proyecto fundamentalmente distinto)

**Paso 3: Detección de ambigüedades**

Si hay ambigüedades, se preguntan **todas juntas** (no una a la vez) con ejemplos de impacto.

**Paso 4: Generación de variante**

Para cambios de categoría 3+, SODA **siempre crea una rama**:

- Versión "main" queda intacta
- Se crea rama con la modificación
- Ambas versiones se construyen
- Ambas versiones corren simultáneamente (puertos distintos)

**Paso 5: Contraste pragmático**

Impact Analyzer ejecuta ambas versiones y mide:
- Benchmarks comparativos
- Cobertura de casos de uso
- Complejidad de migración
- Escenarios adversariales

Presenta comparación visual al usuario.

**Paso 6: Decisión del usuario**

- Adoptar la variante (reemplaza main)
- Mantener la actual
- Seguir explorando

## 12.3 Gestión de Múltiples Variantes

El usuario puede tener múltiples ramas exploratorias simultáneas:

```
🌳 ÁRBOL DE VERSIONES DE TeamTasks

main (activa)
├── multi-asignados          [🟢 Lista para comparar]
├── con-subtareas            [⚙️ Construyendo...]
└── sin-login                [💭 Descartada ayer]
```

**Política:** ramas descartadas se archivan tras 7 días de inactividad. Ramas activas se mantienen hasta que el usuario decida.

## 12.4 Barreras Anti-Huérfanos

Estructuralmente implementadas, no remediales:

**Barrera 1 (Generación):** código se genera solo con goal_id válido. Sin goal_id, no hay generación.

**Barrera 2 (Validación):** pre-commit hook ejecuta test bidireccional (código ↔ árbol). Sin éxito, no hay commit.

**Barrera 3 (Modificación):** cambios al árbol disparan cleanup transaccional. Todo o nada.

**"Casi huérfanos":** hash semántico detecta código desincronizado con objetivo actualizado. Se regenera automáticamente o se pregunta al usuario si hay decisiones involucradas.

---

# 13. Integridad y Monitoreo

## 13.1 Context Health Monitor

Observa señales objetivas de fatiga:

1. Tamaño de contexto cercano al límite
2. Tasa de errores creciente en tareas similares
3. Respuestas incoherentes con estado actual
4. Ciclos de reescritura sin convergencia
5. Tiempo de respuesta creciente

## 13.2 Niveles de Respuesta

**Nivel 1: Observación**
- Una señal moderada aislada
- Log interno, sin acción visible

**Nivel 2: Auto-optimización**
- Dos señales o una crítica
- Sistema resuelve automáticamente:
  - Re-evalúa contexto necesario
  - Resume historiales viejos
  - Purga heurísticas no usadas
  - Re-indexa ChromaDB
- Mensaje mínimo al usuario

**Nivel 3: Sugerencia**
- Tres+ señales o Nivel 2 falló
- Propone al usuario:
  - Limpieza moderada (rápida)
  - Refundación de contexto (más profunda)
  - Posponer

**Nivel 4: Intervención obligada**
- Contexto excede límite técnico del modelo
- No se puede continuar
- Usuario debe decidir refundación

## 13.3 Refundación de Proyecto

Cuando se requiere, el proceso:

1. Snapshot completo del proyecto (backup)
2. Extracción de activos reutilizables (código, árbol actual, datos)
3. Filtrado de aprendizajes (descarta contexto obsoleto)
4. Creación de nuevo proyecto con contexto limpio
5. Verificación de equivalencia (tests del original pasan en el nuevo)
6. Registro en Project Lineage
7. Activación del nuevo proyecto

El usuario final no ve diferencia. El sistema detrás "rejuvenece".

## 13.4 Project Lineage

Cada refundación queda registrada:

```
📜 Historial:

├─ TeamTasks v1 (archivado)
│  └─ Creado: 2026-01-15 / Refundado: 2026-03-10
│  └─ Motivo: contexto sobrepasó límite
│
└─ TeamTasks v2 (actual)
   └─ Creado: 2026-03-10 (desde v1)
```

---

# 14. Comunicación Externa

## 14.1 Filosofía

SODA no es solo un editor, es un asistente persistente. Puede acompañar al usuario fuera de la sesión activa de desarrollo, **siempre respetando su atención**.

**Regla de oro:** nunca interrumpir por canal externo algo que no requiera decisión del usuario.

## 14.2 Canales

**UI Web (default):**
- Siempre activo cuando SODA está abierto
- Todas las interacciones

**Telegram (implementación inicial):**
- API oficial gratuita
- Setup simple (BotFather)
- Ideal para notificaciones + decisiones rápidas

**WhatsApp (planificado fase posterior):**
- Requiere API oficial de Meta (costo)
- Setup complejo
- Se implementa cuando haya demanda real

## 14.3 Qué Va por Canal Externo

**Sí envía:**
- Preguntas de ambigüedad con 2-3 opciones claras
- Checkpoints simples de aprobación
- Alertas de errores escalados
- Confirmación de proyectos completados
- Respuestas a consultas iniciadas por el usuario

**No envía (requiere pantalla):**
- Revisión del árbol de objetivos
- Comparación de variantes de branching
- Revisión de código
- Setup inicial de proyecto
- Configuraciones complejas

## 14.4 Autenticación

Pairing inicial (QR o código) desde la UI de escritorio. Confirmación en 2 pasos para acciones destructivas (deploy a producción, eliminación de proyecto).

---

# 15. Interfaz de Usuario

## 15.1 Tecnología

**Ventana nativa:** pywebview (envuelve contenido web en app de escritorio)
**Frontend:** HTML + CSS + JavaScript
**Editor de código:** Monaco Editor embebido
**Comunicación con backend:** WebSocket
**Backend:** FastAPI

## 15.2 Layout Principal

```
┌──────────────────────────────────────────────────────────────┐
│  [SODA] Proyecto: TeamTasks          [🔔] [⚙️] [👤]          │
├──────────┬───────────────────────────────────┬──────────────┤
│          │                                   │              │
│  Árbol   │      Editor / Panel activo        │  Panel de    │
│  de      │                                   │  progreso    │
│ Objetiv. │   [Monaco Editor]                 │              │
│          │                                   │  - Módulos   │
│  ├─ 📦   │                                   │    en curso  │
│  ├─ 🎯   │                                   │  - Tests     │
│  │  ├─ ▪ │                                   │  - Errores   │
│  │  └─ ▪ │                                   │  - Est. time │
│  ├─ 🎯   │                                   │              │
│  └─ ➕   │                                   │              │
│          │                                   │              │
├──────────┴───────────────────────────────────┴──────────────┤
│  Project Chat: [texto input...]            [Enviar]         │
│  > Usuario: ¿Cómo va el módulo de auth?                     │
│  > SODA: Completo. 3 tests pasando. 0 advertencias.         │
└──────────────────────────────────────────────────────────────┘
```

## 15.3 Vistas / Pestañas

**Pestaña principal:** Código + árbol + progreso (como arriba)

**Pestaña Árbol:** vista expandida del árbol de objetivos, interactivo

**Pestaña Perfiles:** gestión de perfiles + estadísticas

**Pestaña Skills:** visualización de skills activas (informativo)

**Pestaña Chat:** Project Chat expandido

**Pestaña Historial:** Project Lineage + versiones/branches

**Pestaña Configuración:** API keys, preferencias, canales externos

---

# 16. Stack Técnico Completo

## 16.1 Lenguajes y Runtime

- **Python 3.11+** (async con asyncio)
- **JavaScript** (ES6+) para frontend
- **HTML5 + CSS3** para UI

## 16.2 Librerías Python Principales

**Web/API:**
- `fastapi` - servidor principal
- `uvicorn` - ASGI server
- `websockets` - comunicación en tiempo real
- `pywebview` - empaquetado como app de escritorio

**IA/ML:**
- `anthropic` - SDK Claude
- `google-generativeai` - SDK Gemini
- `ollama` - cliente Ollama
- `chromadb` - base vectorial

**Infraestructura:**
- `docker` - SDK Docker
- `watchdog` - monitor de archivos
- `pygithub` - GitHub API
- `gitpython` - operaciones Git locales

**Procesamiento de documentos:**
- `unstructured` - parsing multi-formato
- `pypdf` - PDFs
- `python-docx` - Word

**Comunicación externa:**
- `python-telegram-bot` - Telegram
- (futuro) `twilio` o `whatsapp-business-api-client` - WhatsApp

**Utilidades:**
- `pydantic` - validación de datos
- `sqlalchemy` - ORM (para SQLite/PostgreSQL)
- `rich` - logs bonitos en consola

## 16.3 Librerías Frontend

- **Monaco Editor** (CDN o local)
- **D3.js** o **Cytoscape.js** - para árbol de objetivos interactivo
- **Mermaid.js** - diagramas de arquitectura

## 16.4 Infraestructura

- **Docker Desktop** (sobre WSL2)
- **PostgreSQL** (dentro de Docker, cuando proyectos lo requieran)
- **Redis** (dentro de Docker, para jobs async de proyectos)

## 16.5 Servicios Externos

- **GitHub** - control de versiones
- **Anthropic API** - Claude
- **Google AI Studio API** - Gemini
- **Ollama** (local, no externo)
- **SendGrid/Resend** (opcional, para proyectos que los usen)

---

# 17. Estructura de Archivos

```
soda/
├── pyproject.toml                  # uv project config
├── .env.example                    # template de variables
├── .env                            # secrets (no commiteado)
├── README.md
│
├── kernel/                         # EL KERNEL DE SODA
│   ├── __init__.py
│   ├── orchestrator.py             # Orchestrator principal
│   ├── dependency_graph.py         # DAG de módulos
│   ├── docker_sandbox.py           # Ejecución aislada
│   ├── watchdog_mgr.py             # Monitor archivos + backups
│   ├── git_manager.py              # GitHub + git local
│   │
│   ├── context/
│   │   ├── context_builder.py      # ContextBuilder central
│   │   └── token_counter.py
│   │
│   ├── knowledge/
│   │   ├── knowledge_orchestrator.py
│   │   ├── chromadb_manager.py
│   │   ├── heuristics.py
│   │   └── document_ingestion.py
│   │
│   ├── intelligence/
│   │   ├── wisdom_agent.py
│   │   ├── goal_interpreter.py
│   │   ├── impact_analyzer.py
│   │   └── reference_analyzer.py
│   │
│   ├── integrity/
│   │   ├── goal_integrity_validator.py
│   │   ├── context_health_monitor.py
│   │   └── project_lineage.py
│   │
│   ├── capabilities/
│   │   ├── skill_manager.py
│   │   ├── skill_matcher.py
│   │   ├── profile_manager.py
│   │   ├── profile_matcher.py
│   │   └── profile_evolution.py
│   │
│   ├── communication/
│   │   ├── messaging_gateway.py
│   │   ├── project_chat.py
│   │   └── channels/
│   │       ├── telegram_channel.py
│   │       └── whatsapp_channel.py  # futuro
│   │
│   └── drivers/
│       ├── claude_driver.py
│       ├── gemini_driver.py
│       └── ollama_driver.py
│
├── ui/                             # INTERFAZ
│   ├── server.py                   # FastAPI app
│   ├── websocket_handler.py
│   ├── launcher.py                 # pywebview starter
│   │
│   └── static/
│       ├── index.html
│       ├── css/
│       │   └── styles.css
│       └── js/
│           ├── app.js
│           ├── tree_view.js
│           ├── project_chat.js
│           └── vendor/
│               ├── monaco/
│               └── cytoscape/
│
├── prompts/                        # SYSTEM PROMPTS
│   ├── claude/
│   │   ├── requirements_interviewer.md
│   │   ├── architecture_auditor.md
│   │   ├── debugger.md
│   │   ├── goal_interpreter.md
│   │   └── integration_auditor.md
│   │
│   ├── gemini/
│   │   ├── global_architect.md
│   │   ├── skill_matcher.md
│   │   ├── profile_matcher.md
│   │   ├── wisdom_agent.md
│   │   ├── reference_analyzer.md
│   │   └── final_integrator.md
│   │
│   └── ollama/
│       ├── code_generator.md
│       ├── code_reviewer.md
│       ├── test_generator.md
│       └── optimizer.md
│
├── skills/                         # CATÁLOGO DE SKILLS
│   ├── base/                       # Skills genéricas iniciales
│   │   ├── general_development/
│   │   ├── web_fullstack/
│   │   ├── backend_api/
│   │   ├── mobile_app/
│   │   └── data_engineering/
│   │
│   └── custom/                     # Skills generadas/cargadas
│       └── [se van creando]
│
├── profiles/                       # PERFILES
│   ├── base/                       # Perfiles base iniciales
│   │   ├── general_developer/
│   │   ├── web_fullstack/
│   │   └── backend_api/
│   │
│   └── custom/                     # Perfiles generados
│       └── [evolucionan con uso]
│
├── projects/                       # WORKSPACES DE PROYECTOS
│   └── [proyecto_xxx]/
│       ├── metadata.json
│       ├── blueprint.json
│       ├── goal_tree.json
│       ├── contracts.json
│       ├── source/                 # código del proyecto
│       ├── tests/
│       ├── docs/
│       ├── chromadb/               # RAG del proyecto
│       ├── backups/                # snapshots
│       ├── branches/               # variantes (branching)
│       └── logs/
│
├── data/                           # DATOS GLOBALES
│   ├── heuristics.db               # SQLite heurísticas
│   ├── chromadb_profiles/          # vectores de profiles
│   ├── chromadb_skills/            # vectores de skills
│   ├── lineage.db                  # project lineage
│   └── usage_analytics.db
│
├── tests/                          # tests de SODA mismo
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
└── scripts/                        # utilidades
    ├── setup_environment.sh
    ├── pull_models.sh              # descarga modelos Ollama
    ├── backup_soda.sh
    └── reset_development.sh
```

---

# 18. Roadmap de Implementación

## Fase A: Fundamentos (Semana 1-2)

**Objetivo:** poder hacer una llamada end-to-end simple.

**Tareas:**
1. Setup de entorno (WSL2, uv, Ollama, Cursor)
2. Estructura básica de proyecto
3. Driver de Claude (1 llamada funcional)
4. Driver de Ollama (1 llamada funcional)
5. Driver de Gemini (1 llamada funcional)
6. ContextBuilder versión mínima
7. Test manual: pedido → 3 modelos → respuestas

**Entregable:** CLI simple que prueba los 3 drivers.

## Fase B: Kernel Core (Semana 3-5)

**Objetivo:** ciclo de vida básico funcional (secuencial).

**Tareas:**
1. Orchestrator con máquina de estados básica
2. DependencyGraph simple
3. DockerSandbox funcional
4. Watchdog + backups atómicos
5. GitManager básico
6. Goal Integrity Validator (barreras anti-huérfanos)
7. Primer proyecto end-to-end: "app CRUD simple"

**Entregable:** puede construir un CRUD desde descripción, sin UI aún.

## Fase C: UI y Conocimiento (Semana 6-8)

**Objetivo:** interfaz visual + memoria persistente.

**Tareas:**
1. FastAPI server + WebSocket
2. Monaco Editor integrado
3. pywebview wrapper
4. ChromaDB para Project RAG
5. Knowledge Orchestrator básico
6. Panel de progreso en tiempo real
7. Árbol de objetivos (vista, no interactivo aún)

**Entregable:** SODA como app de escritorio con UI funcional.

## Fase D: Skills y Perfiles Base (Semana 9-11)

**Objetivo:** sistema de capacidades activo.

**Tareas:**
1. Skill Manager + estructura de skills
2. Skill Matcher con Gemini Pro
3. Profile Manager + perfiles base
4. Profile Matcher automático
5. Integración con ContextBuilder
6. 5-8 perfiles base pre-hechos
7. 15-20 skills base pre-hechas

**Entregable:** SODA asigna automáticamente equipo para cada proyecto.

## Fase E: Inteligencia Avanzada (Semana 12-14)

**Objetivo:** comportamiento proactivo y crítico.

**Tareas:**
1. Wisdom Agent
2. Goal Interpreter
3. Impact Analyzer (sin branching aún)
4. Reference Analyzer
5. Context Health Monitor
6. Project Chat
7. Árbol de objetivos interactivo

**Entregable:** SODA como "agencia" con comportamiento inteligente.

## Fase F: Branching y Evolución (Semana 15-17)

**Objetivo:** variantes y aprendizaje acumulativo.

**Tareas:**
1. Branching con contraste pragmático
2. Multi-branch management
3. Profile Evolution Engine
4. Consolidación automática de aprendizajes
5. Project Lineage
6. Refundación de proyectos

**Entregable:** SODA que mejora con el uso.

## Fase G: Comunicación Externa (Semana 18-19)

**Objetivo:** accesibilidad desde cualquier lugar.

**Tareas:**
1. Messaging Gateway
2. Telegram Bot integration
3. Autenticación cross-device
4. Notificaciones inteligentes

**Entregable:** SODA accesible desde celular.

## Fase H: Pulido y Optimización (Semana 20+)

**Objetivo:** producto maduro.

**Tareas:**
1. Testing exhaustivo
2. Optimización de contextos con datos reales
3. Calibración de umbrales (Health Monitor)
4. Mejora de prompts basada en uso
5. Documentación completa
6. Posibles features adicionales (WhatsApp, marketplace de perfiles, etc.)

**Entregable:** SODA 1.0 listo.

---

# 19. Paso a Paso de Ejecución

Esta sección es la guía práctica para empezar a construir.

## Paso 1: Preparación del Entorno (Día 1)

**1.1 Instalar WSL2 con Ubuntu**

En PowerShell como administrador:
```powershell
wsl --install -d Ubuntu
```

Reiniciar, crear usuario en Ubuntu.

**1.2 Dentro de WSL2, instalar dependencias base**

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential curl git
```

**1.3 Instalar uv (gestor de Python)**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

**1.4 Instalar Docker**

Descargar Docker Desktop para Windows, activar integración con WSL2 en settings.

Verificar en WSL2:
```bash
docker --version
docker run hello-world
```

**1.5 Instalar Ollama**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**1.6 Instalar Cursor**

Descargar de cursor.com, instalar en Windows. Abrir extensión de WSL y conectarse a Ubuntu.

## Paso 2: Setup del Proyecto SODA (Día 1)

**2.1 Crear estructura inicial**

```bash
cd ~
mkdir soda && cd soda
uv init .
uv python install 3.11
uv venv
```

**2.2 Crear estructura de carpetas**

```bash
mkdir -p kernel/{context,knowledge,intelligence,integrity,capabilities,communication,drivers}
mkdir -p ui/static/{css,js}
mkdir -p prompts/{claude,gemini,ollama}
mkdir -p skills/{base,custom}
mkdir -p profiles/{base,custom}
mkdir -p projects data tests scripts
```

**2.3 Instalar dependencias**

```bash
uv add fastapi uvicorn websockets pywebview
uv add anthropic google-generativeai ollama chromadb
uv add docker watchdog pygithub gitpython
uv add pydantic sqlalchemy rich python-telegram-bot
uv add pypdf python-docx unstructured
```

**2.4 Configurar variables de entorno**

Crear `.env`:
```bash
ANTHROPIC_API_KEY=tu_key_aqui
GEMINI_API_KEY=tu_key_aqui
GITHUB_TOKEN=tu_token_aqui
OLLAMA_BASE_URL=http://localhost:11434
```

## Paso 3: Descargar Modelos (Día 1, background)

```bash
ollama pull qwen2.5-coder:14b
ollama pull qwen2.5-coder:7b  
ollama pull deepseek-coder-v2:16b
```

Esto tarda según tu conexión. Mientras, seguir con código.

## Paso 4: Primer Driver (Día 2-3)

Empezar con el driver más simple: Claude.

**4.1 Crear `kernel/drivers/claude_driver.py`**

```python
import os
from anthropic import AsyncAnthropic
from typing import Optional

class ClaudeDriver:
    def __init__(self):
        self.client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-5-20250929"
    
    async def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096
    ) -> str:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text
```

**4.2 Test básico**

Crear `scripts/test_claude.py`:
```python
import asyncio
from kernel.drivers.claude_driver import ClaudeDriver

async def main():
    driver = ClaudeDriver()
    response = await driver.call(
        system_prompt="Eres un asistente útil y conciso.",
        user_message="Explicá qué es un DAG en 2 frases."
    )
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

Ejecutar: `uv run scripts/test_claude.py`

Si funciona, seguimos. Si no, debugging.

## Paso 5: Drivers Ollama y Gemini (Día 3-4)

Replicar el patrón con los otros dos drivers. Tests análogos.

## Paso 6: ContextBuilder Mínimo (Día 5)

**6.1 Crear `kernel/context/context_builder.py`**

Versión inicial simple que solo concatena, sin RAG aún:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Context:
    system: str
    task: str
    additional_info: Optional[str] = None
    
    def to_prompt(self) -> dict:
        user_msg = self.task
        if self.additional_info:
            user_msg = f"{self.additional_info}\n\nTarea: {self.task}"
        return {
            "system": self.system,
            "user": user_msg
        }

class ContextBuilder:
    def __init__(self):
        self.token_budget = {
            "qwen_coder_14b": 4000,
            "claude_sonnet": 8000,
            "gemini_pro": 50000
        }
    
    def build(self, role: str, task: str, **kwargs) -> Context:
        # Cargar system prompt según rol
        with open(f"prompts/{self._get_prompt_path(role)}", "r") as f:
            system = f.read()
        
        return Context(
            system=system,
            task=task,
            additional_info=kwargs.get("context", None)
        )
    
    def _get_prompt_path(self, role: str) -> str:
        mapping = {
            "requirements_interviewer": "claude/requirements_interviewer.md",
            "code_generator": "ollama/code_generator.md",
            # ... etc
        }
        return mapping[role]
```

## Paso 7: Primer Orchestrator (Día 6-8)

Orchestrator mínimo que encadene una llamada:

```python
class Orchestrator:
    def __init__(self):
        self.claude = ClaudeDriver()
        self.context_builder = ContextBuilder()
    
    async def interview_user(self, user_description: str) -> dict:
        context = self.context_builder.build(
            role="requirements_interviewer",
            task=user_description
        )
        
        response = await self.claude.call(
            system_prompt=context.system,
            user_message=context.task
        )
        
        # Parsear respuesta (JSON esperado según prompt)
        import json
        return json.loads(response)
```

Test: descripción → entrevista → blueprint básico.

## Paso 8: Iterar hacia el MVP (Semana 2-5)

Siguiendo el roadmap, ir agregando componentes uno a uno:

1. DockerSandbox + validación básica
2. DependencyGraph
3. Generación de código con Qwen
4. Goal Integrity Validator
5. Loop: requirements → architecture → code → validate

**Criterio de MVP:** que pueda construir una app CRUD simple desde descripción en lenguaje natural, con código funcional al final.

## Paso 9: Agregar UI (Semana 6-8)

Primer setup de FastAPI + pywebview + Monaco:

```python
# ui/launcher.py
import webview
from ui.server import app
import threading
import uvicorn

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    webview.create_window("SODA", "http://127.0.0.1:8000", width=1400, height=900)
    webview.start()
```

Iterar sobre la UI hasta tener: árbol visible, progreso en tiempo real, editor de código.

## Paso 10: Sistema de Perfiles (Semana 9-11)

Primera versión de perfiles base:

```bash
mkdir -p profiles/base/general_developer
```

Crear `profiles/base/general_developer/identity.yaml`:
```yaml
name: "General Developer"
description: "Perfil genérico para desarrollo estándar"
expertise_areas:
  primary: [general_software_development]
experience_level: junior
applies_to_roles:
  arquitecto_global: full
  arquitecto_modulo: full
  generador_codigo: full
  revisor: full
```

Ir armando 5-8 perfiles base con configuraciones simples.

Implementar Profile Matcher que los asigne automáticamente.

## Paso 11: Inteligencia Avanzada (Semana 12-14)

Agregar Wisdom Agent, Goal Interpreter, Impact Analyzer.

Integrar en el flujo principal.

## Paso 12: Probar con Proyecto Real (Semana 15+)

Usar SODA para construir algo real. Observar dónde falla, qué funciona, qué no.

**Iterar sobre todo lo anterior basándose en aprendizajes reales.**

---

# 20. Criterios de Éxito y Riesgos

## 20.1 Criterios de Éxito del MVP

SODA v1 (fin de Fase E) se considera exitoso si:

1. Puede generar un proyecto CRUD simple (auth + DB + API + frontend básico) en menos de 30 minutos
2. El costo en APIs paga es menor a USD 3 por proyecto típico
3. La tasa de intervención humana (más allá de checkpoints) es menor al 25%
4. El código generado pasa linting y tests automáticos sin intervención en al menos 70% de los casos
5. La asignación automática de perfiles/skills funciona correctamente en al menos 80% de los proyectos
6. No se generan huérfanos (tolerancia: 0)

## 20.2 Criterios de Madurez (SODA 1.0)

SODA 1.0 (fin de Fase H) se considera maduro si:

1. Los perfiles han acumulado experiencia significativa (10+ proyectos cada uno de los más usados)
2. Las heurísticas consolidadas aportan mejoras medibles respecto al sistema sin ellas
3. El Context Health Monitor rara vez dispara Nivel 3+ (umbrales bien calibrados)
4. El sistema puede proponer mejoras a sus propios perfiles basándose en patrones observados
5. La experiencia de usuario es fluida (los checkpoints no se sienten intrusivos)
6. El costo promedio se ha reducido vs el MVP por mejor caching y optimizaciones

## 20.3 Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Modelos locales insuficientes para tareas complejas | Media | Alto | Escalado automático a Claude; ajuste de umbrales |
| Contextos crecen sin control | Media | Alto | ContextBuilder centralizado + Health Monitor + logging obligatorio |
| Conflictos en paralelismo | Baja | Alto | Aislamiento estricto + locks en escritura + Kernel como único escritor |
| Perfiles mal construidos contaminan proyectos | Media | Alto | Validación de perfiles antes de consolidar + rollback posible |
| API keys comprometidas | Baja | Alto | Variables de entorno + .gitignore + rotación periódica |
| Cambios en APIs externas (Claude, Gemini) | Alta | Medio | Drivers aislados; SDK oficiales; versionado de modelo |
| Costo de APIs se dispara | Media | Medio | Monitor de gasto + alertas + escalado condicional |
| UI compleja abruma al usuario | Media | Medio | Defaults inteligentes; detalles técnicos colapsados; onboarding gradual |
| Goal Integrity falla y aparecen huérfanos | Baja | Alto | Tests bidireccionales rigurosos; bloqueo de commits sin validación |
| Docker Desktop inestable en Windows | Media | Medio | WSL2 bien configurado; documentación de troubleshooting |
| Ollama se cuelga con paralelismo | Media | Medio | Timeout por request; reinicio automático; fallback a secuencial |
| Complejidad total del sistema inmanejable | Media | Alto | **Roadmap por fases**; validación empírica antes de avanzar; resistencia a agregar features |

## 20.4 Señales Tempranas de Problemas

Monitorear durante el desarrollo:

- Tiempo de respuesta de modelos creciendo sostenidamente
- Tasa de escalados a Claude creciendo (indica que los locales no alcanzan)
- Usuario interrumpiendo más que los checkpoints (indica UX fallando)
- Contextos superando presupuestos (indica ContextBuilder o Health Monitor fallando)
- Perfiles acumulando información contradictoria (indica Profile Evolution fallando)

Cualquiera de estas señales debe disparar investigación y ajuste antes de continuar agregando features.

## 20.5 Principios de Resistencia al Scope Creep

Durante el desarrollo, recordar:

1. **El MVP es el MVP.** No agregar features fuera de las 5 primeras fases.
2. **Validar antes de construir.** Cada fase termina con proyecto real probado.
3. **La arquitectura permite agregar después.** No es necesario implementar todo para que el diseño funcione.
4. **Simplicidad > completitud inicial.** Prefiere código menos elegante que funciona y se puede mejorar.
5. **Mide, no adivines.** Decisiones de optimización deben basarse en datos reales del sistema funcionando.

---

# Apéndice A: Glosario

**Agente:** instancia de un modelo de IA trabajando en un rol específico con contexto aislado.

**Branching pragmático:** crear ramas del proyecto para comparar variantes funcionando, no solo código.

**Checkpoint:** momento de validación obligatoria del usuario.

**ContextBuilder:** componente central que arma contextos mínimos para cada llamada a IA.

**Goal integrity:** propiedad del sistema donde todo código tiene objetivo y todo objetivo tiene código.

**Heurística:** "regla de oro" aprendida por el sistema.

**Huérfano:** código sin objetivo que lo justifique (estructura prohibida en SODA).

**Kernel:** el cerebro determinístico de Python que coordina todo.

**Perfil:** agrupación coherente de skills + conocimiento + experiencia que actúa como "especialista".

**Profile Evolution:** mecanismo por el cual los perfiles acumulan experiencia y mejoran.

**RAG:** Retrieval-Augmented Generation. Recuperar información relevante antes de generar.

**Skill:** unidad atómica de capacidad (conocimiento + ejemplos + checklist).

**Wisdom Agent:** componente que genera preguntas proactivas basándose en experiencia.

---

# Apéndice B: Decisiones Clave Tomadas

Resumen de decisiones importantes para consultar:

1. **Coordinación por código**, no por IA. Coordinadores no existen como agentes.
2. **Modelos locales para volumen, APIs para juicio.** Estrategia de costos inteligente.
3. **Cursor + WSL2 + uv** como entorno de desarrollo.
4. **Monaco + pywebview + FastAPI** como stack de interfaz.
5. **Telegram antes que WhatsApp** para comunicación externa.
6. **Skills generadas con aprobación del usuario** (no en background silencioso).
7. **Perfiles asignados automáticamente por la IA**, no por el usuario.
8. **Perfiles arrancan genéricos** y se especializan con uso.
9. **Branching siempre para cambios grandes**, con contraste pragmático (ejecución real).
10. **Barreras anti-huérfanos estructurales**, no limpieza reactiva.
11. **Context Health Monitor basado en señales objetivas** de fatiga, no en métricas abstractas.
12. **Project Chat como pestaña**, no ventana flotante.
13. **Preguntas proactivas sugeridas, no bloqueantes.**
14. **Referencias bajo demanda**, no biblioteca permanente.
15. **Referencias cerradas: LLM + material opcional del usuario.**

---

# Final

Este documento es el plan consolidado de SODA v3. Es ambicioso pero está estructurado en fases alcanzables. La clave del éxito no está en implementar todo de una vez, sino en validar cada fase empíricamente antes de avanzar a la siguiente.

**Próximo paso concreto:** arrancar con el Paso 1 del punto 19 (Preparación del Entorno). Si eso funciona, seguir con el Paso 2. Si aparece fricción, resolver antes de avanzar.

El sistema está diseñado para ser construido incrementalmente. No hay etapas que requieran "todo listo de una". Cada fase produce algo funcional.

Cuando empieces a implementar, el documento puede evolucionar. Tratalo como guía viva, no como especificación inmutable. Si algo se descubre imposible o innecesario, ajustar. Si algo nuevo se revela necesario, incorporar.

Suerte.
