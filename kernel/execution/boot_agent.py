"""
BootAgent — installs and boots a generated project, captures exact errors,
maps them to source files, and runs a targeted fix loop.

Flow:
  1. install()  — run pip install / npm install / go mod tidy / etc.
  2. boot()     — start the process, capture first N lines of stdout/stderr
  3. parse_errors() — map error messages to source files + line numbers
  4. fix_loop() — call Claude/Gemini with exact errors + relevant file content
  5. retry()    — repeat up to MAX_ROUNDS

Returns a BootReport with all attempts and final status.
"""
from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

from kernel.execution.log_collector import LogCollector


MAX_ROUNDS = 3
BOOT_TIMEOUT = 30       # seconds to wait for process to start
INSTALL_TIMEOUT = 120   # seconds for dependency installation
OUTPUT_LINES = 80       # max lines of output to capture


@dataclass
class BootError:
    file: Optional[str]
    line: Optional[int]
    message: str
    raw: str

    def to_dict(self) -> dict:
        return {"file": self.file, "line": self.line, "message": self.message}


@dataclass
class BootAttempt:
    round: int
    install_ok: bool
    install_output: str
    boot_ok: bool
    boot_output: str
    errors: list[BootError] = field(default_factory=list)
    files_fixed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "round": self.round,
            "install_ok": self.install_ok,
            "boot_ok": self.boot_ok,
            "errors": [e.to_dict() for e in self.errors[:5]],
            "files_fixed": self.files_fixed,
        }


@dataclass
class BootReport:
    stack: str
    attempts: list[BootAttempt] = field(default_factory=list)
    final_ok: bool = False
    skipped: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "stack": self.stack,
            "final_ok": self.final_ok,
            "attempts": len(self.attempts),
            "skipped": self.skipped,
            "reason": self.reason,
            "last_errors": [e.to_dict() for e in (self.attempts[-1].errors if self.attempts else [])],
        }


# ─────────────────────────────── stack commands ──

def _detect_commands(source_dir: Path, architecture: dict) -> tuple[list[str], list[str], str]:
    """Returns (install_cmd, run_cmd, stack_name)."""
    stack = architecture.get("stack", {})
    backend = (stack.get("backend") or "").lower()
    frontend = (stack.get("frontend") or "").lower()

    if (source_dir / "requirements.txt").exists() or (source_dir / "pyproject.toml").exists():
        install = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"]
        # Find main entry point
        for candidate in ("main.py", "app.py", "run.py", "server.py", "manage.py"):
            if (source_dir / candidate).exists():
                run = [sys.executable, candidate]
                return install, run, "python"
        run = [sys.executable, "-m", "uvicorn", "main:app", "--port", "8080"]
        return install, run, "python"

    if (source_dir / "package.json").exists():
        npm = "npm"
        install = [npm, "install", "--silent"]
        # Check scripts
        try:
            import json
            pkg = json.loads((source_dir / "package.json").read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            if "dev" in scripts:
                run = [npm, "run", "dev"]
            elif "start" in scripts:
                run = [npm, "start"]
            else:
                run = [npm, "run", "build"]
        except Exception:
            run = [npm, "start"]
        return install, run, "node"

    if (source_dir / "go.mod").exists():
        install = ["go", "mod", "tidy"]
        run = ["go", "run", "."]
        return install, run, "go"

    if (source_dir / "Cargo.toml").exists():
        install = ["cargo", "build"]
        run = ["cargo", "run"]
        return install, run, "rust"

    if any(source_dir.glob("*.csproj")):
        install = ["dotnet", "restore"]
        run = ["dotnet", "run"]
        return install, run, "dotnet"

    if (source_dir / "pom.xml").exists():
        install = ["mvn", "install", "-DskipTests", "-q"]
        run = ["mvn", "spring-boot:run", "-q"]
        return install, run, "java"

    return [], [], "unknown"


# ─────────────────────────────── error parsers ──

_ERROR_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # Python: File "path/file.py", line N
    (re.compile(r'File "([^"]+)", line (\d+)'), "python_traceback", "{file}:{line}"),
    # Python: ModuleNotFoundError: No module named 'X'
    (re.compile(r"ModuleNotFoundError: No module named '([^']+)'"), "python_import", "missing module: {match1}"),
    # Python: ImportError
    (re.compile(r"ImportError: ([^\n]+)"), "python_import", "{match1}"),
    # Python: SyntaxError
    (re.compile(r"SyntaxError: ([^\n]+)"), "python_syntax", "{match1}"),
    # Node: Cannot find module 'X'
    (re.compile(r"Cannot find module '([^']+)'"), "node_import", "missing module: {match1}"),
    # Node: at Object.<file>:line:col
    (re.compile(r'at .+\(([^:)]+):(\d+):\d+\)'), "node_stack", "{file}:{line}"),
    # TypeScript: error TS\d+: ...
    (re.compile(r"error TS\d+: ([^\n]+)"), "typescript_error", "{match1}"),
    # Go: ./file.go:line:col: error
    (re.compile(r'\./?([\w./]+\.go):(\d+):\d+:\s*(.+)'), "go_error", "{file}:{line}: {match3}"),
    # Rust: error[E...]: ...
    (re.compile(r'error\[E\d+\]: ([^\n]+)'), "rust_error", "{match1}"),
    # General: error: ... at file:line
    (re.compile(r'(?:error|Error|ERROR):\s*([^\n]+)'), "general_error", "{match1}"),
]


