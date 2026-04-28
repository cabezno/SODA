@echo off
echo ========================================
echo SODA: Limpiador de Instancias Huérfanas
echo ========================================

echo [1/2] Cerrando procesos de Python (SODA)...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM python3.11.exe /T 2>nul

echo [2/2] Liberando puerto 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /F /PID %%a 2>nul

echo.
echo ========================================
echo LIMPIEZA COMPLETADA
echo Ahora puedes ejecutar 'lanzar_ui.bat'
echo para una sesión limpia.
echo ========================================
pause
