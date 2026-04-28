@echo off
cd /d "%~dp0"
echo ========================================
echo SODA: Lanzador Inteligente
echo ========================================

:: 1. Verificar si Ollama esta corriendo
echo [1/2] Verificando Ollama...
netstat -ano | findstr :11434 >nul
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] Ollama no parece estar corriendo. 
    echo Por favor, abre la aplicacion Ollama antes de continuar.
    pause
) else (
    echo [OK] Ollama detectado.
)

:: 2. Configurar PATH para FFMPEG local
set "PATH=%PATH%;%~dp0"

:: 3. Ejecutar con el Python correcto
echo [2/2] Iniciando UI con entorno virtual...
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe -m ui.launcher
) else (
    echo [ERROR] No se encontro el entorno virtual en venv\
    echo Intenta ejecutar reparar_dependencias.bat primero.
    python -m ui.launcher
)

pause