def parse_errors(output: str, source_dir: Path) -> list[BootError]:
    errors: list[BootError] = []
    lines = output.splitlines()

    for line in lines:
        for pattern, kind, _ in _ERROR_PATTERNS:
            m = pattern.search(line)
            if not m:
                continue

            file_ref: Optional[str] = None
            line_ref: Optional[int] = None

            if kind in ("python_traceback", "node_stack", "go_error"):
                raw_file = m.group(1)
                try:
                    line_ref = int(m.group(2))
                except (IndexError, ValueError):
                    pass
                # Resolve to source_dir-relative path
                fp = Path(raw_file)
                if fp.is_absolute():
                    try:
                        file_ref = str(fp.relative_to(source_dir)).replace("\\", "/")
                    except ValueError:
                        file_ref = raw_file
                else:
                    file_ref = str(fp).replace("\\", "/")

            message = m.group(0)
            errors.append(BootError(file=file_ref, line=line_ref, message=message[:200], raw=line[:200]))

            if len(errors) >= 20:
                return errors

    return errors


# ─────────────────────────────── subprocess helpers ──

async def _run_cmd(cmd: list[str], cwd: Path, timeout: int) -> tuple[bool, str]:
    """Run command, return (success, combined_output)."""
    if not cmd:
        return True, ""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return False, f"Timeout después de {timeout}s"
        output = (stdout or b"").decode("utf-8", errors="replace")
        return proc.returncode == 0, output[-4000:]  # last 4000 chars
    except FileNotFoundError as e:
        return False, f"Comando no encontrado: {e}"
    except Exception as e:
        return False, str(e)


async def _boot_and_capture(cmd: list[str], cwd: Path, timeout: int) -> tuple[bool, str]:
    """Start process, wait timeout seconds, capture output, check if still alive."""
    if not cmd:
        return True, ""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        lines_collected = []
        deadline = asyncio.get_event_loop().time() + timeout

        async def _read_lines():
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                lines_collected.append(line.decode("utf-8", errors="replace").rstrip())
                if len(lines_collected) >= OUTPUT_LINES:
                    break

        try:
            await asyncio.wait_for(_read_lines(), timeout=timeout)
        except asyncio.TimeoutError:
            pass

        output = "\n".join(lines_collected)

        # Check if crashed
        await asyncio.sleep(0.5)
        alive = proc.returncode is None
        if not alive and proc.returncode != 0:
            proc.kill()
            return False, output
        proc.kill()  # clean up after capture
        return alive or True, output

    except FileNotFoundError as e:
        return False, f"Comando no encontrado: {e}"
    except Exception as e:
        return False, str(e)


# ─────────────────────────────── main class ──

