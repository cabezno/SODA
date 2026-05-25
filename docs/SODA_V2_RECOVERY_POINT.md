# SODA V2 - RECOVERY POINT & ARCHITECTURE GUIDE
*Fecha de Consolidación: 28 de Abril de 2026*

Este documento es el Punto de Recuperación Activo de SODA V2. Define la arquitectura estricta del **Compilador de Contratos Recursivo (AST-like)** que reemplazó al pipeline lineal original.

## 1. Topología del Sistema

El corazón de SODA V2 es el `SodaRecursiveEngine` (`kernel/orchestration/recursive_engine.py`), el cual opera de forma aislada e inyecta telemetría/guardado mediante el patrón de **Delegación (Callbacks)** (`notify_fn`, `save_file_fn`).

### Modelos Base (`kernel/core/models_v2.py`)
Todo el sistema se comunica usando un único esquema Pydantic: `SodaContract`.
- `contract_id`: Identificador único.
- `is_atomic`: Booleano que define si el nodo requiere mayor descomposición (`False`) o si ya es implementable en código (`True`).
- `interface`: Entradas y salidas usando `abstract_type`.
- `dynamic_persona`: Roles y skills exigidas para la ejecución.

## 2. El Pipeline de 5 Capas

SODA V2 delega el trabajo cognitivo estrictamente a **Gemini** (Lógica y QA) y a **Qwen** (Escritura de código puro).

1. **Capa 1: Génesis (`kernel/orchestration/genesis.py`)**
   - Transforma el prompt humano libre en el contrato raíz `ROOT-000` (`is_atomic: False`). Inyecta un Python Firewall para evitar alucinaciones en el nivel base.
2. **Capa 2: Analista (Descomposición Top-Down)**
   - Gemini toma nodos no atómicos y los divide recursivamente. 
   - *Validación:* `TopologyValidator` (evita ciclos DAG) y `DataFlowValidator` (asegura que las dependencias provean los inputs requeridos).
3. **Capa 3: Líder Técnico (Traducción Bottom-Up)**
   - Inicia cuando todos los nodos hoja son atómicos. 
   - Traduce los tipos abstractos (ej. `Collection(User)`) a sintaxis nativa (ej. `Array<User>`) según el stack tecnológico inferido de las `ALLOWED_SKILLS`.
4. **Capa 4: Coder (Qwen Local)**
   - Recibe el contrato técnico y genera **Únicamente Código Fuente**.
   - *Validación Estricta:* El `PolyglotValidator` (`kernel/validators/v2/polyglot_validator.py`) verifica mediante AST (para Python) o Regex (para JS/Go/Rust) que todas las funciones exigidas en el contrato existan en el texto generado.
5. **Capa 5: Auditor QA**
   - Gemini audita el código generado por Qwen contra el contrato. Si falla, el feedback se inyecta en la Capa 4 para un reintento (Stage-Gating).

## 3. Adaptadores de Retrocompatibilidad (`kernel/utils/v2_adapters.py`)

Para evitar romper el Ecosistema UI, DockerSandbox y BootAgent, el Orquestador ejecuta `generate_legacy_artifacts()` al finalizar el árbol V2. Esto "falsifica" los antiguos `blueprint.json` y `topology.json` extrayendo la información del `soda_v2_tree.json`.

## Reglas Críticas para Futuros Agentes de IA:
1. **NO modifiques el Motor Recursivo** para añadir lógicas de I/O (rutas de carpetas, bases de datos). Usa siempre Callbacks.
2. **Polyglot Validator:** Si agregas un nuevo lenguaje esotérico, actualiza el fallback Regex en `polyglot_validator.py`. No uses `ast` de Python para lenguajes externos.
3. **ALLOWED_SKILLS:** Cualquier nueva tecnología debe registrarse explícitamente en el set `ALLOWED_SKILLS` en `models_v2.py` o Pydantic abortará el pipeline en el Paso 1.
