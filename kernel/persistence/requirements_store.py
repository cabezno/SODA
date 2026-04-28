"""
Persistent storage of exact user requirements for a SODA project.

Solves hallucination: every AI call throughout the pipeline receives
the original user intent as a hard constraint block.

Saved as USER_REQUIREMENTS.md in the project workspace so it survives
process restarts and can be inspected / edited manually.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


_FILENAME = "USER_REQUIREMENTS.md"


class RequirementsStore:
    """Read/write user requirements for one project workspace."""

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self._path = self.workspace / _FILENAME

    # ── write ─────────────────────────────────────────────────────────────────

    def save(
        self,
        description: str,
        project_name: str = "",
        skills: Optional[list] = None,
        stack_hint: str = "",
        extra_notes: str = "",
    ) -> None:
        """Persist user requirements to disk (idempotent — only writes once)."""
        if self._path.exists():
            return  # never overwrite the original requirements

        self.workspace.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# Requisitos del Usuario — {project_name or 'proyecto'}",
            f"_Guardado: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_",
            "",
            "## Descripción original (NO modificar)",
            "",
            description.strip(),
            "",
        ]
        if stack_hint:
            lines += ["## Stack solicitado", "", stack_hint, ""]
        if skills:
            lines += ["## Skills seleccionadas", "", "- " + "\n- ".join(str(s) for s in skills), ""]
        if extra_notes:
            lines += ["## Notas adicionales", "", extra_notes, ""]

        self._path.write_text("\n".join(lines), encoding="utf-8")

    def update_notes(self, notes: str) -> None:
        """Append clarifications or iteration notes (preserves original)."""
        if not self._path.exists():
            return
        current = self._path.read_text(encoding="utf-8")
        addition = f"\n## Clarificación ({datetime.utcnow().strftime('%H:%M UTC')})\n\n{notes}\n"
        self._path.write_text(current + addition, encoding="utf-8")

    # ── read ──────────────────────────────────────────────────────────────────

    def load(self) -> str:
        """Return full requirements text, or empty string if not yet saved."""
        if not self._path.exists():
            return ""
        return self._path.read_text(encoding="utf-8", errors="replace")

    def get_description(self) -> str:
        """Extract just the original description block."""
        text = self.load()
        m = re.search(r"## Descripción original.*?\n\n(.+?)(?:\n##|\Z)", text, re.DOTALL)
        return m.group(1).strip() if m else text.strip()

    def as_constraint_block(self) -> str:
        """
        Return a formatted block to prepend to any AI prompt.
        The block is short enough to fit comfortably in context but
        authoritative enough that models follow it.
        """
        desc = self.get_description()
        if not desc:
            return ""
        return (
            "╔══════════════════════════════════════════════════════╗\n"
            "║  REQUISITOS EXACTOS DEL USUARIO — SEGUIR AL PIE     ║\n"
            "║  DE LA LETRA. NO AGREGAR NI OMITIR FUNCIONALIDADES  ║\n"
            "╚══════════════════════════════════════════════════════╝\n"
            f"{desc}\n"
            "══════════════════════════════════════════════════════\n"
        )

    def as_task_field(self) -> str:
        """Short version for injection into task JSON fields."""
        desc = self.get_description()
        return desc[:800] if desc else ""

    @staticmethod
    def from_project(workspace: Path) -> "RequirementsStore":
        return RequirementsStore(workspace)
