@echo off
cd /d "%~dp0"
echo ========================================
echo SODA: RESTAURACION DE FLUJO LOCAL
echo ========================================

echo [1/2] Configurando IA Primaria -> OLLAMA...
:: Creamos un soda_config.json que fuerza a Ollama
echo { > soda_config.json
echo   "ai_phase_provider": { >> soda_config.json
echo     "requirements_interviewer": "ollama", >> soda_config.json
echo     "global_architect": "ollama", >> soda_config.json
echo     "code_generator": "ollama" >> soda_config.json
echo   }, >> soda_config.json
echo   "ai_routing": { >> soda_config.json
echo     "ollama": ["ollama", "gemini", "claude"] >> soda_config.json
echo   } >> soda_config.json
echo } >> soda_config.json

echo [2/2] Intentando recuperar entorno de audio...
:: Si tenias F5-TTS, necesitas torch con CUDA
.\venv\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

echo ========================================
echo RESTAURACION COMPLETADA
echo SODA volvera a usar Ollama por defecto.
echo ========================================
pause
