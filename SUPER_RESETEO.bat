@echo off
cd /d "%~dp0"
echo ========================================
echo SODA: OPERACION DE SANEAMIENTO TOTAL
echo ========================================

echo [1/4] Limpiando procesos bloqueados...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM python3.11.exe /T 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /F /PID %%a 2>nul

echo [2/4] Reinstalando dependencias criticas en el venv...
:: Usamos la ruta absoluta para evitar confusiones de disco
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install torch torchaudio soundfile --index-url https://download.pytorch.org/whl/cpu --no-cache-dir
.\venv\Scripts\python.exe -m pip install -r requirements.txt

echo [3/4] Verificando entorno...
.\venv\Scripts\python.exe -c "import torch; import soundfile; print('>>> VERIFICACION EXITOSA')"

echo [4/4] Lanzando SODA en MODO WEB (Puerto 8001 para evitar conflictos)...
echo Abre tu navegador en http://localhost:8001 si la ventana no aparece.
start "" http://localhost:8001
.\venv\Scripts\python.exe -m uvicorn ui.server:app --host 0.0.0.0 --port 8001

pause
