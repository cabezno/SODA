# SODA Runtime System

SODA utiliza un sistema de **Runtimes Aislados** basados en Docker para garantizar que el desarrollo, las pruebas y la ejecución de código sean independientes del sistema host (Windows/WSL).

## 🚀 Cómo empezar

Antes de ejecutar un proyecto en un lenguaje específico, debes asegurarte de que el runtime esté construido. Puedes construir todos los runtimes oficiales ejecutando:

```bash
python scripts/build_runtimes.py
```

## 🛠️ Estructura del Sistema

- **`runtimes/`**: Contiene las definiciones (`Dockerfile`) y el registro (`registry.json`) de los entornos.
- **`kernel/execution/runtime_manager.py`**: El componente encargado de gestionar la construcción y verificación de las imágenes.
- **`kernel/docker_sandbox.py`**: El ejecutor aislado que utiliza estas imágenes para correr código y tests.

## 📝 Cómo añadir un nuevo Lenguaje (ej. Rust)

1. **Crear la carpeta**: `mkdir runtimes/rust`
2. **Crear el Dockerfile**: Define el entorno con las herramientas necesarias (cargo, rustc, linters).
3. **Registrar en `runtimes/registry.json`**:
   ```json
   "rust": {
     "image_tag": "soda-runtime-rust",
     "dockerfile": "runtimes/rust/Dockerfile",
     "tools": ["cargo", "clippy"]
   }
   ```
4. **Actualizar `DockerSandbox.run()`**: Añade la lógica para ejecutar archivos `.rs` o usar `cargo run`.
5. **Actualizar `SodaOrchestrator._get_runtime_key()`**: Añade la lógica para detectar el stack de Rust.

## 🛡️ Beneficios de este enfoque

1. **Aislamiento**: No necesitas instalar Python, Node o Go en tu máquina. SODA lo gestiona todo.
2. **Reproducibilidad**: Si los tests pasan en el runtime de SODA, pasarán en cualquier otro entorno Docker.
3. **Seguridad**: El código generado se ejecuta sin acceso a la red y con límites de CPU/Memoria estrictos.
