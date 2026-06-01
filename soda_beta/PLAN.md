# SODA BETA: PLAN DE EJECUCIÓN MAESTRO (TEACHER-STUDENT PARADIGM)
================================================================================

Este documento define la hoja de ruta y el diseño arquitectónico de **SODA Beta (SODA Learner)**. Su objetivo es observar el funcionamiento de SODA FUSION (el "Profesor"), registrar sus trazas de éxito, errores y correcciones, destilar ese conocimiento de manera estructurada y usarlo para entrenar un ecosistema de SLMs locales ultra-especializados capaces de actuar de manera autónoma en su propio espacio de trabajo con recursos de hardware locales optimizados.

---

## ─── FILOSOFÍA DE TRABAJO ───

La regla suprema de SODA Beta es: **"Observar y aprender pasivamente antes de actuar activamente en su propio entorno."**
Esto evita riesgos en tus proyectos reales de desarrollo y asegura que la IA local de SODA aprenda patrones empíricos y refinados específicos para tu stack y tus proyectos antes de tocar una sola línea de código en producción.

---

## ─── MAPA DE FASES Y COMPONENTES ───

```text
  Fase 1: Observatorio   ┌───────────────────────────────────────────────┐
   (Captura Pasiva)      │  SODA FUSION (Teacher) ───> Prompt/Code/Errors│
                         └──────────────────────┬────────────────────────┘
                                                │ (Interceptar)
                                                ▼
  Fase 2: Destilación    ┌───────────────────────────────────────────────┐
   (Dataset Builder)     │  soda_beta/observatory/data/                  │
                         │  - knowledge_traces.jsonl  - repair_traces.json│
                         └──────────────────────┬────────────────────────┘
                                                │ (Entrenamiento QLoRA)
                                                ▼
  Fase 3: Laboratorio    ┌───────────────────────────────────────────────┐
   (Fine-Tuning Local)   │  soda_beta/trainer/ (Unsloth / PEFT)         │
                         │  --> Genera adaptadores LoRA especializados   │
                         └──────────────────────┬────────────────────────┘
                                                │ (Carga en Caliente)
                                                ▼
  Fase 4: Inferencia     ┌───────────────────────────────────────────────┐
   (Motor Local SLM)     │  soda_beta/inference/ (Ollama / Llama.cpp)    │
                         │  --> Inferencia ágil con VRAM < 4GB           │
                         └──────────────────────┬────────────────────────┘
                                                │ (Acción)
                                                ▼
  Fase 5: Sandbox        ┌───────────────────────────────────────────────┐
   (Workspace de Acción) │  soda_beta/projects/ (Aislado para el Alumno) │
                         │  --> Compila, testea e itera localmente       │
                         └───────────────────────────────────────────────┘
```

---

## ─── DETALLE DE LAS FASES DE IMPLEMENTACIÓN ───

### FASE 1: EL OBSERVATORIO PASIVO (`soda_beta/observatory`)
**Objetivo:** Interceptar las llamadas y respuestas de SODA FUSION de forma totalmente no intrusiva (Shadow Mode) y guardarlas de forma estructurada.

*   **Paso 1.1: Creación del Directorio Raíz de SODA Beta**
    *   Estructura:
        ```text
        soda_beta/
        ├── PLAN.md (Este archivo)
        ├── observatory/
        │   ├── __init__.py
        │   ├── hooks.py          # Interceptores de llamadas de SODA
        │   └── data/             # Almacén de datasets de entrenamiento
        ├── projects/             # Workspace aislado para pruebas de la Beta
        ├── trainer/              # Scripts de Fine-Tuning local (QLoRA)
        └── inference/            # Motor de carga local de SLMs
        ```
*   **Paso 1.2: El `ObservatoryHook`**
    *   Crear un hook en `soda_beta/observatory/hooks.py` con métodos para registrar transacciones exitosas (`register_success`) y transacciones de reparación de código (`register_repair`).
*   **Paso 1.3: Conexión pasiva con SODA FUSION**
    *   Wired pasivo en `CodeGenerator.generate_file` y `WisdomAgent.analyze` para enviar una copia exacta de los prompts de entrada, los reportes de GBrain, el código resultante que compiló y el historial de linters/errores directamente al observatorio.

---

### FASE 2: DESTILACIÓN DE DATASET DE ALTA FIDELIDAD (`soda_beta/observatory/data`)
**Objetivo:** Transformar las observaciones crudas del Shadow Mode en datasets estructurados en formato `.jsonl` optimizados para fine-tuning.

*   **Paso 2.1: `knowledge_traces.jsonl` (Mapeo de Requerimiento a Código)**
    *   *Formato de Entrenamiento:*
        ```json
        {
          "instruction": "Escribe un módulo en {stack} que implemente {responsabilidad}. Contexto previo: {gbrain_context}",
          "input": "Archivo a generar: {filepath}\nEstructura de interfaces: {interfaz_a_implementar}",
          "output": "```\n{codigo_final_exitoso_que_compilo}\n```"
        }
        ```
