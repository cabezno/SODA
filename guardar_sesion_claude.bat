@echo off
cd /d "%~dp0"
set N=%1
if "%N%"=="" set N=5
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\guardar_sesion_claude.ps1" -Ultimas %N%
pause
