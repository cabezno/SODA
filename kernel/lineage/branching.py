import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


STRUCTURAL_TYPES = {"structural", "scope", "new_module"}


class BranchManager:
    def __init__(self, projects_dir: Path):
        self.projects_dir = projects_dir

    def should_branch(self, change_type: str, requires_regeneration: bool) -> bool:
        return change_type in STRUCTURAL_TYPES and requires_regeneration

    def create_branch(self, parent_id: str, branch_name: str) -> tuple[str, Path]:
        """Copy parent source into a new branch workspace. Returns (branch_id, branch_dir)."""
        branch_id = f"{parent_id}_branch_{branch_name}_{datetime.now().strftime('%H%M%S')}"
        parent_dir = self.projects_dir / parent_id
        branch_dir = self.projects_dir / branch_id
        branch_dir.mkdir(parents=True, exist_ok=True)

        # Copy source files
        parent_source = parent_dir / "source"
        if parent_source.exists():
            shutil.copytree(parent_source, branch_dir / "source")

        # Copy metadata and adjust
        meta_path = parent_dir / "metadata.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["id"] = branch_id
            meta["parent_id"] = parent_id
            meta["branch_name"] = branch_name
            meta["state"] = "branch"
            meta["created_at"] = datetime.now().isoformat()
            (branch_dir / "metadata.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
            )

        # Copy architecture and blueprint
        for fname in ("blueprint.json", "architecture.json", "execution_plan.json"):
            src = parent_dir / fname
            if src.exists():
                shutil.copy2(src, branch_dir / fname)

        return branch_id, branch_dir

    def list_branches(self, parent_id: str) -> list[dict]:
        branches = []
        for d in self.projects_dir.iterdir():
            if not d.is_dir():
                continue
            meta_path = d / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if meta.get("parent_id") == parent_id:
                    branches.append({
                        "branch_id": meta["id"],
                        "branch_name": meta.get("branch_name", ""),
                        "state": meta.get("state", ""),
                        "created_at": meta.get("created_at", ""),
                    })
            except Exception:
                pass
        return sorted(branches, key=lambda b: b["created_at"])

    def promote_branch(self, parent_id: str, branch_id: str):
        """Copy branch source back to parent, overwriting it."""
        branch_source = self.projects_dir / branch_id / "source"
        parent_source = self.projects_dir / parent_id / "source"
        if branch_source.exists():
            if parent_source.exists():
                shutil.rmtree(parent_source)
            shutil.copytree(branch_source, parent_source)

        # Update parent metadata state
        meta_path = self.projects_dir / parent_id / "metadata.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["state"] = "done"
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
