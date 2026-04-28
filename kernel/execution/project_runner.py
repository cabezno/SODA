from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from kernel.execution.stack_detector import StackDetector
from kernel.execution.port_manager import PortManager
from kernel.execution.log_monitor import LogMonitor


_MAX_LOG_BYTES = 50 * 1024 * 1024  # 50 MB cap on _soda_launch.log


def _kill_process_tree(proc) -> None:
    """Kill the process and its entire child tree.

    On Windows, proc.kill() only kills cmd.exe (the shell), leaving child
    processes (node, python, uvicorn, etc.) running as orphans that hold
    onto the port. taskkill /F /T kills the full tree atomically.
    On Unix, proc.kill() is sufficient because SIGKILL propagates.
    """
    if proc is None:
        return
    pid = getattr(proc, "pid", None)
    if not pid:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    else:
        try:
            proc.kill()
        except Exception:
            pass


# ── Global process registry ───────────────────────────────────────────────────
# Maps project_id → ProcessHandle so we can kill, query and log running projects.
@dataclass
class ProcessHandle:
    project_id: str
    pid: int
    command: str
    cwd: str
    started_at: str
    log_path: str
    proc: object = field(repr=False, default=None)  # asyncio.subprocess.Process

    def is_alive(self) -> bool:
        if self.proc is None:
            return False
        return self.proc.returncode is None

    def kill(self) -> None:
        if self.proc and self.proc.returncode is None:
            _kill_process_tree(self.proc)

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "pid": self.pid,
            "command": self.command,
            "cwd": self.cwd,
            "started_at": self.started_at,
            "log_path": self.log_path,
            "alive": self.is_alive(),
        }


_PROCESS_REGISTRY: dict[str, ProcessHandle] = {}


