@echo off
cd /d "%~dp0"
echo ========================================
echo SODA: Instalacion Forzada de Inteligencia
echo ========================================

if exist venv\Scripts\python.exe (
    echo [1/2] Instalando PyTorch y dependencias (Esto puede tardar)...
    :: Usamos --no-cache-dir para asegurar que no use archivos corruptos
    venv\Scripts\python.exe -m pip install torch torchaudio soundfile --index-url https://download.pytorch.org/whl/cpu --no-cache-dir
    
    echo [2/2] Verificando...
    venv\Scripts\python.exe -c "import torch; print('PyTorch version:', torch.__version__)"
) else (
    echo [ERROR] Entorno virtual no encontrado.
)

echo.
echo ========================================
echo PROCESO FINALIZADO
echo ========================================
pause
