# Guarda la sesion actual de Claude Code como acceso directo en el escritorio.
#
# Claude Code ya persiste cada conversacion en ~/.claude/projects/<proyecto>/<sessionId>.jsonl.
# Este script toma la sesion modificada mas recientemente (la que estas usando) y crea
# un .lnk que abre una consola en la carpeta correcta y ejecuta `claude --resume <sessionId>`.
#
# Uso desde dentro de Claude Code (no consume tokens):
#   ! powershell -ExecutionPolicy Bypass -File scripts/guardar_sesion_claude.ps1
#   ! powershell -ExecutionPolicy Bypass -File scripts/guardar_sesion_claude.ps1 -Nombre "fix pipeline"
# O con doble clic en guardar_sesion_claude.bat (raiz del repo) despues de cerrar Claude.

param(
    [string]$Nombre = ""
)

$ErrorActionPreference = "Stop"

$projectsDir = Join-Path $HOME ".claude\projects"
if (-not (Test-Path $projectsDir)) {
    Write-Host "No existe $projectsDir - Claude Code todavia no guardo ninguna sesion." -ForegroundColor Red
    exit 1
}

# Sesion principal mas reciente (se excluyen transcripts de subagentes)
$sesion = Get-ChildItem -Path $projectsDir -Filter *.jsonl -File -Recurse -Depth 1 |
    Where-Object { $_.BaseName -notlike "agent-*" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $sesion) {
    Write-Host "No se encontraron sesiones en $projectsDir" -ForegroundColor Red
    exit 1
}

$sessionId = $sesion.BaseName

# La carpeta de trabajo de la sesion figura en el campo "cwd" de las lineas del transcript.
# `claude --resume` debe ejecutarse desde esa misma carpeta para encontrar la sesion.
$cwd = $null
foreach ($linea in Get-Content -LiteralPath $sesion.FullName -Encoding UTF8) {
    if ($linea -notmatch '"cwd"') { continue }
    try {
        $obj = $linea | ConvertFrom-Json
        if ($obj.cwd) { $cwd = $obj.cwd; break }
    } catch { }
}
if (-not $cwd -or -not (Test-Path -LiteralPath $cwd)) {
    Write-Host "No pude determinar la carpeta de la sesion $sessionId" -ForegroundColor Red
    exit 1
}

$proyecto = Split-Path $cwd -Leaf
$fecha = Get-Date -Format "yyyy-MM-dd HH.mm"
$etiqueta = if ($Nombre) { "$proyecto - $Nombre - $fecha" } else { "$proyecto - $fecha" }
$etiqueta = $etiqueta -replace '[\\/:*?"<>|]', '_'

$escritorio = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $escritorio "Claude - $etiqueta.lnk"

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath = "$env:SystemRoot\System32\cmd.exe"
$lnk.Arguments = "/k cd /d `"$cwd`" && claude --resume $sessionId"
$lnk.WorkingDirectory = $cwd
$lnk.Description = "Retomar sesion de Claude Code $sessionId"
$lnk.Save()

Write-Host "Sesion guardada:" -ForegroundColor Green
Write-Host "  ID:       $sessionId"
Write-Host "  Carpeta:  $cwd"
Write-Host "  Acceso:   $lnkPath"
