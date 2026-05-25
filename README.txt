SODA V2 (Software Orchestration & Development Agency)
===================================================

SODA es un framework multi-agente diseñado para la generación automatizada de software de alta calidad. 
La versión 2.0 introduce un "Compilador de Contratos Recursivo" (AST-like), abandonando la aproximación lineal en favor de un enfoque de árbol topológico estricto (Stage-Gating).

# Arquitectura General

El sistema se compone de 5 Capas principales gobernadas por el `SodaRecursiveEngine`:
- CAPA 1 (Génesis): Gemini convierte lenguaje natural a un contrato raíz `ROOT-000`.
- CAPA 2 (Analista): Descomposición recursiva del contrato en nodos atómicos (con validación de Topología y DataFlow).
- CAPA 3 (Tech Lead): Traducción de tipos abstractos a la sintaxis del proyecto (Python, TypeScript, Go, etc.).
- CAPA 4 (Coder): Qwen 14B escribe el código puro que cumple estrictamente el contrato (Validado por Regex/AST).
- CAPA 5 (QA): Gemini inspecciona y aprueba/rechaza el código.

# Componentes Clave
- UI / Frontend: Interfaz gráfica que corre en localhost (React / pywebview).
- Docker Sandbox: Entorno donde el código generado es evaluado empíricamente.
- Orquestador: Actúa como el puente de entrada y salida, inyectando telemetría al motor algorítmico sin acoplarse a él.

# Ejecución
Lanzar la interfaz principal:
$ python -m ui.launcher

# Recuperación y Documentación de Arquitectura
Para un entendimiento técnico profundo del flujo de datos interno, referirse al documento:
`docs/SODA_V2_RECOVERY_POINT.md`
