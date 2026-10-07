# Guarda sesiones de Claude Code como accesos directos en el escritorio.
#
# Claude Code ya persiste cada conversacion en ~/.claude/projects/<proyecto>/<sessionId>.jsonl.
# Este script toma las sesiones modificadas mas recientemente y crea un .lnk por cada una,
# que abre una consola en la carpeta correcta y ejecuta `claude --resume <sessionId>`.
# El nombre del acceso incluye el primer mensaje de la sesion para distinguirlas.
#
# Uso desde dentro de Claude Code (no consume tokens):
#   ! powershell -ExecutionPolicy Bypass -File scripts/guardar_sesion_claude.ps1              (la ultima)
#   ! powershell -ExecutionPolicy Bypass -File scripts/guardar_sesion_claude.ps1 -Ultimas 5   (las 5 ultimas)
#   ! powershell -ExecutionPolicy Bypass -File scripts/guardar_sesion_claude.ps1 -Nombre "fix pipeline"
# O con doble clic en guardar_sesion_claude.bat (raiz del repo), que guarda las 5 ultimas.

param(
    [string]$Nombre = "",
    [int]$Ultimas = 1
)

$ErrorActionPreference = "Stop"

$projectsDir = Join-Path $HOME ".claude\projects"
if (-not (Test-Path $projectsDir)) {
    Write-Host "No existe $projectsDir - Claude Code todavia no guardo ninguna sesion." -ForegroundColor Red
    exit 1
}

# Sesiones principales mas recientes (se excluyen transcripts de subagentes)
$sesiones = Get-ChildItem -Path $projectsDir -Filter *.jsonl -File -Recurse -Depth 1 |
    Where-Object { $_.BaseName -notlike "agent-*" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First $Ultimas

if (-not $sesiones) {
    Write-Host "No se encontraron sesiones en $projectsDir" -ForegroundColor Red
    exit 1
}

# Devuelve la carpeta de trabajo ("cwd") y el primer mensaje del usuario de un transcript.
function Leer-Sesion($archivo) {
    $cwd = $null
    $tema = $null
    foreach ($linea in Get-Content -LiteralPath $archivo -Encoding UTF8) {
        if ($cwd -and $tema) { break }
        try { $obj = $linea | ConvertFrom-Json } catch { continue }
        if (-not $cwd -and $obj.cwd) { $cwd = $obj.cwd }
        if (-not $tema -and $obj.type -eq "user" -and $obj.message) {
            $c = $obj.message.content
            $texto = if ($c -is [string]) { $c } else { ($c | Where-Object { $_.type -eq "text" } | Select-Object -First 1).text }
            # Se saltean mensajes internos (comandos, avisos del sistema)
            if ($texto -and -not $texto.TrimStart().StartsWith("<")) { $tema = $texto }
        }
    }
    return @{ Cwd = $cwd; Tema = $tema }
}

$escritorio = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell

foreach ($sesion in $sesiones) {
    $sessionId = $sesion.BaseName
    $info = Leer-Sesion $sesion.FullName
    $cwd = $info.Cwd

    # `claude --resume` debe ejecutarse desde la misma carpeta para encontrar la sesion.
    if (-not $cwd -or -not (Test-Path -LiteralPath $cwd)) {
        Write-Host "Salteo $sessionId - no pude determinar su carpeta" -ForegroundColor Yellow
        continue
    }

    $proyecto = Split-Path $cwd -Leaf
    $fecha = $sesion.LastWriteTime.ToString("yyyy-MM-dd HH.mm")
    $tema = if ($Nombre -and $Ultimas -eq 1) { $Nombre } elseif ($info.Tema) { $info.Tema } else { $sessionId.Substring(0, 8) }
    $tema = ($tema -replace '\s+', ' ').Trim()
    if ($tema.Length -gt 40) { $tema = $tema.Substring(0, 40).Trim() + "..." }
    $etiqueta = "$proyecto - $tema - $fecha" -replace '[\\/:*?"<>|]', '_'

    $lnkPath = Join-Path $escritorio "Claude - $etiqueta.lnk"
    $lnk = $shell.CreateShortcut($lnkPath)
    $lnk.TargetPath = "$env:SystemRoot\System32\cmd.exe"
    $lnk.Arguments = "/k cd /d `"$cwd`" && claude --resume $sessionId"
    $lnk.WorkingDirectory = $cwd
    $lnk.Description = "Retomar sesion de Claude Code $sessionId"
    $lnk.Save()

    Write-Host "Guardada: $etiqueta" -ForegroundColor Green
    Write-Host "  ID: $sessionId"
}
