"""
Auto-fix execution system for SODA projects.

Ladder:
  Attempt 1 — normal run (deps already installed)
  Attempt 2 — re-install deps + alternative runtime detection
  Attempt 3 — stack-aware fallback commands (venv activation, npm ci, etc.)
  If all fail → invoke Claude CLI (claude) as autonomous subprocess to diagnose
               and fix, then generate _soda_execution_notes.md as a precedent.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from kernel.execution.execution_error_log import ExecutionErrorLog
from kernel.execution.execution_precedents import ExecutionPrecedents
from kernel.execution.project_runner import ProjectRunner
from kernel.execution.stack_detector import StackDetector


NotifyFn = Callable[[str, str, dict], None]


# ── Attempt helpers ────────────────────────────────────────────────────────────

def _noop(*_):
    pass


async def _run_cmd(cmd: str, cwd: Path, timeout: int = 120) -> tuple[bool, str]:
    """Run a shell command, return (success, output)."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=os.environ.copy(),
        )
        try:
            out_b, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return False, f"Timeout after {timeout}s"
        output = out_b.decode("utf-8", errors="replace")[-3000:]
        return proc.returncode == 0, output
    except Exception as e:
        return False, str(e)


def _build_attempt2_commands(
    stack: str,
    run_command: str,
    install_command: str,
    workdir: Path,
) -> tuple[str, str]:
    """Return (install_cmd, run_cmd) for attempt 2: clean-reinstall + alt runtime."""
    if stack == "python":
        venv = workdir / ".venv"
        if not venv.exists():
            install = f"py -m venv .venv && .venv\\Scripts\\activate && pip install -r requirements.txt"
        else:
            install = ".venv\\Scripts\\activate && pip install -r requirements.txt --upgrade"
        run = run_command.replace("python ", ".venv\\Scripts\\python ").replace(
            "uvicorn ", ".venv\\Scripts\\uvicorn "
        )
    elif stack == "node":
        install = "npm ci" if (workdir / "package-lock.json").exists() else "npm install --force"
        run = run_command
    elif stack == "dotnet":
        install = "dotnet restore"
        run = run_command
    else:
        install = install_command
        run = run_command
    return install, run


def _build_attempt3_commands(
    stack: str,
    run_command: str,
    install_command: str,
    workdir: Path,
    precedents: list[dict],
) -> tuple[str, str]:
    """Return (install_cmd, run_cmd) for attempt 3: precedent-based fallback."""
    if precedents:
        best = precedents[0]
        return best.get("install_command", install_command), best.get("run_command", run_command)

    # Generic fallbacks per stack
    if stack == "python":
        return "pip install -r requirements.txt", "python main.py"
    if stack == "node":
        return "npm install", "node index.js"
    if stack == "dotnet":
        return "dotnet build", "dotnet run"
    return install_command, run_command


# ── Claude CLI fallback ────────────────────────────────────────────────────────

