from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass
class VenvInfo:
    path: Path
    python: str    # absolute path to python executable inside venv
    pip: str       # absolute path to pip executable inside venv
    created_now: bool


class VenvManager:
    """Creates and manages a per-workspace .venv virtual environment."""

    def ensure(
        self,
        workspace: Path,
        notify: Optional[Callable] = None,
    ) -> VenvInfo:
        _notify = notify or (lambda *a, **kw: None)
        venv_dir = workspace / ".venv"
        created_now = False

        if not venv_dir.exists():
            _notify(
                f"VenvManager: creando entorno virtual en {venv_dir}",
                "LOG",
                {"phase": "venv_create", "path": str(venv_dir)},
            )
            try:
                subprocess.run(
                    [sys.executable, "-m", "venv", str(venv_dir)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                created_now = True
                _notify(
                    "VenvManager: entorno virtual creado",
                    "LOG",
                    {"phase": "venv_create", "status": "ok"},
                )
            except subprocess.CalledProcessError as e:
                _notify(
                    f"VenvManager: error creando venv — {e.stderr.strip()[:200]}",
                    "HEALTH_WARN",
                    {"phase": "venv_create", "error": str(e)},
                )
                return self._fallback_info(workspace)
            except Exception as e:
                _notify(
                    f"VenvManager: error inesperado creando venv — {e}",
                    "HEALTH_WARN",
                    {"phase": "venv_create", "error": str(e)},
                )
                return self._fallback_info(workspace)

        return VenvInfo(
            path=venv_dir,
            python=str(self._venv_python(venv_dir)),
            pip=str(self._venv_pip(venv_dir)),
            created_now=created_now,
        )

    def install_requirements(
        self,
        workspace: Path,
        venv_info: VenvInfo,
        notify: Optional[Callable] = None,
    ) -> bool:
        _notify = notify or (lambda *a, **kw: None)
        req = workspace / "requirements.txt"
        if not req.exists():
            return True

        _notify(
            "VenvManager: instalando dependencias en venv",
            "LOG",
            {"phase": "venv_install"},
        )
        try:
            result = subprocess.run(
                [venv_info.pip, "install", "-r", str(req), "--quiet"],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=str(workspace),
            )
            if result.returncode != 0:
                _notify(
                    f"VenvManager: pip install falló — {result.stderr.strip()[:300]}",
                    "HEALTH_WARN",
                    {"phase": "venv_install", "returncode": result.returncode},
                )
                return False
            _notify(
                "VenvManager: dependencias instaladas",
                "LOG",
                {"phase": "venv_install", "status": "ok"},
            )
            return True
        except Exception as e:
            _notify(
                f"VenvManager: error instalando dependencias — {e}",
                "HEALTH_WARN",
                {"phase": "venv_install", "error": str(e)},
            )
            return False

    # ── internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _venv_python(venv_dir: Path) -> Path:
        # Windows: Scripts\python.exe — Unix: bin/python
        win = venv_dir / "Scripts" / "python.exe"
        if win.exists():
            return win
        return venv_dir / "bin" / "python"

    @staticmethod
    def _venv_pip(venv_dir: Path) -> Path:
        win = venv_dir / "Scripts" / "pip.exe"
        if win.exists():
            return win
        return venv_dir / "bin" / "pip"

    @staticmethod
    def _fallback_info(workspace: Path) -> VenvInfo:
        return VenvInfo(
            path=workspace / ".venv",
            python=sys.executable,
            pip=f"{sys.executable} -m pip",
            created_now=False,
        )
