"""
BootAgent — installs and boots a generated project, captures exact errors,
maps them to source files, and runs a targeted fix loop.
Strictly uses DockerSandbox for all executions (Zero-Host Policy).
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

from kernel.execution.log_collector import LogCollector
from kernel.docker_sandbox import DockerSandbox, SandboxResult

MAX_ROUNDS = 5
BOOT_TIMEOUT = 45 
INSTALL_TIMEOUT = 180
OUTPUT_LINES = 100
HEALTH_CHECK_TIMEOUT = 15
HEALTH_CHECK_INTERVAL = 0.5

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

_FATAL_ENV_ERRORS = [
    (re.compile(r"CMAKE_CXX_COMPILER not set|CMAKE_C_COMPILER not set|No CMAKE_CXX_COMPILER", re.I), "Falta compilador C++. Instalá Build Tools."),
    (re.compile(r"'cmake' is not recognized|cmake.*not found", re.I), "CMake no instalado."),
    (re.compile(r"'cargo' is not recognized|cargo.*not found", re.I), "Rust no instalado."),
    (re.compile(r"'docker' is not recognized|docker.*not found", re.I), "Docker no instalado."),
    (re.compile(r"No space left on device|ENOSPC", re.I), "Sin espacio en disco."),
]

def _detect_fatal_env_error(output: str) -> str | None:
    for pattern, fix in _FATAL_ENV_ERRORS:
        if pattern.search(output): return fix
    return None

def _sanitize_package_json(pkg_path: Path) -> None:
    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        changed = False
        for s in ("dependencies", "devDependencies"):
            deps = pkg.get(s, {})
            bad = [k for k in deps if k.startswith(("@/", "~", "."))]
            for k in bad:
                del deps[k]
                changed = True
        if changed:
            pkg_path.write_text(json.dumps(pkg, indent=2), encoding="utf-8")
    except Exception: pass

def _bootstrap_env(source_dir: Path, notify=None) -> None:
    candidates = [(".env.example", ".env"), (".env.example", ".env.local")]
    for src_name, dst_name in candidates:
        src, dst = source_dir / src_name, source_dir / dst_name
        if src.exists() and not dst.exists():
            try:
                import shutil
                shutil.copy2(src, dst)
            except Exception: pass

def _detect_commands(source_dir: Path, architecture: dict) -> tuple[list[str], list[str], str, Path]:
    # Recursive search for manifests
    py_reqs = list(source_dir.rglob("requirements.txt"))
    py_proj = list(source_dir.rglob("pyproject.toml"))
    pkg_jsons = list(source_dir.rglob("package.json"))
    dc_files = list(source_dir.rglob("docker-compose.y*ml"))

    # Check if docker is actually available in the system
    import shutil
    docker_available = shutil.which("docker") is not None

    # Docker Compose wins for microservices ONLY if docker is installed
    if dc_files and docker_available:
        f = dc_files[0]
        cmd = "docker-compose" # simplify
        return [cmd, "-f", f.name, "build"], [cmd, "-f", f.name, "up", "-d"], "docker-compose", f.parent

    # Node.js
    if pkg_jsons:
        f = pkg_jsons[0]
        _sanitize_package_json(f)
        return ["npm", "install"], ["npm", "start"], "node", f.parent

    # Python
    if py_reqs or py_proj or any(f.suffix == ".py" for f in source_dir.rglob("*")):
        manifest = (py_reqs or py_proj)[0] if (py_reqs or py_proj) else None
        eff_cwd = manifest.parent if manifest else source_dir
        req_file = "requirements.txt" if (eff_cwd / "requirements.txt").exists() else None
        
        # In Zero-Host, we use the python interpreter inside the container.
        # sys.executable refers to the host's python, so we replace it with "python" or "pip".
        install = ["pip", "install", "-r", req_file] if req_file else []
        
        # Priority 1: Standard entry points
        for c in ("main.py", "app.py", "run.py", "server.py", "api.py"):
            if (eff_cwd / c).exists():
                return install, ["python", c], "python", eff_cwd
        
        # Priority 2: Files with __main__
        for py_file in eff_cwd.glob("*.py"):
            try:
                if "__main__" in py_file.read_text(encoding="utf-8"):
                    return install, ["python", py_file.name], "python", eff_cwd
            except Exception: pass
            
        # Priority 3: First .py file found (Desperate fallback)
        all_pys = list(eff_cwd.glob("*.py"))
        if all_pys:
            return install, ["python", all_pys[0].name], "python", eff_cwd

    return [], [], "unknown", source_dir

def parse_errors(output: str, source_dir: Path) -> list[BootError]:
    errors = []
    # Python Tracebacks
    m_py = re.findall(r'File "([^"]+)", line (\d+)', output)
    for f, l in m_py:
        errors.append(BootError(file=f, line=int(l), message="Traceback", raw=f"File {f}, line {l}"))
    
    # Node/NPM specific errors
    if "npm ERR!" in output:
        msg = re.search(r'npm ERR! (.*)', output)
        errors.append(BootError(file=None, line=None, message=msg.group(1) if msg else "NPM Install Error", raw=output))
    
    # Module missing (Python or Node)
    if "ModuleNotFoundError" in output or "Cannot find module" in output:
        errors.append(BootError(file=None, line=None, message="Missing Dependency", raw=output))
        
    if not errors and output.strip():
        # Catch-all for generic failure
        errors.append(BootError(file=None, line=None, message="Unknown Boot Error", raw=output[:500]))
        
    return errors[:20]

class BootAgent:
    def __init__(self, gemini_driver=None, claude_driver=None, context_builder=None, notify_fn=None):
        self.gemini = gemini_driver
        self.notify = notify_fn or (lambda *a: None)
        self.builder = context_builder
        self.sandbox = DockerSandbox()

    async def run(self, source_dir: Path, architecture: dict, blueprint: dict) -> BootReport:
        install_cmd, run_cmd, stack, eff_cwd = _detect_commands(source_dir, architecture)
        report = BootReport(stack=stack)

        if not install_cmd and not run_cmd:
            report.skipped = True
            report.reason = "No se detectaron comandos de instalación o ejecución."
            return report

        _bootstrap_env(eff_cwd, self.notify)

        self.notify(f"BootAgent: Iniciando despliegue en Sandbox Aislado (Stack: {stack})", "LOG")

        for r in range(MAX_ROUNDS):
            attempt = BootAttempt(round=r+1, install_ok=False, install_output="", boot_ok=False, boot_output="")
            
            # Ejecutamos el proyecto completo en el Sandbox (ASYNC)
            self.notify(f"BootAgent: Ronda {r+1}/{MAX_ROUNDS} en Sandbox...", "LOG")
            
            result: SandboxResult = await self.sandbox.run_project(
                source_dir=eff_cwd,
                install_cmd=install_cmd,
                run_cmd=run_cmd,
                timeout=BOOT_TIMEOUT
            )
            
            # Analizar el resultado
            output = result.stdout + "\n" + result.stderr
            if "DOCKER_UNAVAILABLE" in output:
                report.final_ok = False
                report.reason = "CRÍTICO: SODA requiere Docker para ejecución segura (Zero-Host Policy)."
                self.notify(report.reason, "ERROR")
                return report

            if not result.success:
                attempt.install_ok = "pip install" not in output.lower() or "successfully installed" in output.lower()
                attempt.boot_ok = False
                attempt.boot_output = output
                attempt.errors = parse_errors(output, eff_cwd)
                report.attempts.append(attempt)
                
                self.notify(f"BootAgent: Fallo en ronda {r+1}. Intentando reparación...", "WARNING")
                await self._fix_errors(attempt.errors, output, eff_cwd)
                continue
            else:
                attempt.install_ok = True
                attempt.boot_ok = True
                attempt.boot_output = output
                report.final_ok = True
                report.attempts.append(attempt)
                self.notify(f"BootAgent: Proyecto desplegado exitosamente en el Sandbox.", "SUCCESS")
                break

        if not report.final_ok and not report.reason:
            last_attempt = report.attempts[-1] if report.attempts else None
            if last_attempt and last_attempt.errors:
                report.reason = "; ".join(e.message for e in last_attempt.errors[:3])
            else:
                report.reason = "Límite de reintentos alcanzado sin éxito en el Sandbox."

        return report

    async def _fix_errors(self, errors: list[BootError], output: str, cwd: Path):
        """Implementation of AI fix loop: sends the error to the IA to get a correction."""
        if not self.gemini: return
        
        self.notify(f"BootAgent: detectados {len(errors)} errores. Iniciando auto-reparación...", "LOG")
        
        # Collect relevant files
        files_to_send = set()
        for e in errors:
            if e.file:
                # Resolve relative or absolute path
                p = Path(e.file)
                if not p.is_absolute(): p = cwd / p
                if p.exists(): files_to_send.add(p)

        combined_code = ""
        for f in files_to_send:
            try:
                rel_path = f.relative_to(cwd)
                combined_code += f"\n--- FILE: {rel_path} ---\n{f.read_text(encoding='utf-8')}\n"
            except Exception: pass

        sys_p = (
            "Eres el Ingeniero de Debugging de SODA (Nivel L3).\n"
            "Tu misión es corregir errores de ejecución (Tracebacks, TypeErrors, ModuleNotFound).\n"
            "MANDATORIO: Devuelve solo los archivos corregidos usando <FILE path='...'> tags.\n"
            "Analiza el error cuidadosamente. Si es un 'non-default argument follows default', reordena los campos."
        )
        
        user_msg = (
            f"ERROR DE EJECUCIÓN EN SANDBOX:\n{output}\n\n"
            f"CÓDIGO RELACIONADO:\n{combined_code}\n\n"
            "Corrige los archivos para que la aplicación arranque sin errores en el contenedor."
        )
        
        try:
            resp = await self.gemini.call(system_prompt=sys_p, user_message=user_msg, max_tokens=8192)
            from kernel.validators.v2.polyglot_validator import PolyglotValidator
            corrected_files = PolyglotValidator.extract_files(resp.content)
            
            for path, content in corrected_files.items():
                dest = cwd / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
                self.notify(f"BootAgent: archivo {path} reparado.", "LOG")
                
        except Exception as e:
            self.notify(f"BootAgent: fallo crítico en la reparación: {e}", "ERROR")
