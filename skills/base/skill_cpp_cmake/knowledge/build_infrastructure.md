# Build Infrastructure Checklist — C++ / CMake

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `CMakeLists.txt` | Sin esto cmake no puede configurar ni compilar el proyecto |
| `.vscode/tasks.json` | Sin esto el usuario no puede hacer Ctrl+Shift+B para compilar |
| `.vscode/launch.json` | Sin esto F5 no funciona para debug |
| `.vscode/c_cpp_properties.json` | Sin esto IntelliSense no resuelve headers y hay subrayado rojo en todo |
| `README.md` | Sin instrucciones de build el usuario no sabe qué hacer |

## Pasos que debe ejecutar el usuario para correr el proyecto

1. Instalar Visual Studio 2022 con workload "Desktop development with C++"
2. Instalar CMake >= 3.20 (https://cmake.org/download/)
3. Abrir VS Code en la carpeta del proyecto
4. Ctrl+Shift+B → "CMake Build" (esto configura y compila)
5. F5 para debug, o Ctrl+F5 para correr sin debug

## Generadores CMake por plataforma

| Plataforma | Generador recomendado |
|-----------|----------------------|
| Windows + MSVC | `Visual Studio 17 2022` con `-A x64` |
| Windows + MinGW | `MinGW Makefiles` |
| Windows + Ninja | `Ninja` (requiere ninja en PATH) |
| Linux/Mac | Sin -G (usa Make por defecto) |

## Por qué `Visual Studio 17 2022` y no `NMake Makefiles`

- NMake requiere activar VCVARS manualmente (`vcvars64.bat`) antes de correr cmake
- El generador `Visual Studio 17 2022` detecta MSVC automáticamente
- El generador Visual Studio produce una solución `.sln` que se puede abrir directamente en VS
- cmake --build funciona igual con ambos generadores

## Flags de compilación recomendados

```cmake
# Warnings como errores en CI
if(MSVC)
    target_compile_options(<proyecto> PRIVATE /W4 /WX)
else()
    target_compile_options(<proyecto> PRIVATE -Wall -Wextra -Werror)
endif()

# Debug vs Release
set(CMAKE_BUILD_TYPE "Debug" CACHE STRING "Build type")
```

## Manejo de múltiples CMakeLists.txt (proyectos con submódulos)

Si la arquitectura tiene módulos separados, cada uno puede tener su `CMakeLists.txt`:

```
raíz/
├── CMakeLists.txt          ← add_subdirectory(src/modulo_a)
└── src/
    ├── modulo_a/
    │   └── CMakeLists.txt  ← add_library(modulo_a ...)
    └── modulo_b/
        └── CMakeLists.txt  ← add_library(modulo_b ...)
```

Raíz:
```cmake
add_subdirectory(src/modulo_a)
add_subdirectory(src/modulo_b)
add_executable(app src/main.cpp)
target_link_libraries(app PRIVATE modulo_a modulo_b)
```
