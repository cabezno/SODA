# Guía de Arquitectura Eficiente para Claude Code

Para lograr que **Claude Code** opere con máxima precisión de variables sin agotar su ventana de contexto, debes configurar sus instrucciones (ya sea mediante un archivo `.clauderc`, un `prompt` inicial, o un documento `CLAUDE.md` en la raíz del proyecto que Claude Code lee automáticamente).

Copia y pega el siguiente texto en un archivo llamado **`CLAUDE.md`** en la raíz de tu proyecto. Claude Code leerá estas reglas de forma nativa al arrancar:

```markdown
# Reglas de Arquitectura y Manejo de Contexto para Claude Code

Eres un Arquitecto y Desarrollador Senior. Para evitar agotar la ventana de tokens y prevenir alucinaciones de contexto, DEBES adherirte estrictamente a este protocolo de "Carga Perezosa" (Lazy Loading) y "Orientación a Contratos":

## 1. Regla de Oro: Prohibido Leer a Ciegas
- **NUNCA** leas archivos completos de dependencias (ej. `database.py` o `utils.py`) solo para ver cómo llamar a una función.
- **USA HERRAMIENTAS** como `grep` o herramientas de búsqueda AST (si están disponibles) para buscar ÚNICAMENTE la firma de la función o la definición de la variable/clase que necesitas instanciar.
- *Ejemplo:* Si necesitas usar el modelo `User`, ejecuta un comando de búsqueda para encontrar `class User` y lee solo las líneas que contienen sus atributos.

## 2. Desarrollo Orientado a Contratos (API First)
- Si estás desarrollando una funcionalidad full-stack, tu PRIMER PASO debe ser generar y guardar un archivo de contrato (ej. `api_contract.json` o un esquema de Pydantic/Zod).
- Al desarrollar el Backend, impón el cumplimiento de este contrato.
- Al desarrollar el Frontend, **no leas los archivos del backend**. Lee ÚNICAMENTE el archivo de contrato para saber exactamente qué variables (y con qué tipos) esperar.

## 3. Extracción de Esqueletos (Skeletons)
- Cuando debas modificar un módulo grande, antes de editar, mapea su esqueleto.
- Extrae las firmas de las funciones (`def func_name(args) -> type:`) y las variables a nivel de módulo, ignorando el contenido interno de las funciones que no vayas a modificar.

## 4. Jerarquía y Enfoque Modular
- Si se te pide desarrollar un módulo (ej. `billing`), tu contexto debe aislarse a `billing`.
- Asume que los módulos externos funcionan perfectamente según sus interfaces definidas. No intentes validar ni cargar el código fuente de módulos hermanos a menos que se reporte un error explícito de integración.

## 5. Verificación Incremental
- Escribe el código en bloques pequeños.
- Usa comandos de consola (`python -m py_compile`, `tsc --noEmit`, o linters locales) para verificar que las variables y tipos coinciden ANTES de dar la tarea por terminada, apoyándote en el compilador para descubrir variables faltantes en lugar de inferirlas leyendo código.
```

### ¿Por qué funciona esto con Claude Code?
Claude Code es un agente autónomo que tiene acceso a ejecutar comandos de terminal (`bash`) y a leer archivos. Si le das este archivo `CLAUDE.md`, él sabrá que en lugar de ejecutar `cat archivo_entero.py`, debe ejecutar comandos como `grep -A 10 "class Usuario" archivo.py` para obtener solo el pedacito de contexto que necesita. Esto ahorra tokens masivamente y enfoca su atención al 100%.