from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EnvironmentReport:
    python_version: str          # e.g. "3.11.9"
    node_version: str            # e.g. "20.11.0" or ""
    required_python: str         # from .python-version / pyproject.toml or ""
    compatible: bool
    warnings: list[str] = field(default_factory=list)
    venv_exists: bool = False
    venv_path: str = ""


class EnvironmentDetector:
    """Detects Python/Node versions and checks project compatibility."""

    def detect(self, workspace: Path) -> EnvironmentReport:
        python_ver = self._python_version()
        node_ver = self._node_version()
        required = self._required_python(workspace)
        venv_path = workspace / ".venv"
        venv_exists = venv_path.exists()
        warnings: list[str] = []
        compatible = True

        if required:
            compatible = self._is_compatible(python_ver, required)
            if not compatible:
                warnings.append(
                    f"Python {python_ver} instalado, proyecto requiere {required}"
                )

        if not node_ver and self._has_node_project(workspace):
            warnings.append("Node.js no encontrado en PATH — proyecto frontend puede no iniciar")

        return EnvironmentReport(
            python_version=python_ver,
            node_version=node_ver,
            required_python=required,
            compatible=compatible,
            warnings=warnings,
            venv_exists=venv_exists,
            venv_path=str(venv_path) if venv_exists else "",
        )

    # ── version probes ────────────────────────────────────────────────────────

    @staticmethod
    def _python_version() -> str:
        v = sys.version_info
        return f"{v.major}.{v.minor}.{v.micro}"

    @staticmethod
    def _node_version() -> str:
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip().lstrip("v")
        except Exception:
            return ""

    # ── requirement detection ─────────────────────────────────────────────────

    @staticmethod
    def _required_python(workspace: Path) -> str:
        # .python-version (pyenv style)
        pv = workspace / ".python-version"
        if pv.exists():
            text = pv.read_text(encoding="utf-8").strip()
            if text:
                return text

        # pyproject.toml: requires-python = ">=3.11"
        pp = workspace / "pyproject.toml"
        if pp.exists():
            try:
                content = pp.read_text(encoding="utf-8")
                for line in content.splitlines():
                    if "requires-python" in line:
                        # extract version specifier
                        import re
                        m = re.search(r'["\']([>=<!\s\d.]+)["\']', line)
                        if m:
                            return m.group(1).strip().lstrip(">=")
            except Exception:
                pass

        return ""

    @staticmethod
    def _is_compatible(installed: str, required: str) -> bool:
        try:
            inst = tuple(int(x) for x in installed.split(".")[:2])
            req = tuple(int(x) for x in required.split(".")[:2])
            return inst >= req
        except Exception:
            return True  # can't parse → assume OK

    @staticmethod
    def _has_node_project(workspace: Path) -> bool:
        return (workspace / "package.json").exists()
