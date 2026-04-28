from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class UsageMonitor:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    tokens_input INTEGER NOT NULL,
                    tokens_output INTEGER NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    error_code TEXT,
                    metadata_json TEXT
                )
                """
            )
            conn.commit()

    def record(
        self,
        *,
        provider: str,
        model: str,
        tokens_input: int,
        tokens_output: int,
        latency_ms: int,
        cost_usd: float,
        error_code: Optional[str],
        metadata: dict,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_usage (
                    timestamp, provider, model, tokens_input, tokens_output,
                    latency_ms, cost_usd, error_code, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    provider,
                    model,
                    int(tokens_input),
                    int(tokens_output),
                    int(latency_ms),
                    float(cost_usd),
                    error_code,
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )
            conn.commit()

    def summary(self) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*),
                    COALESCE(SUM(tokens_input), 0),
                    COALESCE(SUM(tokens_output), 0),
                    COALESCE(SUM(cost_usd), 0.0),
                    COALESCE(AVG(latency_ms), 0)
                FROM ai_usage
                """
            ).fetchone()
        return {
            "total_calls": row[0],
            "tokens_input": row[1],
            "tokens_output": row[2],
            "cost_usd": row[3],
            "avg_latency_ms": int(row[4]),
        }

    def grouped_summary(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    provider,
                    model,
                    COUNT(*) AS total_calls,
                    COALESCE(SUM(tokens_input), 0) AS tokens_input,
                    COALESCE(SUM(tokens_output), 0) AS tokens_output,
                    COALESCE(SUM(cost_usd), 0.0) AS cost_usd,
                    COALESCE(AVG(latency_ms), 0) AS avg_latency_ms,
                    COALESCE(SUM(CASE WHEN error_code IS NOT NULL THEN 1 ELSE 0 END), 0) AS error_calls
                FROM ai_usage
                GROUP BY provider, model
                ORDER BY cost_usd DESC, total_calls DESC
                """
            ).fetchall()

        return [
            {
                "provider": r[0],
                "model": r[1],
                "total_calls": r[2],
                "tokens_input": r[3],
                "tokens_output": r[4],
                "cost_usd": r[5],
                "avg_latency_ms": int(r[6]),
                "error_calls": r[7],
            }
            for r in rows
        ]

    def recent_calls(self, limit: int = 25) -> list[dict]:
        lim = max(1, min(int(limit), 200))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    timestamp,
                    provider,
                    model,
                    tokens_input,
                    tokens_output,
                    latency_ms,
                    cost_usd,
                    error_code,
                    metadata_json
                FROM ai_usage
                ORDER BY id DESC
                LIMIT ?
                """,
                (lim,),
            ).fetchall()

        out = []
        for r in rows:
            try:
                meta = json.loads(r[8]) if r[8] else {}
            except Exception:
                meta = {}
            out.append(
                {
                    "timestamp": r[0],
                    "provider": r[1],
                    "model": r[2],
                    "tokens_input": r[3],
                    "tokens_output": r[4],
                    "latency_ms": r[5],
                    "cost_usd": r[6],
                    "error_code": r[7],
                    "metadata": meta,
                }
            )
        return out
