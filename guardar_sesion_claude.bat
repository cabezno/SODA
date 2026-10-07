@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\guardar_sesion_claude.ps1" %*
pause
