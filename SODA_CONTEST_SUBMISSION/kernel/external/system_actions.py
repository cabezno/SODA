from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from kernel.projects.project_manager import ProjectManager


@dataclass
class SystemActionResult:
    action: str
    target: str
    launched: bool
    message: str


class SystemActionsExecutor:
    """Executes a small, validated catalog of local system actions."""

    def __init__(self, project_manager: ProjectManager):
        self.project_manager = project_manager

    def execute(self, action: str, params: dict | None = None) -> SystemActionResult:
        payload = params or {}
        action_name = (action or "").strip().lower()

        if action_name == "open_project":
            project_id = self._require_project_id(payload)
            target = self.project_manager.project_dir(project_id)
            self._validate_existing_directory(target)
            self._launch_path(target)
            return SystemActionResult(action_name, str(target), True, "Project opened")

        if action_name == "open_source":
            project_id = self._require_project_id(payload)
            target = self.project_manager.source_dir(project_id)
            self._validate_existing_directory(target)
            self._launch_path(target)
            return SystemActionResult(action_name, str(target), True, "Source directory opened")

        if action_name == "open_file":
            project_id = self._require_project_id(payload)
            relative_path = (payload.get("relative_path") or "").strip()
            if not relative_path:
                raise ValueError("relative_path is required")
            target = self._resolve_project_file(project_id, relative_path)
            self._validate_existing_file(target)
            self._launch_path(target)
            return SystemActionResult(action_name, str(target), True, "File opened")

        raise ValueError(f"Unsupported action: {action}")

    def _require_project_id(self, params: dict) -> str:
        project_id = (params.get("project_id") or "").strip()
        if not project_id:
            raise ValueError("project_id is required")
        if not self.project_manager.exists(project_id):
            raise FileNotFoundError(f"Project not found: {project_id}")
        return project_id

    def _resolve_project_file(self, project_id: str, relative_path: str) -> Path:
        base_dir = self.project_manager.project_dir(project_id).resolve()
        candidate = (base_dir / relative_path).resolve()
        if not candidate.is_relative_to(base_dir):
            raise ValueError("relative_path escapes the project directory")
        return candidate

    @staticmethod
    def _validate_existing_directory(path: Path) -> None:
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"Directory not found: {path}")

    @staticmethod
    def _validate_existing_file(path: Path) -> None:
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

    @staticmethod
    def _launch_path(path: Path) -> None:
        target = str(path)
        if hasattr(os, "startfile"):
            os.startfile(target)
            return
        subprocess.Popen(["cmd", "/c", "start", "", target], shell=False)