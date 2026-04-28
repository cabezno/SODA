@echo off
cd /d "%~dp0"
echo === SODA DEBUG SESSION ===
echo Directorio: %cd%

echo 1. Verificando archivos...
if exist venv\Scripts\python.exe (echo [OK] Python venv encontrado) else (echo [FAIL] Python venv NO ENCONTRADO)
if exist ui\launcher.py (echo [OK] Launcher encontrado) else (echo [FAIL] Launcher NO ENCONTRADO)

echo 2. Probando ejecucion minima de Python venv...
venv\Scripts\python.exe --version
if %errorlevel% neq 0 echo [FAIL] El Python del venv no responde.

echo 3. Probando dependencias criticas...
venv\Scripts\python.exe -c "import torch; import soundfile; import pywebview; print('Dependencias OK')"
if %errorlevel% neq 0 echo [FAIL] Faltan librerias en el venv.

echo 4. Intentando lanzar UI con salida de error visible...
venv\Scripts\python.exe -m ui.launcher
if %errorlevel% neq 0 echo [FAIL] El proceso termino con error %errorlevel%

echo === FIN DE DEBUG ===
pause
