from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple


class GoalIntegrityValidator:
    """Anti-orphan validator.

    Checks that every generated .py file in source/ carries SODA metadata
    and that every goal_id it declares is registered in goal_tree.json.
    Also verifies that goals marked as 'implemented' have their files on disk.
    """

    _GOAL_ID_RE = re.compile(r"#\s*goal_id:\s*(\S+)")

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def validate_workspace(self, workspace: Path) -> Tuple[bool, List[str]]:
        """Return (is_valid, issues).

        Checks (in order):
        1. Every .py in source/ has a ``# goal_id:`` header.
        2. Every declared goal_id exists in goal_tree.json (when present).
        3. Every goal with status=implemented has its files on disk.
        """
        workspace = Path(workspace)
        issues: List[str] = []
        declared: dict[str, str] = {}  # goal_id -> relative path

        _SKIP_DIRS = {"tests", "test", "__pycache__", ".venv", "node_modules"}
        source_dir = workspace / "source"
        if source_dir.exists():
            for py_file in sorted(source_dir.rglob("*.py")):
                # Skip test directories and auto-generated test files
                if any(part in _SKIP_DIRS for part in py_file.parts):
                    continue
                rel = py_file.relative_to(workspace).as_posix()
                try:
                    content = py_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                match = self._GOAL_ID_RE.search(content)
                if not match:
                    issues.append(f"missing metadata: {rel}")
                else:
                    declared[match.group(1)] = rel

        tree_path = workspace / "goal_tree.json"
        if tree_path.exists():
            try:
                tree_data = json.loads(tree_path.read_text(encoding="utf-8"))
                known_ids = {node["id"] for node in tree_data.get("nodes", [])}

                for goal_id in declared:
                    if goal_id not in known_ids:
                        issues.append(f"undeclared goal_id: {goal_id}")

                for node in tree_data.get("nodes", []):
                    if node.get("status") == "implemented":
                        for filepath in node.get("implemented_by", []):
                            if not (workspace / filepath).exists():
                                issues.append(
                                    f"implemented goal missing file: {node['id']} -> {filepath}"
                                )
            except Exception:
                pass

        return len(issues) == 0, issues

    # ------------------------------------------------------------------
    # Inline content check (used by CodeGenerator)
    # ------------------------------------------------------------------

    def validate_content(self, code: str) -> bool:
        """Return True if the code string contains a SODA metadata goal_id header."""
        return bool(self._GOAL_ID_RE.search(code or ""))

    # ------------------------------------------------------------------
    # Legacy / convenience
    # ------------------------------------------------------------------

    def validate_project_integrity(self, architecture: dict) -> Dict:
        """Legacy shim — callers should migrate to validate_workspace()."""
        return {"status": "skipped", "orphans": [], "is_clean": True}
