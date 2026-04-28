@echo off
:: Cambiar al directorio donde reside este archivo .bat
cd /d "%~dp0"

echo ========================================
echo SODA: Construyendo Runtimes Aislados
echo ========================================
echo Directorio actual: %cd%

:: Añadir ruta de Docker al PATH para esta sesion
set "PATH=%PATH%;C:\Program Files\Docker\Docker\resources\bin"

:: Intentar con python del venv primero
if exist venv\Scripts\python.exe (
    echo [INFO] Usando Python del venv...
    venv\Scripts\python.exe scripts\build_runtimes.py
    goto end
)

:: Intentar con python global
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Usando Python global...
    python scripts\build_runtimes.py
    goto end
)

:: Intentar con python3
python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Usando Python3...
    python3 scripts\build_runtimes.py
    goto end
)

:: Intentar con py launcher
py --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Usando lanzador py...
    py scripts\build_runtimes.py
    goto end
)

echo [ERROR] No se pudo encontrar Python. Por favor, asegúrate de que Python esté en el PATH.

:end
pause
