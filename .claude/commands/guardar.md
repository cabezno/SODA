---
description: Crea un acceso directo en el escritorio para retomar esta sesión exacta
allowed-tools: Bash(powershell:*)
---
!`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/guardar_sesion_claude.ps1 -Nombre "$ARGUMENTS"`

Confirmá en una sola línea que la sesión quedó guardada, usando la salida de arriba.
