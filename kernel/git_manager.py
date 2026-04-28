from __future__ import annotations

import shutil
import sys
from pathlib import Path
import subprocess

from kernel.integrity.goal_integrity_validator import GoalIntegrityValidator

# Windows-specific fallback paths for git (when PATH is stripped by the launcher).
_WINDOWS_GIT_CANDIDATES = [
    r"C:\Program Files\Git\cmd\git.exe",
    r"C:\Program Files\Git\bin\git.exe",
    r"C:\Program Files (x86)\Git\cmd\git.exe",
    r"C:\Program Files (x86)\Git\bin\git.exe",
]

def _find_git() -> str:
    """Return the path to the git executable, searching common locations on Windows."""
    found = shutil.which("git")
    if found:
        return found
    if sys.platform == "win32":
        for candidate in _WINDOWS_GIT_CANDIDATES:
            if Path(candidate).exists():
                return candidate
    raise FileNotFoundError(
        "git executable not found. Install Git and ensure it is in PATH, "
        "or add its directory to the system PATH."
    )

_GIT_EXE: str | None = None

def _git_exe() -> str:
    global _GIT_EXE
    if _GIT_EXE is None:
        _GIT_EXE = _find_git()
    return _GIT_EXE


class GitManager:
    """Small non-interactive git helper for project snapshots."""

    def __init__(self, validator: GoalIntegrityValidator | None = None):
        self.validator = validator or GoalIntegrityValidator()

    _PRECOMMIT_SCRIPT = """\
#!/usr/bin/env python3
\"\"\"SODA pre-commit hook — validates goal integrity before every commit.\"\"\"
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

try:
    from kernel.integrity.goal_integrity_validator import GoalIntegrityValidator
    arch_path = Path(".") / "architecture.json"
    if arch_path.exists():
        import json
        arch = json.loads(arch_path.read_text(encoding="utf-8"))
        ok, issues = GoalIntegrityValidator().validate_workspace(Path("."))
        if not ok:
            print("SODA pre-commit: goal integrity issues found:")
            for issue in issues[:10]:
                print(f"  - {issue}")
            sys.exit(1)
except Exception as exc:
    # Non-fatal: validator unavailable — let commit proceed
    print(f"SODA pre-commit: validator skipped ({exc})")
sys.exit(0)
"""

    @staticmethod
    def _install_precommit_hook(workspace: Path) -> None:
        hooks_dir = workspace / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_path = hooks_dir / "pre-commit"
        hook_path.write_text(GitManager._PRECOMMIT_SCRIPT, encoding="utf-8")
        try:
            import stat
            hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except Exception:
            pass

    @staticmethod
    def ensure_repo(workspace: Path) -> None:
        if not (workspace / ".git").exists():
            subprocess.run([_git_exe(), "init"], cwd=str(workspace), check=True, capture_output=True)
        GitManager._install_precommit_hook(workspace)

    def commit_all(self, workspace: Path, message: str) -> None:
        self.ensure_repo(workspace)
        is_valid, issues = self.validator.validate_workspace(workspace)
        if not is_valid:
            details = ", ".join(issues[:5])
            if len(issues) > 5:
                details += ", ..."
            raise ValueError(f"Goal integrity validation failed: {details}")
        git = _git_exe()
        subprocess.run([git, "add", "."], cwd=str(workspace), check=True, capture_output=True)
        subprocess.run([git, "commit", "-m", message], cwd=str(workspace), check=True, capture_output=True)
