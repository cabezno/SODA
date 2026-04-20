import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class ProjectLineage:
    """Append-only log of every project run, branch, and refoundation."""

    def __init__(self, base_dir: Path):
        self._path = base_dir / "projects" / "lineage.json"
        self._entries: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._entries, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def record_start(self, project_id: str, description: str, parent_id: Optional[str] = None, branch_name: Optional[str] = None):
        entry = {
            "project_id": project_id,
            "description": description[:120],
            "parent_id": parent_id,
            "branch_name": branch_name,
            "state": "running",
            "skills": [],
            "profile": "",
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
        }
        self._entries.append(entry)
        self._save()

    def record_capabilities(self, project_id: str, skills: list[str], profile: str):
        entry = self._get(project_id)
        if entry:
            entry["skills"] = skills
            entry["profile"] = profile
            self._save()

    def record_complete(self, project_id: str, state: str = "done"):
        entry = self._get(project_id)
        if entry:
            entry["state"] = state
            entry["completed_at"] = datetime.now().isoformat()
            self._save()

    def record_branch(self, parent_id: str, branch_id: str, branch_name: str, description: str):
        self.record_start(branch_id, description, parent_id=parent_id, branch_name=branch_name)

    def get_history(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._entries[-limit:]))

    def get_project(self, project_id: str) -> Optional[dict]:
        return self._get(project_id)

    def get_branches(self, parent_id: str) -> list[dict]:
        return [e for e in self._entries if e.get("parent_id") == parent_id]

    def _get(self, project_id: str) -> Optional[dict]:
        for e in reversed(self._entries):
            if e["project_id"] == project_id:
                return e
        return None
