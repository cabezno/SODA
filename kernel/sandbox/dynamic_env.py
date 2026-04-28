"""DynamicEnvironment — creates and manages an isolated venv per project.

Lifecycle:
  1. ensure_venv()        — create .soda_venv if missing
  2. install_requirements() — pip install from requirements.txt
  3. run_syntax_check()   — py_compile every .py file (fast, no execution)
  4. run_project()        — execute entry point, capture stdout/stderr
  5. parse_errors()       — extract file/line from Python tracebacks

All output is:
  - Printed to console with [SANDBOX] prefix
  - Broadcast via notify_fn as SANDBOX_* events (→ UI terminal tab)
  - Appended to workspace/logs/sandbox.log
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


@dataclass
class SandboxResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    duration: float = 0.0
    errors: list[dict] = field(default_factory=list)
    label: str = ""


class DynamicEnvironment:
    """Isolated venv manager + code tester for a single project."""

    VENV_DIR = ".soda_venv"
    LOG_DIR = "logs"
    LOG_FILE = "sandbox.log"
    EXEC_TIMEOUT = 60  # seconds per run
    INSTALL_TIMEOUT = 180

    def __init__(
        self,
        project_id: str,
        workspace: Path,
        notify_fn: Optional[Callable] = None,
    ):
        self.project_id = project_id
        self.workspace = workspace
        self.venv_path = workspace / self.VENV_DIR
        self.log_dir = workspace / self.LOG_DIR
        self._notify = notify_fn or (lambda msg, ev, data: None)
        self._ready = False

    # ── Public API ───────────────────────────────────────────────────────

    async def ensure_venv(self) -> bool:
        """Create venv if it doesn't exist. Returns True if ready."""
        if self._ready:
            return True
        if not self.venv_path.exists():
            self._emit("Creando entorno virtual...", "SANDBOX_INIT")
            result = await self._run_raw(
                [sys.executable, "-m", "venv", str(self.venv_path)],
                timeout=60,
                label="venv_create",
                cwd=str(self.workspace),
            )
            if not result.success:
                self._emit(f"Error creando venv: {result.stderr[:300]}", "SANDBOX_ERROR")
                return False
            self._emit("Entorno virtual creado.", "SANDBOX_INIT")
        self._ready = True
        return True

    async def install_requirements(self, req_file: Optional[Path] = None) -> SandboxResult:
        """Install from requirements.txt (auto-detected if not given)."""
        if not await self.ensure_venv():
            return SandboxResult(success=False, label="install", stderr="venv not ready")

        if req_file is None:
            req_file = self.workspace / "source" / "requirements.txt"
            if not req_file.exists():
                req_file = self.workspace / "requirements.txt"

        if not req_file or not req_file.exists():
            self._emit("No se encontro requirements.txt — omitiendo instalacion.", "SANDBOX_LOG")
            return SandboxResult(success=True, label="install")

        self._emit(f"Instalando dependencias desde {req_file.name}...", "SANDBOX_INIT")
        pip = self._pip_path()
        result = await self._run_raw(
            [pip, "install", "-r", str(req_file), "--quiet"],
            timeout=self.INSTALL_TIMEOUT,
            label="pip_install",
            cwd=str(self.workspace),
        )
        if result.success:
            self._emit("Dependencias instaladas correctamente.", "SANDBOX_INIT")
        else:
            self._emit(f"Error instalando dependencias:\n{result.stderr[:600]}", "SANDBOX_ERROR")
        return result

    async def run_autofix(self, source_dir: Optional[Path] = None) -> SandboxResult:
        """Use ruff to automatically fix trivial lint/syntax issues (imports, formatting)."""
        if source_dir is None:
            source_dir = self.workspace / "source"
        if not source_dir.exists():
            return SandboxResult(success=True, label="autofix")

        self._emit("Ejecutando auto-reparador de código (Ruff)...", "SANDBOX_LOG")
        
        # 1. Fix actionable rules (imports, simple bug patterns)
        # We use sys.executable -m ruff to ensure we use the same environment's ruff if available,
        # or the global one if not.
        fix_result = await self._run_raw(
            [sys.executable, "-m", "ruff", "check", "--fix", "--unsafe-fixes", str(source_dir)],
            timeout=15,
            label="ruff_fix",
            cwd=str(self.workspace),
        )

        # 2. Reformat code (indentation, spacing)
        fmt_result = await self._run_raw(
            [sys.executable, "-m", "ruff", "format", str(source_dir)],
            timeout=15,
            label="ruff_format",
            cwd=str(self.workspace),
        )

        success = fix_result.success and fmt_result.success
        if success:
            self._emit("Auto-reparación estática completada.", "SANDBOX_LOG")
        else:
            self._emit("Ruff no pudo corregir todos los problemas (no crítico).", "SANDBOX_LOG")
            
        return SandboxResult(success=success, label="autofix")

    async def run_syntax_check(self, source_dir: Optional[Path] = None) -> SandboxResult:
        """Run py_compile on all .py files. Fast — no execution needed."""
        if source_dir is None:
            source_dir = self.workspace / "source"

        # Pilar 1: Auto-fix before checking
        await self.run_autofix(source_dir)

        py_files = list(source_dir.rglob("*.py")) if source_dir.exists() else []
        if not py_files:
            return SandboxResult(success=True, label="syntax")

        self._emit(f"Verificando sintaxis de {len(py_files)} archivo(s)...", "SANDBOX_LOG")
        errors: list[dict] = []
        for f in py_files:
            result = await self._run_raw(
                [sys.executable, "-m", "py_compile", str(f)],
                timeout=10,
                label=f"syntax:{f.name}",
                cwd=str(self.workspace),
            )
            if not result.success:
                parsed = self._parse_errors(result.stderr, str(f.relative_to(self.workspace)))
                errors.extend(parsed)
                self._emit(f"Error de sintaxis en {f.name}:\n{result.stderr[:300]}", "SANDBOX_ERROR")

        ok = len(errors) == 0
        summary = f"Sintaxis OK ({len(py_files)} archivos)" if ok else f"{len(errors)} error(es) de sintaxis"
        self._emit(summary, "SANDBOX_SYNTAX_DONE")
        return SandboxResult(success=ok, errors=errors, label="syntax")

    async def run_project(self, entry_command: Optional[str] = None) -> SandboxResult:
        """Run the project entry point and capture output."""
        if not await self.ensure_venv():
            return SandboxResult(success=False, label="run", stderr="venv not ready")

        cmd = self._resolve_entry_command(entry_command)
        if not cmd:
            self._emit("No se encontro comando de entrada para ejecutar.", "SANDBOX_LOG")
            return SandboxResult(success=False, label="run", stderr="no entry command")

        self._emit(f"Ejecutando: {' '.join(cmd)}", "SANDBOX_RUN")
        result = await self._run_raw(
            cmd,
            timeout=self.EXEC_TIMEOUT,
            label="run_project",
            cwd=str(self.workspace / "source"),
            stream=True,
        )
        if result.success:
            self._emit("Ejecucion completada sin errores.", "SANDBOX_RUN")
        else:
            errors = self._parse_errors(result.stderr)
            result.errors = errors
            self._emit(
                f"Ejecucion finalizo con codigo {result.return_code}.\n{result.stderr[-600:]}",
                "SANDBOX_ERROR",
            )
        return result

    async def run_startup_check(
        self, entry_command: Optional[str] = None, startup_timeout: int = 12
    ) -> SandboxResult:
        """Start the project and wait up to startup_timeout seconds.

        - Crashes before timeout  → real failure, return errors
        - Still running at timeout → server started OK, kill it, return success
        - Exits with code 0       → script completed cleanly, return success
        """
        if not await self.ensure_venv():
            return SandboxResult(success=False, label="startup", stderr="venv not ready")
        cmd = self._resolve_entry_command(entry_command)
        if not cmd:
            return SandboxResult(success=True, label="startup")

        self._emit(
            f"Verificando arranque: {' '.join(cmd[:3])} (timeout {startup_timeout}s)...",
            "SANDBOX_RUN",
        )
        import time
        t0 = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace / "source"),
            )
            try:
                stdout_raw, stderr_raw = await asyncio.wait_for(
                    proc.communicate(), timeout=startup_timeout
                )
                code = proc.returncode or 0
                stdout = stdout_raw.decode("utf-8", errors="replace")
                stderr = stderr_raw.decode("utf-8", errors="replace")
                duration = time.monotonic() - t0
                if code == 0:
                    self._emit("Proceso completó sin errores.", "SANDBOX_RUN")
                    return SandboxResult(success=True, stdout=stdout, stderr=stderr,
                                         return_code=0, duration=duration, label="startup")
                errors = self._parse_errors(stderr)
                self._emit(f"Proceso crasheó (code={code}):\n{stderr[-500:]}", "SANDBOX_ERROR")
                return SandboxResult(success=False, stdout=stdout, stderr=stderr,
                                     return_code=code, duration=duration,
                                     errors=errors, label="startup")
            except asyncio.TimeoutError:
                # Still running → server started correctly
                try:
                    proc.kill()
                    await proc.communicate()
                except Exception:
                    pass
                duration = time.monotonic() - t0
                self._emit(f"Servidor arrancó correctamente (activo tras {startup_timeout}s).", "SANDBOX_RUN")
                return SandboxResult(success=True, duration=duration, label="startup")
        except Exception as exc:
            self._emit(f"Error al verificar arranque: {exc}", "SANDBOX_ERROR")
            return SandboxResult(success=False, stderr=str(exc), label="startup",
                                 errors=[{"file": "", "line": 0, "message": str(exc)[:200]}])

    async def full_cycle(self, entry_command: Optional[str] = None) -> dict:
        """Run the complete test cycle: venv → install → syntax → run."""
        self._emit("=== Sandbox: iniciando ciclo completo ===", "SANDBOX_INIT")
        results = {}

        results["venv"] = await self.ensure_venv()
        if not results["venv"]:
            return results

        install = await self.install_requirements()
        results["install"] = install.success

        syntax = await self.run_syntax_check()
        results["syntax"] = syntax.success
        results["syntax_errors"] = syntax.errors

        run = await self.run_project(entry_command)
        results["run"] = run.success
        results["run_errors"] = run.errors
        results["stdout"] = run.stdout[-2000:]
        results["stderr"] = run.stderr[-2000:]

        ok = install.success and syntax.success and run.success
        self._emit(
            f"=== Sandbox: ciclo {'EXITOSO' if ok else 'con errores'} ===",
            "SANDBOX_DONE",
        )
        return results

    # ── Internals ────────────────────────────────────────────────────────

    def _python_path(self) -> str:
        if sys.platform == "win32":
            return str(self.venv_path / "Scripts" / "python.exe")
        return str(self.venv_path / "bin" / "python")

    def _pip_path(self) -> str:
        if sys.platform == "win32":
            return str(self.venv_path / "Scripts" / "pip.exe")
        return str(self.venv_path / "bin" / "pip")

    def _resolve_entry_command(self, entry_command: Optional[str]) -> Optional[list[str]]:
        python = self._python_path()
        if entry_command:
            parts = entry_command.strip().split()
            if parts[0] in ("python", "python3"):
                return [python] + parts[1:]
            return parts

        source = self.workspace / "source"
        for candidate in ("main.py", "app.py", "run.py", "server.py", "manage.py"):
            if (source / candidate).exists():
                return [python, candidate]
        return None

    async def _run_raw(
        self,
        cmd: list[str],
        timeout: int,
        label: str,
        cwd: str = ".",
        stream: bool = False,
    ) -> SandboxResult:
        import time
        t0 = time.monotonic()
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        code = 0
        import os as _os
        _env = {k: v for k, v in _os.environ.items() if k != "PYTHONHASHSEED"}
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=_env,
            )
            if stream:
                async def _read_stream(stream_reader, chunks, ev_type):
                    async for raw_line in stream_reader:
                        line = raw_line.decode("utf-8", errors="replace").rstrip()
                        chunks.append(line)
                        self._emit(line, ev_type)

                await asyncio.wait_for(
                    asyncio.gather(
                        _read_stream(proc.stdout, stdout_chunks, "SANDBOX_OUTPUT"),
                        _read_stream(proc.stderr, stderr_chunks, "SANDBOX_ERROR"),
                    ),
                    timeout=timeout,
                )
                await proc.wait()
            else:
                stdout_raw, stderr_raw = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
                stdout_chunks.append(stdout_raw.decode("utf-8", errors="replace"))
                stderr_chunks.append(stderr_raw.decode("utf-8", errors="replace"))

            code = proc.returncode or 0
        except asyncio.TimeoutError:
            stderr_chunks.append(f"TIMEOUT: proceso excedio {timeout}s")
            code = -1
            try:
                proc.kill()
            except Exception:
                pass
        except Exception as e:
            stderr_chunks.append(f"ERROR al ejecutar: {e}")
            code = -1

        stdout = "\n".join(stdout_chunks)
        stderr = "\n".join(stderr_chunks)
        duration = time.monotonic() - t0
        self._log(label, stdout, stderr, code, duration)
        return SandboxResult(
            success=code == 0,
            stdout=stdout,
            stderr=stderr,
            return_code=code,
            duration=duration,
            label=label,
        )

    @staticmethod
    def _parse_errors(stderr: str, hint_file: str = "") -> list[dict]:
        """Extract file/line/message from Python tracebacks."""
        errors: list[dict] = []
        lines = stderr.splitlines()
        tb_re = re.compile(r'File "(.+?)", line (\d+)')
        for i, line in enumerate(lines):
            m = tb_re.search(line)
            if m:
                msg = lines[i + 1].strip() if i + 1 < len(lines) else ""
                errors.append({
                    "file": m.group(1),
                    "line": int(m.group(2)),
                    "message": msg,
                })
        if not errors and stderr.strip():
            errors.append({"file": hint_file, "line": 0, "message": stderr.strip()[:300]})
        return errors

    def _emit(self, message: str, event_type: str) -> None:
        prefix = {
            "SANDBOX_INIT":        "[SANDBOX] ",
            "SANDBOX_ERROR":       "[SANDBOX ERROR] ",
            "SANDBOX_OUTPUT":      "[SANDBOX OUT] ",
            "SANDBOX_RUN":         "[SANDBOX RUN] ",
            "SANDBOX_LOG":         "[SANDBOX] ",
            "SANDBOX_SYNTAX_DONE": "[SANDBOX SYNTAX] ",
            "SANDBOX_DONE":        "[SANDBOX] ",
        }.get(event_type, "[SANDBOX] ")
        print(f"{prefix}{message}")
        self._notify(message, event_type, {
            "project_id": self.project_id,
            "timestamp": datetime.now().isoformat(),
        })

    def _log(self, label: str, stdout: str, stderr: str, code: int, duration: float) -> None:
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            entry = {
                "ts": datetime.now().isoformat(),
                "label": label,
                "code": code,
                "duration_s": round(duration, 2),
                "stdout": stdout[-1000:],
                "stderr": stderr[-1000:],
            }
            with open(self.log_dir / self.LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