@dataclass
class RuntimeHealth:
    stack: str
    working_dir: str
    has_run_command: bool
    has_install_command: bool
    source_exists: bool
    manifest_found: bool
    detected_manifest: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RuntimeSmoke:
    attempted: bool
    passed: bool
    target_url: str
    reason: str
    status_code: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InstallResult:
    success: bool
    stdout: str
    stderr: str
    returncode: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LaunchResult:
    launched: bool
    pid: int
    url: str
    error: str = ""
    log_path: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class ProjectRunner:
    """
    Full project lifecycle: preflight → install → launch → smoke → cleanup.

    install() and launch() are async and run subprocesses via asyncio without
    blocking the event loop. smoke_check() remains sync for backward compat.
    """

    INSTALL_TIMEOUT = 180   # seconds for dependency installation
    LAUNCH_WAIT_S = 8       # seconds to wait for app to be ready after launch

    # ── Process registry helpers ─────────────────────────────────────────────

    @staticmethod
    def register_process(handle: ProcessHandle) -> None:
        _PROCESS_REGISTRY[handle.project_id] = handle

    @staticmethod
    def get_process(project_id: str) -> Optional[ProcessHandle]:
        return _PROCESS_REGISTRY.get(project_id)

    @staticmethod
    def list_processes() -> list[dict]:
        return [h.to_dict() for h in _PROCESS_REGISTRY.values()]

    @staticmethod
    def kill_process(project_id: str) -> bool:
        handle = _PROCESS_REGISTRY.get(project_id)
        if handle:
            handle.kill()
            _PROCESS_REGISTRY.pop(project_id, None)
            return True
        return False

    @staticmethod
    def kill_all() -> None:
        for h in list(_PROCESS_REGISTRY.values()):
            h.kill()
        _PROCESS_REGISTRY.clear()

    # ── Command helpers ──────────────────────────────────────────────────────

    @staticmethod
    def normalize_run_command(source_dir: Path, run_command: str) -> tuple[Path, str]:
        import re as _re
        cmd = (run_command or "").strip()
        cwd = source_dir
        # Handle both "cd dir && cmd" and "cd /d drive:\path && cmd" (Windows)
        match = _re.match(r'^cd(?:\s+/d)?\s+"?([^"&]+?)"?\s*&&\s*(.+)$', cmd, _re.IGNORECASE)
        if match:
            subdir = match.group(1).strip().strip('"')
            rest   = match.group(2).strip()
            # Try as absolute path first, then relative
            candidate = Path(subdir) if Path(subdir).is_absolute() else source_dir / subdir
            if candidate.exists():
                cwd = candidate
                cmd = rest
        return cwd, cmd

    def detect_stack(self, run_command: str, install_command: str = "") -> str:
        return StackDetector.detect(run_command, install_command)

    def _find_manifest_dir(self, root: Path, stack: str) -> tuple[Path, str]:
        patterns = {
            "python": ["pyproject.toml", "requirements.txt", "setup.py"],
            "node":   ["package.json"],
            "dotnet": ["*.csproj", "*.fsproj", "*.vbproj"],
            "go":     ["go.mod"],
            "rust":   ["Cargo.toml"],
            "static": ["*.html"],
            "unknown":["pyproject.toml", "package.json", "*.csproj", "go.mod", "Cargo.toml", "*.html"],
        }
        for pat in patterns.get(stack, patterns["unknown"]):
            hits = [p for p in root.rglob(pat) if "node_modules" not in str(p)]
            if hits:
                return hits[0].parent, hits[0].name
        return root, ""

    def resolve_working_dir(self, source_dir: Path, run_command: str, install_command: str = "") -> tuple[Path, str]:
        cwd, cmd = self.normalize_run_command(source_dir, run_command)
        stack = self.detect_stack(cmd, install_command)
        workdir, _ = self._find_manifest_dir(cwd, stack)
        return workdir, cmd

    def preflight(self, project_workspace: Path, run_command: str, install_command: str = "") -> RuntimeHealth:
        source_dir = project_workspace / "source"
        root = source_dir if source_dir.exists() else project_workspace
        stack = self.detect_stack(run_command, install_command)
        workdir, manifest = self._find_manifest_dir(root, stack)
        return RuntimeHealth(
            stack=stack,
            working_dir=str(workdir),
            has_run_command=bool((run_command or "").strip()),
            has_install_command=bool((install_command or "").strip()),
            source_exists=source_dir.exists(),
            manifest_found=bool(manifest),
            detected_manifest=manifest,
        )

    @staticmethod
    def infer_runtime_url(run_command: str, stack: str) -> str:
        return PortManager.infer_url(run_command, stack)

    # ------------------------------------------------------------------
    # Async: install dependencies
    # ------------------------------------------------------------------

    async def install(
        self,
        project_workspace: Path,
        install_command: str,
        run_command: str = "",
        timeout: int = INSTALL_TIMEOUT,
    ) -> InstallResult:
        """Run the install command inside the project's working directory."""
        if not (install_command or "").strip():
            return InstallResult(success=True, stdout="", stderr="", returncode=0)

        source_dir = project_workspace / "source"
        root = source_dir if source_dir.exists() else project_workspace
        stack = self.detect_stack(run_command, install_command)
        workdir, _ = self._find_manifest_dir(root, stack)

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        try:
            proc = await asyncio.create_subprocess_shell(
                install_command,
                cwd=str(workdir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                _kill_process_tree(proc)
                return InstallResult(
                    success=False, stdout="", stderr=f"Timeout after {timeout}s", returncode=-1
                )
            return InstallResult(
                success=(proc.returncode == 0),
                stdout=stdout_b.decode("utf-8", errors="replace")[-3000:],
                stderr=stderr_b.decode("utf-8", errors="replace")[-2000:],
                returncode=proc.returncode or 0,
            )
        except Exception as e:
            return InstallResult(success=False, stdout="", stderr=str(e), returncode=-1)

    # ------------------------------------------------------------------
    # Async: launch project in background
    # ------------------------------------------------------------------

    async def launch(
        self,
        project_workspace: Path,
        run_command: str,
        install_command: str = "",
        use_docker: bool = False,
    ) -> LaunchResult:
        """Start the project process in the background. Returns PID immediately.

        When use_docker=True the project is launched inside a DockerSandbox container
        instead of a raw subprocess. Requires Docker Desktop (Windows npipe).
        """
        if not (run_command or "").strip():
            return LaunchResult(launched=False, pid=0, url="", error="no run command")

        if use_docker:
            return await self._launch_docker(project_workspace, run_command, install_command)

        source_dir = project_workspace / "source"
        root = source_dir if source_dir.exists() else project_workspace
        cwd, cmd = self.normalize_run_command(root, run_command)
        stack = self.detect_stack(cmd, install_command)
        workdir, _ = self._find_manifest_dir(cwd, stack)
        url = self.infer_runtime_url(cmd, stack)

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        log_path = project_workspace / "_soda_launch.log"
        try:
            # Use PIPE for stdout/stderr so the file handle is owned by the process
            # and we can read it independently. Write to log file via a background task.
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=str(workdir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )

            async def _stream_to_log(p, path: Path) -> None:
                try:
                    written = 0
                    with open(str(path), "w", encoding="utf-8", errors="replace") as f:
                        while True:
                            line = await p.stdout.readline()
                            if not line:
                                break
                            decoded = line.decode("utf-8", errors="replace")
                            f.write(decoded)
                            f.flush()
                            written += len(decoded.encode("utf-8", errors="replace"))
                            if written >= _MAX_LOG_BYTES:
                                f.write("\n[SODA] Log truncado — límite de 50 MB alcanzado.\n")
                                break
                except Exception:
                    pass

            asyncio.create_task(_stream_to_log(proc, log_path))

            pid = proc.pid or 0
            handle = ProcessHandle(
                project_id=str(project_workspace.name),
                pid=pid,
                command=cmd,
                cwd=str(workdir),
                started_at=datetime.utcnow().isoformat(),
                log_path=str(log_path),
                proc=proc,
            )
            self.register_process(handle)
            return LaunchResult(launched=True, pid=pid, url=url, log_path=str(log_path))
        except Exception as e:
            from kernel.execution.execution_error_log import ExecutionErrorLog
            ExecutionErrorLog.record(
                str(project_workspace.name), "launch", str(e), "LaunchError",
                {"command": cmd, "cwd": str(workdir)},
            )
            return LaunchResult(launched=False, pid=0, url=url, error=str(e))

    async def _launch_docker(
        self,
        project_workspace: Path,
        run_command: str,
        install_command: str = "",
    ) -> LaunchResult:
        """Launch the project inside a DockerSandbox container."""
        try:
            from kernel.execution.docker_sandbox import DockerSandbox
        except ImportError:
            return LaunchResult(launched=False, pid=0, url="", error="DockerSandbox not available")

        source_dir = project_workspace / "source"
        root = source_dir if source_dir.exists() else project_workspace
        cwd, cmd = self.normalize_run_command(root, run_command)
        stack = self.detect_stack(cmd, install_command)
        url = self.infer_runtime_url(cmd, stack)

        try:
            sandbox = DockerSandbox()
            result = sandbox.run_tests(str(root), install_command, run_command)
            if result.get("success"):
                return LaunchResult(launched=True, pid=0, url=url, log_path="")
            return LaunchResult(
                launched=False, pid=0, url=url,
                error=result.get("stderr", "Docker launch failed")[:300],
            )
        except Exception as e:
            return LaunchResult(launched=False, pid=0, url=url, error=str(e))

    # ------------------------------------------------------------------
    # Async: full setup + verify pipeline
    # ------------------------------------------------------------------

    async def setup_and_verify(
        self,
        project_workspace: Path,
        run_command: str,
        install_command: str = "",
        notify_fn=None,
    ) -> dict:
        """install → launch → wait → smoke.  Returns combined result dict."""
        _notify = notify_fn or (lambda msg, t, d: None)

        # Environment detection + venv for Python projects
        source_dir = project_workspace / "source"
        root = source_dir if source_dir.exists() else project_workspace
        _stack = self.detect_stack(run_command, install_command)
        if _stack == "python":
            try:
                from kernel.execution.environment_detector import EnvironmentDetector
                from kernel.execution.venv_manager import VenvManager
                env_report = EnvironmentDetector().detect(root)
                for w in env_report.warnings:
                    _notify(w, "HEALTH_WARN", {"phase": "env_check"})
                venv_info = VenvManager().ensure(root, _notify)
                # Replace bare python executable in string commands with venv python
                if venv_info.python != sys.executable:
                    install_command = install_command.replace(sys.executable, venv_info.python)
                    run_command = run_command.replace(sys.executable, venv_info.python)
            except Exception:
                pass  # detection is best-effort, never block the pipeline

        # 1. Install
        if (install_command or "").strip():
            _notify(f"Instalando dependencias: {install_command[:60]}…", "LOG", {"phase": "install"})
            install_res = await self.install(project_workspace, install_command, run_command)
            if not install_res.success:
                _notify(
                    f"Instalación falló (rc={install_res.returncode}): {install_res.stderr[:200]}",
                    "HEALTH_WARN",
                    {"phase": "install", "returncode": install_res.returncode},
                )
        else:
            install_res = InstallResult(success=True, stdout="", stderr="", returncode=0)

        # 2. Launch
        _notify(f"Lanzando proyecto: {run_command[:60]}…", "LOG", {"phase": "launch"})
        launch_res = await self.launch(project_workspace, run_command, install_command)
        if not launch_res.launched:
            _notify(f"No se pudo lanzar: {launch_res.error}", "HEALTH_WARN", {"phase": "launch"})

        # 3. Wait for app readiness; stream logs via LogMonitor
        log_monitor: Optional[LogMonitor] = None
        if launch_res.launched and launch_res.log_path:
            import pathlib as _pl
            log_monitor = LogMonitor(
                _pl.Path(launch_res.log_path),
                on_entry=lambda e: _notify(e.line[:200], "LOG", {"severity": e.severity, "source": "launch"}),
            )
            log_monitor.start()

        if launch_res.launched and launch_res.url:
            _notify(f"Esperando que la app esté lista en {launch_res.url}…", "LOG", {})
            await asyncio.sleep(self.LAUNCH_WAIT_S)

        # 4. Smoke check with retry
        smoke = await self.smoke_check_with_retry(
            project_workspace=project_workspace,
            run_command=run_command,
            install_command=install_command,
            target_url=launch_res.url or None,
            attempts=4,
            delay_s=2.0,
        )
        if smoke.passed:
            _notify(f"App respondiendo en {smoke.target_url}", "LOG", {})
        else:
            _notify(
                f"Smoke check no pasó ({smoke.reason})",
                "HEALTH_WARN",
                {"phase": "smoke", "url": smoke.target_url},
            )

        # Surface log errors found during startup
        log_summary = {}
        if log_monitor:
            errors = log_monitor.last_errors(5)
            log_summary = log_monitor.summary()
            if errors:
                _notify(
                    f"{len(errors)} errores en logs de arranque",
                    "HEALTH_WARN",
                    {"phase": "log_monitor", "errors": [e.line for e in errors]},
                )
            log_monitor.stop()

        return {
            "install": install_res.to_dict(),
            "launch": launch_res.to_dict(),
            "smoke": smoke.to_dict(),
            "log_summary": log_summary,
        }

    # ------------------------------------------------------------------
    # Sync smoke check (backward-compat, used by server.py)
    # ------------------------------------------------------------------

    def smoke_check(
        self,
        project_workspace: Path,
        run_command: str,
        install_command: str = "",
        target_url: Optional[str] = None,
        timeout_s: float = 1.5,
    ) -> RuntimeSmoke:
        health = self.preflight(project_workspace, run_command, install_command)
        if not health.has_run_command:
            return RuntimeSmoke(False, False, "", "no_run_command", 0)

        # Non-HTTP stacks (go, rust, static, unknown) cannot be probed via HTTP.
        # Return non_http_stack (not a failure) instead of probing and failing.
        if not target_url and not StackDetector.is_http_probe_applicable(health.stack):
            return RuntimeSmoke(False, False, "", "non_http_stack", 0)

        url = target_url or self.infer_runtime_url(run_command, health.stack)
        if not url:
            return RuntimeSmoke(False, False, "", "no_probe_target", 0)

        try:
            response = requests.get(url, timeout=timeout_s)
            ok = 200 <= response.status_code < 500
            return RuntimeSmoke(True, ok, url, "http_ok" if ok else "http_error", response.status_code)
        except requests.ConnectionError:
            return RuntimeSmoke(True, False, url, "connection_error", 0)
        except requests.Timeout:
            return RuntimeSmoke(True, False, url, "timeout", 0)
        except Exception:
            return RuntimeSmoke(True, False, url, "probe_error", 0)

    async def smoke_check_with_retry(
        self,
        project_workspace: Path,
        run_command: str,
        install_command: str = "",
        target_url: Optional[str] = None,
        timeout_s: float = 2.0,
        attempts: int = 4,
        delay_s: float = 2.0,
    ) -> RuntimeSmoke:
        last = RuntimeSmoke(False, False, "", "no_attempt", 0)
        for idx in range(max(1, attempts)):
            result = self.smoke_check(
                project_workspace=project_workspace,
                run_command=run_command,
                install_command=install_command,
                target_url=target_url,
                timeout_s=timeout_s,
            )
            if result.passed:
                return result
            last = result
            if idx < attempts - 1 and delay_s > 0:
                await asyncio.sleep(delay_s)
        return last
