from __future__ import annotations

import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


@dataclass
class WatchEvent:
    event_type: str   # "created" | "modified" | "deleted" | "moved"
    src_path: str
    dest_path: str = ""
    timestamp: float = field(default_factory=time.monotonic)


class ProjectWatchdog:
    """
    Monitors a project workspace for file changes.

    Uses the `watchdog` library if available; falls back to polling if not.
    Calls `on_change(event)` in a background thread on every detected change.
    Backs up files atomically before modifications to `.soda_backup/` inside the workspace.
    """

    BACKUP_DIR = ".soda_watchdog_backup"
    POLL_INTERVAL = 2.0   # seconds between polls in fallback mode
    IGNORED_DIRS = {".git", ".soda_watchdog_backup", "__pycache__", "node_modules", ".venv", "venv"}

    def __init__(self, workspace: Path, on_change: Optional[Callable[[WatchEvent], None]] = None):
        self.workspace = Path(workspace)
        self.on_change = on_change or (lambda e: None)
        self._observer = None
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._snapshot: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start watching the workspace in a background thread."""
        if not self.workspace.exists():
            return
        try:
            self._start_watchdog_observer()
        except ImportError:
            self._start_poll_watcher()

    def stop(self) -> None:
        """Stop watching."""
        self._stop_event.set()
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=3)
            except Exception:
                pass
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=3)

    def backup_file(self, file_path: Path) -> Optional[Path]:
        """Copy a file into the backup dir before modification. Returns backup path."""
        file_path = Path(file_path)
        if not file_path.exists() or not file_path.is_file():
            return None
        try:
            rel = file_path.relative_to(self.workspace)
        except ValueError:
            return None
        backup = self.workspace / self.BACKUP_DIR / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, backup)
        return backup

    def restore_file(self, file_path: Path) -> bool:
        """Restore a file from backup. Returns True if restored."""
        file_path = Path(file_path)
        try:
            rel = file_path.relative_to(self.workspace)
        except ValueError:
            return False
        backup = self.workspace / self.BACKUP_DIR / rel
        if not backup.exists():
            return False
        file_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, file_path)
        return True

    # ------------------------------------------------------------------
    # Internal — watchdog library observer
    # ------------------------------------------------------------------

    def _start_watchdog_observer(self) -> None:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler, FileSystemEvent

        watchdog_self = self

        class _Handler(FileSystemEventHandler):
            def on_any_event(self, event: FileSystemEvent):
                if event.is_directory:
                    return
                src = str(event.src_path)
                if any(d in src for d in watchdog_self.IGNORED_DIRS):
                    return
                dest = getattr(event, "dest_path", "") or ""
                evt = WatchEvent(
                    event_type=event.event_type,
                    src_path=src,
                    dest_path=str(dest),
                )
                watchdog_self.on_change(evt)

        self._observer = Observer()
        self._observer.schedule(_Handler(), str(self.workspace), recursive=True)
        self._observer.daemon = True
        self._observer.start()

    # ------------------------------------------------------------------
    # Internal — fallback polling
    # ------------------------------------------------------------------

    def _start_poll_watcher(self) -> None:
        self._snapshot = self._take_snapshot()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _poll_loop(self) -> None:
        while not self._stop_event.wait(self.POLL_INTERVAL):
            current = self._take_snapshot()
            old_keys = set(self._snapshot)
            new_keys = set(current)

            for p in new_keys - old_keys:
                self.on_change(WatchEvent("created", p))
            for p in old_keys - new_keys:
                self.on_change(WatchEvent("deleted", p))
            for p in old_keys & new_keys:
                if self._snapshot[p] != current[p]:
                    self.on_change(WatchEvent("modified", p))

            self._snapshot = current

    def take_tree_snapshot(self) -> dict[str, dict]:
        """
        [IMP-022] Toma una firma completa del estado actual del árbol de archivos.
        """
        snapshot = {}
        if not self.workspace.exists():
            return snapshot
            
        for p in self.workspace.rglob("*"):
            if p.is_file():
                # Ignorar carpetas de sistema
                if any(d in str(p) for d in self.IGNORED_DIRS):
                    continue
                try:
                    stat = p.stat()
                    snapshot[str(p.relative_to(self.workspace))] = {
                        "size": stat.st_size,
                        "mtime": stat.st_mtime
                    }
                except OSError:
                    pass
        return snapshot

    def verify_and_restore_tree(self, previous_snapshot: dict[str, dict]) -> list[str]:
        """
        [IMP-022] Compara el estado actual con el snapshot previo y restaura 
        archivos eliminados o drásticamente truncados.
        """
        violations = []
        current_snapshot = self.take_tree_snapshot()

        for rel_path, meta in previous_snapshot.items():
            full_path = self.workspace / rel_path

            # Caso 1: El archivo fue eliminado
            if rel_path not in current_snapshot:
                if self.restore_file(full_path):
                    violations.append(f"Restaurado archivo eliminado: {rel_path}")
                else:
                    violations.append(f"Fallo al restaurar: {rel_path}")

            # Caso 2: Reducción drástica de tamaño (Vaciado accidental)
            elif current_snapshot[rel_path]["size"] < (meta["size"] * 0.4) and meta["size"] > 100:
                if self.restore_file(full_path):
                    violations.append(f"Revertido truncado destructivo: {rel_path} ({meta['size']} -> {current_snapshot[rel_path]['size']} bytes)")

        return violations

    def _take_snapshot(self) -> dict[str, float]:
        snap: dict[str, float] = {}
        for p in self.workspace.rglob("*"):
            if p.is_file():
                parts = set(p.parts)
                if parts & self.IGNORED_DIRS:
                    continue
                try:
                    snap[str(p)] = p.stat().st_mtime
                except OSError:
                    pass
        return snap