def _invoke_claude_cli(
    project_id: str,
    project_workspace: Path,
    run_command: str,
    install_command: str,
    error_log: str,
    notify: NotifyFn,
) -> Optional[str]:
    """
    Spawn Claude CLI as an autonomous subprocess to diagnose and fix execution.
    Grants full tool access (dangerouslySkipPermissions).
    Returns the notes text if Claude produced them, else None.
    """
    claude_exe = shutil.which("claude")
    if not claude_exe:
        notify("Claude CLI no encontrado en PATH. Instalar con: npm i -g @anthropic-ai/claude-code", "LOG", {})
        return None

    source_dir = project_workspace / "source"
    root = str(source_dir if source_dir.exists() else project_workspace)

    prompt = textwrap.dedent(f"""
        Sos el agente de ejecución de SODA. El proyecto '{project_id}' no pudo ejecutarse
        después de 3 intentos automáticos.

        Directorio del proyecto: {root}
        Comando de instalación intentado: {install_command or "(ninguno)"}
        Comando de ejecución intentado: {run_command}
        Errores recientes:
        {error_log[:1500]}

        TU TAREA:
        1. Explorá el directorio, leé los archivos principales y entendé la aplicación.
        2. Instalá las dependencias necesarias (puede requerir crear venv, npm install, etc.).
        3. Ejecutá el proyecto y confirmá que arranca sin errores críticos.
        4. Si encontrás problemas de código, corregílos.
        5. Cuando todo funcione, creá el archivo `_soda_execution_notes.md` dentro de {root}
           con el formato:
           ```
           # Notas de ejecución — {project_id}
           stack: <stack detectado>
           install_command: <comando que funcionó>
           run_command: <comando que funcionó>
           notas: <qué hubo que corregir y por qué>
           ```
        6. NO me pidas permiso para cada paso — tenés autorización completa para leer,
           escribir, ejecutar y corregir archivos en este proyecto.
    """).strip()

    notify("Llamando a Claude CLI para diagnóstico autónomo...", "LOG", {"project_id": project_id})

    try:
        result = subprocess.run(
            [claude_exe, "--dangerouslySkipPermissions", "-p", prompt],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=600,
            encoding="utf-8",
            errors="replace",
            env=os.environ.copy(),
        )
        notify(
            f"Claude CLI terminó (rc={result.returncode}). "
            f"stdout={result.stdout[:200]}",
            "LOG",
            {"project_id": project_id},
        )
        # Read notes file if Claude created it
        notes_path = Path(root) / "_soda_execution_notes.md"
        if notes_path.exists():
            return notes_path.read_text(encoding="utf-8", errors="replace")
        return result.stdout[:500] if result.stdout else None
    except subprocess.TimeoutExpired:
        notify("Claude CLI timeout (10 min). Operación cancelada.", "LOG", {})
        return None
    except Exception as e:
        notify(f"Error al invocar Claude CLI: {e}", "LOG", {})
        return None


def _save_notes(project_workspace: Path, notes: str) -> Path:
    """Write _soda_execution_notes.md to project workspace."""
    source_dir = project_workspace / "source"
    root = source_dir if source_dir.exists() else project_workspace
    notes_path = root / "_soda_execution_notes.md"
    notes_path.write_text(notes, encoding="utf-8")
    return notes_path


# ── Main AutoFixer ─────────────────────────────────────────────────────────────

