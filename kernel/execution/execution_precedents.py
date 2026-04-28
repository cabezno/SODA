"""
Persistent store of execution configs that worked for a project/stack.
Keyed by stack type (python, node, dotnet, go, rust, static).
Used by AutoFixer to seed its first attempt and by future projects with same stack.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "execution_precedents.db"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH))
    c.execute("""
        CREATE TABLE IF NOT EXISTS precedents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ts              TEXT    NOT NULL,
            project_id      TEXT    NOT NULL,
            stack           TEXT    NOT NULL,
            run_command     TEXT    NOT NULL,
            install_command TEXT    NOT NULL DEFAULT '',
            working_dir     TEXT    NOT NULL DEFAULT '',
            notes           TEXT    NOT NULL DEFAULT '',
            success_count   INTEGER NOT NULL DEFAULT 1
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_stack ON precedents(stack)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_pid   ON precedents(project_id)")
    c.commit()
    return c


class ExecutionPrecedents:
    """Thread-safe SQLite store for successful execution configurations."""

    @staticmethod
    def record(
        project_id: str,
        stack: str,
        run_command: str,
        install_command: str = "",
        working_dir: str = "",
        notes: str = "",
    ) -> None:
        try:
            c = _conn()
            existing = c.execute(
                "SELECT id, success_count FROM precedents WHERE project_id=? AND stack=?",
                (project_id, stack),
            ).fetchone()
            if existing:
                c.execute(
                    "UPDATE precedents SET run_command=?, install_command=?, working_dir=?, "
                    "notes=?, success_count=?, ts=? WHERE id=?",
                    (run_command, install_command, working_dir, notes,
                     existing[1] + 1, datetime.utcnow().isoformat(), existing[0]),
                )
            else:
                c.execute(
                    "INSERT INTO precedents (ts,project_id,stack,run_command,install_command,working_dir,notes) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (datetime.utcnow().isoformat(), project_id, stack,
                     run_command, install_command, working_dir, notes),
                )
            c.commit()
            c.close()
        except Exception:
            pass

    @staticmethod
    def get_for_stack(stack: str, limit: int = 5) -> list[dict]:
        try:
            c = _conn()
            rows = c.execute(
                "SELECT project_id,run_command,install_command,working_dir,notes,success_count,ts "
                "FROM precedents WHERE stack=? ORDER BY success_count DESC, id DESC LIMIT ?",
                (stack, limit),
            ).fetchall()
            c.close()
            return [
                {
                    "project_id": r[0], "run_command": r[1], "install_command": r[2],
                    "working_dir": r[3], "notes": r[4], "success_count": r[5], "ts": r[6],
                }
                for r in rows
            ]
        except Exception:
            return []

    @staticmethod
    def get_for_project(project_id: str) -> Optional[dict]:
        try:
            c = _conn()
            row = c.execute(
                "SELECT stack,run_command,install_command,working_dir,notes FROM precedents "
                "WHERE project_id=? ORDER BY id DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            c.close()
            if row:
                return {
                    "stack": row[0], "run_command": row[1], "install_command": row[2],
                    "working_dir": row[3], "notes": row[4],
                }
        except Exception:
            pass
        return None

    @staticmethod
    def summary_for_ai(stack: str, max_entries: int = 3) -> str:
        """Compact text for injection into AI prompts about how to run this stack."""
        entries = ExecutionPrecedents.get_for_stack(stack, limit=max_entries)
        if not entries:
            return ""
        lines = [f"PRECEDENTES DE EJECUCIÓN para stack '{stack}':"]
        for e in entries:
            lines.append(
                f"  [{e['project_id']}] run='{e['run_command']}' "
                f"install='{e['install_command']}' — {e['notes'][:100]}"
            )
        return "\n".join(lines)
