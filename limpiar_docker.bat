@echo off
:: Solicitar permisos de administrador si no los tiene
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo [INFO] Solicitando permisos de administrador...
    goto UACPrompt
) else ( goto gotAdmin )
:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    exit /B
:gotAdmin
    if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )
    pushd "%CD%"
    CD /D "%~dp0"

echo ========================================
echo SODA: Limpiador de EMERGENCIA Docker
echo ========================================

echo [1/3] Deteniendo servicios de Docker...
net stop com.docker.service /y
sc stop com.docker.service

echo [2/3] Matando procesos persistentes...
taskkill /F /IM "Docker Desktop.exe" /T
taskkill /F /IM "com.docker.backend.exe" /T
taskkill /F /IM "com.docker.vpnkit.exe" /T
taskkill /F /IM "com.docker.proxy.exe" /T
taskkill /F /IM "dockerd.exe" /T
taskkill /F /IM "docker.exe" /T
taskkill /F /IM "vmmem" /T

echo [3/3] Limpiando sockets...
del /f /q "\\.\pipe\docker_engine" 2>nul
del /f /q "\\.\pipe\docker_engine_linux" 2>nul

echo.
echo ========================================
echo LIMPIEZA COMPLETADA
echo Por favor, REINICIA DOCKER DESKTOP ahora.
echo ========================================
pause
