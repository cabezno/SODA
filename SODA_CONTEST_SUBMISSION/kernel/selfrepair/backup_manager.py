"""BackupManager — full system snapshot before any self-repair change."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


_IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.pyo",
    ".soda_venv", "backup", ".git",
    "node_modules", "*.egg-info", "dist", "build",
    "debug", "*.log",
)


class BackupManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.backup_root = base_dir / "backup"

    def create(self, label: str = "") -> Path:
        """Copy entire project to backup/YYYYMMDD_HHMMSS[_label]/. Returns dest path."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"{ts}_{label}" if label else ts
        dest = self.backup_root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(self.base_dir), str(dest), ignore=_IGNORE)
        print(f"  [Backup] Snapshot guardado en backup/{name}")
        return dest

    def list_backups(self) -> list[dict]:
        if not self.backup_root.exists():
            return []
        entries = []
        for d in sorted(self.backup_root.iterdir()):
            if d.is_dir():
                size_mb = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / 1_048_576
                entries.append({"name": d.name, "path": str(d), "size_mb": round(size_mb, 1)})
        return entries

    def restore(self, backup_name: str) -> bool:
        """Overwrite base_dir with backup (except backup/ folder itself)."""
        src = self.backup_root / backup_name
        if not src.exists():
            return False
        for item in src.iterdir():
            dest = self.base_dir / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(str(item), str(dest))
            else:
                shutil.copy2(str(item), str(dest))
        print(f"  [Backup] Restaurado desde backup/{backup_name}")
        return True
