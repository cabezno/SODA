"""
Persistent log of execution and launch errors.
Stores errors in SQLite so the orchestrator can learn from repeated failures.
"""
from __future__ import annotations

import json
import sqlite3
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional


_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "execution_errors.db"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH))
    c.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL,
            project_id  TEXT    NOT NULL,
            phase       TEXT    NOT NULL,
            error_type  TEXT    NOT NULL,
            message     TEXT    NOT NULL,
            context     TEXT    NOT NULL DEFAULT '{}',
            resolved    INTEGER NOT NULL DEFAULT 0
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_pid ON errors(project_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ts  ON errors(ts)")
    c.commit()
    return c


class ExecutionErrorLog:
    """Thread-safe SQLite log for execution errors."""

    # ── write ────────────────────────────────────────────────────────────────

    @staticmethod
    def record(
        project_id: str,
        phase: str,
        message: str,
        error_type: str = "runtime",
        context: Optional[dict] = None,
    ) -> None:
        try:
            c = _conn()
            c.execute(
                "INSERT INTO errors (ts, project_id, phase, error_type, message, context) VALUES (?,?,?,?,?,?)",
                (
                    datetime.utcnow().isoformat(),
                    project_id,
                    phase,
                    error_type,
                    message[:2000],
                    json.dumps(context or {}, ensure_ascii=False),
                ),
            )
            c.commit()
            c.close()
        except Exception:
            pass  # logging must never crash the caller

    @staticmethod
    def record_exception(
        project_id: str,
        phase: str,
        exc: Exception,
        context: Optional[dict] = None,
    ) -> None:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        ExecutionErrorLog.record(
            project_id=project_id,
            phase=phase,
            message=f"{type(exc).__name__}: {exc}\n{tb}",
            error_type=type(exc).__name__,
            context=context,
        )

    @staticmethod
    def mark_resolved(project_id: str) -> None:
        try:
            c = _conn()
            c.execute("UPDATE errors SET resolved=1 WHERE project_id=? AND resolved=0", (project_id,))
            c.commit()
            c.close()
        except Exception:
            pass

    # ── read ─────────────────────────────────────────────────────────────────

    @staticmethod
    def get_project_errors(project_id: str, limit: int = 50) -> list[dict]:
        try:
            c = _conn()
            rows = c.execute(
                "SELECT ts,phase,error_type,message,context,resolved FROM errors "
                "WHERE project_id=? ORDER BY id DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
            c.close()
            return [
                {
                    "ts": r[0], "phase": r[1], "error_type": r[2],
                    "message": r[3], "context": json.loads(r[4]), "resolved": bool(r[5]),
                }
                for r in rows
            ]
        except Exception:
            return []

    @staticmethod
    def get_recent_errors(limit: int = 20, unresolved_only: bool = False) -> list[dict]:
        try:
            c = _conn()
            where = "WHERE resolved=0" if unresolved_only else ""
            rows = c.execute(
                f"SELECT ts,project_id,phase,error_type,message,context FROM errors "
                f"{where} ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            c.close()
            return [
                {
                    "ts": r[0], "project_id": r[1], "phase": r[2],
                    "error_type": r[3], "message": r[4], "context": json.loads(r[5]),
                }
                for r in rows
            ]
        except Exception:
            return []

    @staticmethod
    def error_summary_for_ai(project_id: str, max_errors: int = 5) -> str:
        """Return a compact text summary of recent errors for injection into AI prompts."""
        errors = ExecutionErrorLog.get_project_errors(project_id, limit=max_errors)
        if not errors:
            return ""
        lines = [f"ERRORES DE EJECUCIÓN PREVIOS en '{project_id}':"]
        for e in errors:
            lines.append(f"  [{e['phase']}] {e['error_type']}: {e['message'][:300]}")
        return "\n".join(lines)
