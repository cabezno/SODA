import os
import shutil
from pathlib import Path
import datetime

BACKUP_DIR = Path(__file__).resolve().parent / ".soda_backups"
TARGET_DIRS = ["kernel", "ui"]
TARGET_FILES = ["README.md", "soda_config.json", "pyproject.toml"]

def create_snapshot():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_dir = BACKUP_DIR / f"snapshot_{timestamp}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    
    # Backup directories
    for d in TARGET_DIRS:
        src = Path(d)
        if src.exists():
            shutil.copytree(src, snapshot_dir / d, dirs_exist_ok=True)
            print(f"Backed up directory: {d} -> {snapshot_dir / d}")
            
    # Backup files
    for f in TARGET_FILES:
        src = Path(f)
        if src.exists():
            shutil.copy2(src, snapshot_dir / f)
            print(f"Backed up file: {f} -> {snapshot_dir / f}")
            
    print(f"\n✅ Snapshot created successfully at: {snapshot_dir}")
    print(f"To restore, use: python soda_snapshot.py restore {snapshot_dir.name}")

def restore_snapshot(snapshot_name):
    snapshot_dir = BACKUP_DIR / snapshot_name
    if not snapshot_dir.exists():
        print(f"❌ Error: Snapshot {snapshot_name} not found.")
        return

    # Restore directories
    for d in TARGET_DIRS:
        src = snapshot_dir / d
        dst = Path(d)
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"Restored directory: {d}")
            
    # Restore files
    for f in TARGET_FILES:
        src = snapshot_dir / f
        dst = Path(f)
        if src.exists():
            shutil.copy2(src, dst)
            print(f"Restored file: {f}")
            
    print(f"\n✅ System restored to snapshot: {snapshot_name}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        if len(sys.argv) < 3:
            print("Usage: python soda_snapshot.py restore <snapshot_folder_name>")
        else:
            restore_snapshot(sys.argv[2])
    else:
        create_snapshot()
