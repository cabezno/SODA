import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

class CorrelationIndex:
    """
    Gestiona el índice de correlación alfanumérica entre UI y Backend.
    Actúa como el 'Data Dictionary' central del proyecto SODA V3.
    """
    def __init__(self, workspace_path: Path):
        self.db_path = workspace_path / "correlation_index.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS symbol_index (
                    code_id TEXT PRIMARY KEY,
                    concept TEXT NOT NULL,
                    frontend_ref TEXT,
                    backend_ref TEXT,
                    data_type TEXT,
                    status TEXT DEFAULT 'PENDING',
                    metadata TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON symbol_index(status)")

    def register_symbol(self, code_id: str, concept: str, data_type: str = "Any", metadata: dict = None):
        """Registra un nuevo símbolo alfanumérico en el índice."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO symbol_index (code_id, concept, data_type, metadata) VALUES (?, ?, ?, ?)",
                (code_id, concept, data_type, json.dumps(metadata or {}))
            )

    def update_ref(self, code_id: str, frontend_ref: str = None, backend_ref: str = None, status: str = None):
        """Actualiza las referencias de implementación para un símbolo."""
        with sqlite3.connect(self.db_path) as conn:
            if frontend_ref:
                conn.execute("UPDATE symbol_index SET frontend_ref = ?, updated_at = CURRENT_TIMESTAMP WHERE code_id = ?", (frontend_ref, code_id))
            if backend_ref:
                conn.execute("UPDATE symbol_index SET backend_ref = ?, updated_at = CURRENT_TIMESTAMP WHERE code_id = ?", (backend_ref, code_id))
            if status:
                conn.execute("UPDATE symbol_index SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE code_id = ?", (status, code_id))

    def get_all(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM symbol_index")
            return [dict(row) for row in cursor.fetchall()]

    def get_pending_sync(self) -> List[Dict[str, Any]]:
        """Retorna símbolos que existen en un lado pero no en el otro."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            # Símbolos que tienen front pero no back, o viceversa (y no están marcados como SYNCED)
            cursor = conn.execute("""
                SELECT * FROM symbol_index 
                WHERE (frontend_ref IS NOT NULL AND backend_ref IS NULL)
                   OR (frontend_ref IS NULL AND backend_ref IS NOT NULL)
            """)
            return [dict(row) for row in cursor.fetchall()]

    def mark_synced(self, code_id: str):
        self.update_ref(code_id, status='SYNCED')
