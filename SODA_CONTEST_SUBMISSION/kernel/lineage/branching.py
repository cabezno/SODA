import shutil
import json
import asyncio
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

    # ------------------------------------------------------------------
    # Comparative branching
    # ------------------------------------------------------------------

    async def run_both_and_compare(
        self,
        parent_id: str,
        branch_id: str,
        run_command: str,
        install_command: str = "",
        notify_fn=None,
    ) -> dict:
        """
        Run both parent and branch versions, compare smoke results, and return
        a comparison report so the user can choose which to adopt.
        """
        from kernel.execution.project_runner import ProjectRunner
        from kernel.execution.smoke_tester import SmokeTester

        _notify = notify_fn or (lambda msg, t, d: None)
        runner = ProjectRunner()
        tester = SmokeTester()

        async def _setup_version(project_id: str, label: str) -> dict:
            workspace = self.projects_dir / project_id
            _notify(f"Arrancando versión {label}…", "LOG", {"branch": label, "project_id": project_id})
            result = await runner.setup_and_verify(
                project_workspace=workspace,
                run_command=run_command,
                install_command=install_command,
                notify_fn=_notify,
            )
            smoke = result.get("smoke", {})
            base_url = smoke.get("target_url", "")
            suite_result = None
            if base_url and smoke.get("passed"):
                meta_path = workspace / "metadata.json"
                arch = {}
                if meta_path.exists():
                    try:
                        arch = json.loads(meta_path.read_text(encoding="utf-8")).get("architecture", {})
                    except Exception:
                        pass
                source_dir = workspace / "source"
                suite = await tester.run_suite_async(base_url, arch, source_dir if source_dir.exists() else None)
                suite_result = suite.to_dict()
            return {
                "project_id": project_id,
                "label": label,
                "setup": result,
                "smoke_suite": suite_result,
                "score": suite_result["passed"] if suite_result else (1 if smoke.get("passed") else 0),
            }

        # Run both in parallel
        raw_parent, raw_branch = await asyncio.gather(
            _setup_version(parent_id, "main"),
            _setup_version(branch_id, "branch"),
            return_exceptions=True,
        )

        _error_result = lambda label: {
            "project_id": parent_id if label == "main" else branch_id,
            "label": label, "setup": {}, "smoke_suite": None, "score": 0,
            "error": True,
        }
        parent_result = _error_result("main") if isinstance(raw_parent, Exception) else raw_parent
        branch_result = _error_result("branch") if isinstance(raw_branch, Exception) else raw_branch
        if isinstance(raw_parent, Exception):
            _notify(f"Error arrancando versión main: {raw_parent}", "HEALTH_WARN", {})
        if isinstance(raw_branch, Exception):
            _notify(f"Error arrancando versión branch: {raw_branch}", "HEALTH_WARN", {})

        recommendation = "branch" if branch_result["score"] >= parent_result["score"] else "main"
        comparison = {
            "main": parent_result,
            "branch": branch_result,
            "recommendation": recommendation,
            "scores": {"main": parent_result["score"], "branch": branch_result["score"]},
        }
        _notify(
            f"Comparación completa — recomendación: {recommendation} "
            f"(main={parent_result['score']}, branch={branch_result['score']})",
            "LOG",
            comparison,
        )
        return comparison