class AutoFixer:
    """
    Tries 3 increasingly aggressive execution strategies before falling back
    to Claude CLI for fully autonomous repair.
    """

    def __init__(self, notify_fn: Optional[NotifyFn] = None):
        self._notify: NotifyFn = notify_fn or _noop
        self._runner = ProjectRunner()

    async def fix_and_run(
        self,
        project_id: str,
        project_workspace: Path,
        run_command: str,
        install_command: str = "",
    ) -> dict:
        """
        Execute the 3-attempt ladder + Claude CLI fallback.
        Returns {success, attempt, pid, url, notes_path, error}.
        """
        source_dir = project_workspace / "source"
        root = source_dir if source_dir.exists() else project_workspace
        stack = StackDetector.detect(run_command, install_command)
        precedents = ExecutionPrecedents.get_for_stack(stack)

        attempts = self._build_attempts(stack, run_command, install_command, root, precedents)

        last_error = ""
        for idx, (inst_cmd, run_cmd, label) in enumerate(attempts, start=1):
            self._notify(
                f"[AutoFix] Intento {idx}/3: {label}",
                "LOG",
                {"project_id": project_id, "attempt": idx},
            )

            # Install
            if inst_cmd and inst_cmd.strip():
                ok, out = await _run_cmd(inst_cmd, root, timeout=180)
                if not ok:
                    last_error = out
                    ExecutionErrorLog.record(
                        project_id, f"auto_fix_install_{idx}", out[:500], "InstallError",
                        {"command": inst_cmd},
                    )
                    self._notify(f"[AutoFix] Instalación falló en intento {idx}: {out[:150]}", "LOG", {})
                    continue

            # Launch
            result = await self._runner.launch(project_workspace, run_cmd, inst_cmd)
            if result.launched:
                self._notify(
                    f"[AutoFix] Éxito en intento {idx}! PID={result.pid}, URL={result.url}",
                    "LOG",
                    {"project_id": project_id, "attempt": idx, "pid": result.pid},
                )
                await asyncio.sleep(4)
                smoke = await self._runner.smoke_check_with_retry(
                    project_workspace, run_cmd, inst_cmd,
                    target_url=result.url or None,
                    attempts=3, delay_s=2.0,
                )
                if smoke.passed or result.launched:
                    # Record working config as precedent
                    ExecutionPrecedents.record(
                        project_id=project_id,
                        stack=stack,
                        run_command=run_cmd,
                        install_command=inst_cmd,
                        working_dir=str(root),
                        notes=f"AutoFix intento {idx}: {label}",
                    )
                    self._write_notes_file(
                        project_workspace, project_id, stack, run_cmd, inst_cmd,
                        f"Resuelto automáticamente — {label}",
                    )
                    return {
                        "success": True,
                        "attempt": idx,
                        "pid": result.pid,
                        "url": result.url,
                        "notes_path": str(project_workspace / "source" / "_soda_execution_notes.md"),
                        "error": "",
                    }
            else:
                last_error = result.error
                ExecutionErrorLog.record(
                    project_id, f"auto_fix_launch_{idx}", result.error[:500], "LaunchError",
                    {"command": run_cmd},
                )
                self._notify(f"[AutoFix] Lanzamiento falló en intento {idx}: {result.error[:120]}", "LOG", {})

        # All 3 failed → Claude CLI
        self._notify(
            "[AutoFix] 3 intentos fallidos. Invocando Claude CLI para reparación autónoma...",
            "HEALTH_WARN",
            {"project_id": project_id},
        )
        error_summary = ExecutionErrorLog.error_summary_for_ai(project_id, max_errors=5)
        notes_text = _invoke_claude_cli(
            project_id, project_workspace, run_command, install_command,
            error_summary or last_error, self._notify,
        )
        notes_path = None
        if notes_text:
            notes_path = _save_notes(project_workspace, notes_text)
            # Try to parse notes and record as precedent
            self._parse_and_record_notes(project_id, stack, notes_text)
            self._notify(
                f"[AutoFix] Claude CLI generó notas de ejecución: {notes_path}",
                "LOG",
                {"project_id": project_id, "notes_path": str(notes_path)},
            )

        return {
            "success": False,
            "attempt": 3,
            "pid": 0,
            "url": "",
            "notes_path": str(notes_path) if notes_path else "",
            "error": last_error,
        }

    def _build_attempts(
        self,
        stack: str,
        run_command: str,
        install_command: str,
        workdir: Path,
        precedents: list[dict],
    ) -> list[tuple[str, str, str]]:
        """Return list of (install_cmd, run_cmd, label) for 3 attempts."""
        inst2, run2 = _build_attempt2_commands(stack, run_command, install_command, workdir)
        inst3, run3 = _build_attempt3_commands(stack, run_command, install_command, workdir, precedents)
        return [
            (install_command, run_command, "ejecución normal"),
            (inst2, run2, "reinstalación de dependencias"),
            (inst3, run3, "fallback basado en precedentes"),
        ]

    def _write_notes_file(
        self,
        project_workspace: Path,
        project_id: str,
        stack: str,
        run_command: str,
        install_command: str,
        notes: str,
    ) -> None:
        source_dir = project_workspace / "source"
        root = source_dir if source_dir.exists() else project_workspace
        content = (
            f"# Notas de ejecución — {project_id}\n"
            f"generado: {datetime.utcnow().isoformat()}\n\n"
            f"stack: {stack}\n"
            f"install_command: {install_command}\n"
            f"run_command: {run_command}\n"
            f"notas: {notes}\n"
        )
        try:
            (root / "_soda_execution_notes.md").write_text(content, encoding="utf-8")
        except Exception:
            pass

    def _parse_and_record_notes(self, project_id: str, stack: str, notes_text: str) -> None:
        """Parse _soda_execution_notes.md produced by Claude CLI and save as precedent."""
        run_cmd = install_cmd = notes_str = ""
        for line in notes_text.splitlines():
            line = line.strip()
            if line.startswith("run_command:"):
                run_cmd = line.split(":", 1)[1].strip()
            elif line.startswith("install_command:"):
                install_cmd = line.split(":", 1)[1].strip()
            elif line.startswith("notas:"):
                notes_str = line.split(":", 1)[1].strip()
            elif line.startswith("stack:"):
                stack = line.split(":", 1)[1].strip() or stack
        if run_cmd:
            ExecutionPrecedents.record(
                project_id=project_id,
                stack=stack,
                run_command=run_cmd,
                install_command=install_cmd,
                notes=notes_str or "Resuelto por Claude CLI",
            )