*   **Paso 2.2: `repair_traces.jsonl` (Aprendizaje de Auto-Corrección)**
    *   *Formato de Entrenamiento:*
        ```json
        {
          "instruction": "Corrige el siguiente código que tiene un fallo de compilación.",
          "input": "Código Erróneo:\n{last_failed_code}\n\nError de Compilación:\n{last_error_reason}",
          "output": "```\n{codigo_corregido_que_paso_el_linter}\n```"
        }
        ```
*   **Paso 2.3: Validador de Calidad del Dataset**
    *   Filtrar rigurosamente los registros para asegurar que solo se guarden trazas donde el linter final dio estado `SUCCESS` y el código funcionó correctamente en el disco físico.

---

### FASE 3: PIPELINE DE ENTRENAMIENTO LOCAL (`soda_beta/trainer`)
**Objetivo:** Crear un script de fine-tuning automatizado que aproveche tu GPU RTX 5070 Ti para destilar el dataset en adaptadores LoRA ligeros.

*   **Paso 3.1: Configuración del Entorno de Entrenamiento Local**
    *   Utilizar librerías de aceleración local como `unsloth` (el motor más rápido del mundo en GPU para fine-tuning) o `peft` de HuggingFace optimizado para CUDA 12.8.
*   **Paso 3.2: El script `train_lora.py`**
    *   Script parametrizable que carga el modelo base **Qwen 2.5 Coder 1.5B** (o 0.5B), aplica cuantización de 4 bits (QLoRA) para no superar los 6GB de VRAM durante el entrenamiento, entrena con los datasets del Observatorio y genera:
        *   `soda_coder_lora/` (Adaptador de codificación estricta).
        *   `soda_repair_lora/` (Adaptador para corregir errores).

---

### FASE 4: MOTOR DE INFERENCIA LOCAL OPTIMIZADO (`soda_beta/inference`)
**Objetivo:** Ejecutar inferencias a la velocidad del rayo en tu GPU utilizando un solo modelo base cargando los LoRAs en caliente (Hot-Swapping) para no colapsar la VRAM.

*   **Paso 4.1: Integración con la API nativa de `llama.cpp`**
    *   Llamada a la API nativa de C++ o Go de llama.cpp para cargar el modelo base en VRAM (~1.5 GB).
*   **Paso 4.2: Hot-Swapping de Adaptadores**
    *   Implementar la lógica asíncrona de conmutación en caliente de adaptadores:
        *   Para escribir código: aplicar adaptador `soda_coder_lora`.
        *   Para auditar o corregir: descargar `soda_coder_lora` y aplicar `soda_repair_lora` en milisegundos.
*   **Paso 4.3: Telemetría de Inferencia Local**
    *   Monitoreo en consola de latencias de pre-procesamiento (Prefill ms), decoding speed (tokens/segundo) y ocupación de la memoria caché de tokens (KV Cache).

---

### FASE 5: EL ESPACIO DE TRABAJO INDEPENDIENTE (`soda_beta/projects`)
**Objetivo:** El "Laboratorio del Alumno". Un workspace 100% aislado de los proyectos de producción donde SODA Beta puede actuar activamente.

*   **Paso 5.1: Creación de la Carpeta de Proyectos Piloto**
    *   Workspace: `soda_beta/projects/`
*   **Paso 5.2: Motor de Ejecución Autónomo Local (`BetaRunner`)**
    *   Un script que toma un requerimiento experimental de prueba (ej: "Crear una pequeña API con FastAPI que valide HWID"), arranca el pipeline local usando tus SLMs entrenados, genera los archivos en `soda_beta/projects/temp_project/`, corre el linter y evalúa la tasa de éxito de compilación del código generado 100% en local.
*   **Paso 5.3: El Suite de Comparación**
    *   Herramienta analítica que toma un mismo requerimiento, lo ejecuta con SODA FUSION (Claude 3.5 en la nube) y con SODA Beta (SLM Local), compara la calidad del código, las líneas de código generadas, los errores sintácticos iniciales, y arroja métricas comparativas.

---

## ─── PROTOCOLO DE DESPLIEGUE INCREMENTAL ───

Para garantizar el cumplimiento de la filosofía de "no interferir y observar primero", estructuraremos el desarrollo en tres hitos de entrega rigurosos:

1.  **HITO I (OBSERVACIÓN):** Creación del observatorio, los hooks y el colector de datos en SODA FUSION. Este hito corre 100% pasivo en segundo plano. Tu SODA FUSION original sigue funcionando sin que notes ninguna diferencia de velocidad.
2.  **HITO II (ENTRENAMIENTO):** Una vez que SODA FUSION haya acumulado al menos 50 trazas exitosas de desarrollo y reparación, lanzamos la fase del entrenador local de LoRA utilizando tu GPU.
3.  **HITO III (ACCIÓN EN SANDBOX):** Implementamos el motor de inferencia local con Hot-Swapping y abrimos el workspace aislado para ver a tu modelo local programar de forma coherente.
