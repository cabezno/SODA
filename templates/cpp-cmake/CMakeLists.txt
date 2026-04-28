cmake_minimum_required(VERSION 3.15)
project(SodaCppProject VERSION 1.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Añadir carpeta src a los includes
include_directories(src)

# Archivos fuente
file(GLOB_RECURSE SOURCES "src/*.cpp")

# Crear el ejecutable
add_executable(${PROJECT_NAME} ${SOURCES})

# Configuración básica para Windows (evitar consola fantasma si es GUI, etc)
if(WIN32 AND MSVC)
    add_compile_options(/W4)
    # Si detecta windows.h pero es consola, se queda normal
endif()