class BootAgent:
    """
    Installs and boots a generated project, captures errors,
    and runs a targeted AI fix loop.
    """

    def __init__(self, claude_driver=None, gemini_driver=None, context_builder=None, notify_fn: Optional[Callable] = None):
        self.claude = claude_driver
        self.gemini = gemini_driver
        self.builder = context_builder
        self.notify = notify_fn or (lambda *a, **kw: None)
        self._log_collector = LogCollector(max_bytes_per_tool=3_000, max_age_minutes=30)

    async def run(self, source_dir: Path, architecture: dict, blueprint: dict) -> BootReport:
        install_cmd, run_cmd, stack = _detect_commands(source_dir, architecture)
        report = BootReport(stack=stack)

        if not install_cmd and not run_cmd:
            report.skipped = True
            report.reason = "Stack no reconocido para boot automático."
            self.notify(report.reason, "LOG", {})
            return report

        self.notify(
            f"BootAgent [{stack}]: instalando dependencias…",
            "PHASE_START",
            {"phase": "boot_agent", "stack": stack},
        )

        for round_idx in range(MAX_ROUNDS):
            attempt = BootAttempt(round=round_idx + 1, install_ok=False, install_output="", boot_ok=False, boot_output="")

            # Step 1: Install
            install_ok, install_out = await _run_cmd(install_cmd, source_dir, INSTALL_TIMEOUT)
            attempt.install_ok = install_ok
            attempt.install_output = install_out[-2000:]

            if not install_ok:
                self.notify(
                    f"BootAgent ronda {round_idx+1}: instalación falló.",
                    "HEALTH_WARN",
                    {"round": round_idx + 1, "output": install_out[-500:]},
                )
                errors = parse_errors(install_out, source_dir)
                attempt.errors = errors
                report.attempts.append(attempt)
                fixed = await self._fix_errors(errors, install_out, source_dir, blueprint, architecture)
                attempt.files_fixed = fixed
                if not fixed:
                    break
                continue

            self.notify(f"BootAgent ronda {round_idx+1}: dependencias instaladas. Iniciando…", "LOG", {})

            # Step 2: Boot
            boot_ok, boot_out = await _boot_and_capture(run_cmd, source_dir, BOOT_TIMEOUT)
            attempt.boot_ok = boot_ok
            attempt.boot_output = boot_out[-2000:]

            if boot_ok:
                self.notify(
                    f"BootAgent: proyecto arranca correctamente en ronda {round_idx+1}.",
                    "LOG",
                    {"round": round_idx + 1, "stack": stack},
                )
                report.final_ok = True
                report.attempts.append(attempt)
                break

            # Boot failed
            errors = parse_errors(boot_out, source_dir)
            attempt.errors = errors
            report.attempts.append(attempt)

            self.notify(
                f"BootAgent ronda {round_idx+1}: el proyecto no arranca — {len(errors)} error(es) detectados.",
                "HEALTH_WARN",
                {"round": round_idx + 1, "errors": [e.to_dict() for e in errors[:3]]},
            )

            fixed = await self._fix_errors(errors, boot_out, source_dir, blueprint, architecture)
            attempt.files_fixed = fixed
            if not fixed:
                break

        if not report.final_ok:
            self.notify(
                f"BootAgent: proyecto no pudo arrancar tras {len(report.attempts)} intento(s).",
                "HEALTH_WARN",
                report.to_dict(),
            )

        return report

    async def _fix_errors(
        self,
        errors: list[BootError],
        raw_output: str,
        source_dir: Path,
        blueprint: dict,
        architecture: dict,
    ) -> list[str]:
        """Ask Claude/Gemini to fix the errors. Returns list of patched file paths."""
        if not errors or (not self.claude and not self.gemini):
            return []

        # Detect stack for log collection
        stack = architecture.get("stack", {})
        stack_name = (stack.get("backend") or stack.get("frontend") or "").lower()
        extra_stacks = [
            v.lower() for v in stack.values()
            if isinstance(v, str) and v.lower() != stack_name
        ]

        # Collect system + workspace logs relevant to this failure
        log_context = self._log_collector.collect(
            stack=stack_name or "node",
            workspace=source_dir,
            extra_stacks=extra_stacks,
        )
        if log_context:
            self.notify(
                "BootAgent: logs del sistema recolectados para contexto de corrección.",
                "LOG",
                {"log_bytes": len(log_context)},
            )

        # Build context: relevant source files
        file_snippets = ""
        seen: set[str] = set()
        for err in errors[:6]:
            if err.file and err.file not in seen:
                seen.add(err.file)
                fp = source_dir / err.file
                if fp.exists():
                    content = fp.read_text(encoding="utf-8", errors="ignore")[:2500]
                    file_snippets += f"\n### {err.file}\n```\n{content}\n```\n"

        errors_text = "\n".join(
            f"  {'→ ' + err.file + ':' + str(err.line) if err.file else '  '} {err.message}"
            for err in errors[:10]
        )

        task = (
            f"El proyecto no arranca. Estos son los errores:\n\n{errors_text}\n\n"
            f"OUTPUT COMPLETO:\n{raw_output[-1500:]}\n\n"
            f"ARCHIVOS RELEVANTES:{file_snippets}"
            + (f"\n{log_context}" if log_context else "")
            + "\n\nCorregí los archivos necesarios para que el proyecto arranque. "
            f'Respondé con JSON array: [{{"file": "ruta/relativa", "content": "código completo corregido"}}]\n'
            f"Solo archivos que necesitan cambios reales."
        )

        for driver, provider in [(self.claude, "claude"), (self.gemini, "gemini")]:
            if driver is None:
                continue
            try:
                payload = self.builder.build_payload(provider, "code_fixer", task)
                raw = await driver.prompt(payload["system"], payload["user"])
                if hasattr(raw, "content"):
                    raw = raw.content

                import json as _json, re as _re
                # Try array extraction
                m = _re.search(r"\[.*\]", raw, _re.DOTALL)
                if not m:
                    continue
                fixes = _json.loads(m.group(0))
                if not isinstance(fixes, list):
                    continue

                patched: list[str] = []
                for fix in fixes:
                    fpath = fix.get("file", "")
                    content = fix.get("content", "")
                    if not fpath or not content:
                        continue
                    out = source_dir / fpath
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(content, encoding="utf-8")
                    patched.append(fpath)
                    self.notify(
                        f"BootAgent corrigió: {fpath}",
                        "FILE_GENERATED",
                        {"filename": fpath, "code": content, "validated": False, "phase": "boot_fix"},
                    )

                if patched:
                    return patched

            except Exception as e:
                self.notify(f"BootAgent fix error: {e}", "LOG", {})
                continue

        return []
