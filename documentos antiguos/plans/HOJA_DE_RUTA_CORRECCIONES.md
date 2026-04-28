# Hoja de Ruta: Correcciones Críticas y Optimización (SODA)

Tras analizar los últimos cambios en la base de código (especialmente la excelente centralización de `_handle_copilot_review`), esta hoja de ruta detalla los pasos prácticos para corregir las fallas restantes, priorizadas por su impacto en el rendimiento y la estabilidad.

---

## 🚀 PRIORIDAD ALTA: Rendimiento y Estabilidad del Sistema

### 1. Paralelismo Síncrono en Generación de Código
*   **Archivo afectado:** `kernel/code_generator.py` (método `generate_module`)
*   **Problema:** Se itera sobre los archivos de un módulo (`for filepath in files:`) esperando a que cada uno termine de generarse antes de empezar el siguiente. 
*   **Acción:** Reemplazar el bucle `for` secuencial por `asyncio.gather(*tasks)` para lanzar la generación de todos los archivos independientes de un módulo al mismo tiempo.
*   **Impacto [MUY ALTO]:** Reducirá el tiempo de desarrollo de la FASE 4 dramáticamente (hasta un 60-70% más rápido), aprovechando las ventajas asíncronas de las APIs de LLMs.

### 2. Fuga de Recursos por Hilos Zombie en Notificaciones
*   **Archivo afectado:** `kernel/orchestrator.py` (método `_notify`)
*   **Problema:** Crea un `threading.Thread(target=_post, daemon=True).start()` por cada evento que emite el orquestador. En picos altos de logs, puede agotar los descriptores de red y la memoria.
*   **Acción:** Migrar a una cola asíncrona (`asyncio.Queue`) con un *worker* dedicado que procese y envíe los eventos por lotes, o usar un *Connection Pool* para limitar los hilos.
*   **Impacto [ALTO]:** Evitará cuelgues repentinos y saturación de memoria durante corridas largas o proyectos muy grandes.

---

## 🛠️ PRIORIDAD MEDIA: Deuda Técnica y Redundancias

### 3. I/O Excesivo de Archivos de Configuración
*   **Archivo afectado:** `kernel/orchestrator.py`
*   **Problema:** Métodos como `_get_auto_confirm()`, `_runtime_smoke_enabled()` y `_load_ai_routing()` abren y parsean `soda_config.json` en cada ejecución.
*   **Acción:** Crear una clase `ConfigManager` Singleton que lea el archivo una vez al inicio y exponga propiedades en memoria.
*   **Impacto [MEDIO]:** Mejorará el rendimiento general y evitará cuellos de botella de disco o condiciones de carrera si el archivo se edita mientras corre.

### 4. Acoplamiento en el Orquestador (God Object)
*   **Archivo afectado:** `kernel/orchestrator.py`
*   **Problema:** El `__init__` inicializa directamente a fuego más de 40 componentes distintos (drivers, validadores, agentes).
*   **Acción:** Implementar Inyección de Dependencias (DI) o crear un patrón "Factory/Provider" que pase las dependencias ya armadas.
*   **Impacto [MEDIO]:** Permitirá hacer *Unit Tests* reales del orquestador (actualmente es imposible sin mockear la mitad de Internet) y reducirá la huella de memoria inicial.

### 5. Parseo Frágil y Magic Strings
*   **Archivo afectado:** `kernel/code_generator.py`
*   **Problema:** 
    1. El método `_strip_fence` para quitar Markdown asume que la cerca empieza en la primera línea.
    2. Diccionario `_VERSION_CORRECTIONS` con versiones estáticas ("@types/react": "^18.0.0").
*   **Acción:** Mejorar la Regex de `_strip_fence` para que ignore texto previo, y mover el diccionario de versiones a un archivo de configuración externo u obtener la última versión dinámicamente.
*   **Impacto [MEDIO]:** Evitará fallas silenciosas donde texto basura del LLM se cuela en el código fuente, rompiendo los *builds*.

---

## 🔍 PRIORIDAD BAJA: Robustez

### 6. Homologar el Driver de Control de Errores (JSON "parts")
*   **Archivo afectado:** `kernel/drivers/gemini_driver.py` y equivalentes.
*   **Problema:** Si ocurre un error estructural en la API (como cuando faltan "parts" por un bloqueo interno), se lanza una excepción nativa de Python (`KeyError`) que borra el contexto real.
*   **Acción:** Ajustar los `try/except` para mapear estos errores de formato a mensajes de control precisos (ej. "ERROR:FORMAT_BLOCKED").
*   **Impacto [BAJO]:** Hará que los logs sean legibles, permitiendo que SODA decida si debe escalar al siguiente modelo de manera mucho más rápida.