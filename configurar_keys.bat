@echo off
cd /d "%~dp0"
echo ========================================
echo SODA: Configuracion de API Keys
echo ========================================
echo.
set /p key="Pega tu GEMINI_API_KEY de AI Studio y presiona ENTER: "

:: Verificar si el .env existe, si no crearlo desde el ejemplo
if not exist .env (
    if exist .env.example (
        copy .env.example .env
    ) else (
        echo. > .env
    )
)

:: Usar PowerShell para reemplazar o añadir la key de forma segura
powershell -Command "$content = Get-Content .env; if ($content -match 'GEMINI_API_KEY=') { $content -replace 'GEMINI_API_KEY=.*', 'GEMINI_API_KEY=%key%' | Set-Content .env } else { Add-Content .env 'GEMINI_API_KEY=%key%' }"

echo.
echo [OK] GEMINI_API_KEY actualizada en el archivo .env
echo Ahora SODA y Gemini CLI usaran tu propia cuota.
echo.
pause
