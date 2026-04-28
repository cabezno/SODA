@echo off
cd /d "%~dp0"
echo ========================================
echo SODA: Reparando Dependencias Críticas
echo ========================================

if exist venv\Scripts\python.exe (
    echo [1/3] Instalando PyTorch (CPU) y Torchaudio...
    venv\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
    
    echo [2/3] Instalando Soundfile...
    venv\Scripts\python.exe -m pip install soundfile
    
    echo [3/3] Verificando instalaciones...
    venv\Scripts\python.exe -c "import torch; import soundfile; print('SODA CORE DEPS: OK')"
) else (
    echo [ERROR] No se encontro el entorno virtual en venv\
)

echo.
echo ========================================
echo REPARACION COMPLETADA
echo Ahora puedes volver a lanzar SODA UI.
echo ========================================
pause
