"""
ContractRepository — Semana 3 del plan de evolución SODA.

Abstracción de persistencia para SodaContract y el árbol de contratos
completo. Desacopla el motor recursivo del sistema de archivos y habilita:
  - Reanudación de proyectos parcialmente completados
  - Migración a SQLite sin tocar el engine
  - Consulta del estado del árbol desde la UI / Telegram
"""
from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional


# ── Interface (storage-agnostic) ──────────────────────────────────────────────

class IContractRepository(ABC):
    """
    Contrato de persistencia para SodaContracts.
    Las implementaciones concretas (JSON, SQLite) no deben filtrarse
    al engine — solo esta interfaz es visible desde fuera del módulo.
    """

    @abstractmethod
    def save(self, contract: object) -> None:
        """Persiste o actualiza un contrato individual."""

    @abstractmethod
    def load(self, contract_id: str) -> Optional[object]:
        """Carga un contrato por su ID. Retorna None si no existe."""

    @abstractmethod
    def save_tree(self, project_id: str, pool: Dict[str, object]) -> None:
        """Persiste el árbol completo de un proyecto."""

    @abstractmethod
    def load_tree(self, project_id: str) -> Dict[str, object]:
        """
        Carga el árbol completo de contratos de un proyecto.
        Retorna dict vacío si el proyecto no existe o está vacío.
        """

    @abstractmethod
    def list_projects(self) -> List[str]:
        """Lista todos los project_id con datos persistidos."""

    @abstractmethod
    def delete_project(self, project_id: str) -> None:
        """Elimina todos los contratos de un proyecto."""


# ── JSON implementation (mantiene compatibilidad con el estado actual) ────────

class JsonContractRepository(IContractRepository):
    """
    Implementación basada en archivos JSON por proyecto.
    Reemplaza la escritura directa en recursive_engine.py conservando
    el mismo formato en disco.

    Estructura en disco:
        workspace/
          soda_v2_tree.json          ← árbol completo (compatible con el formato actual)
          contracts/
            {contract_id}.json       ← contratos individuales (nuevo)
    """

    def __init__(self, workspace: Path) -> None:
        self._root = Path(workspace)
        self._contracts_dir = self._root / "contracts"
        self._contracts_dir.mkdir(parents=True, exist_ok=True)

    # ── IContractRepository ───────────────────────────────────────────────

    def save(self, contract: object) -> None:
        cid = getattr(contract, "contract_id", None)
        if not cid:
            raise ValueError("Contract must have a contract_id attribute")
        path = self._contracts_dir / f"{self._safe(cid)}.json"
        path.write_text(
            json.dumps(contract.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def load(self, contract_id: str) -> Optional[object]:
        path = self._contracts_dir / f"{self._safe(contract_id)}.json"
        if not path.exists():
            return None
        from kernel.core.models_v2 import SodaContract
        return SodaContract(**json.loads(path.read_text(encoding="utf-8")))

    def save_tree(self, project_id: str, pool: Dict[str, object]) -> None:
        tree_path = self._root / "soda_v2_tree.json"
        dump = {cid: c.model_dump() for cid, c in pool.items()}
        tree_path.write_text(
            json.dumps(dump, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        # Also persist each contract individually for point lookups
        for contract in pool.values():
            try:
                self.save(contract)
            except Exception:
                pass

    def load_tree(self, project_id: str) -> Dict[str, object]:
        tree_path = self._root / "soda_v2_tree.json"
        if not tree_path.exists():
            return {}
        from kernel.core.models_v2 import SodaContract
        raw = json.loads(tree_path.read_text(encoding="utf-8"))
        result = {}
        for cid, data in raw.items():
            try:
                result[cid] = SodaContract(**data)
            except Exception:
                pass
        return result

    def list_projects(self) -> List[str]:
        # For the JSON repo a "project" == a workspace directory.
        # Return the workspace name as the single project.
        return [self._root.name] if (self._root / "soda_v2_tree.json").exists() else []

    def delete_project(self, project_id: str) -> None:
        tree_path = self._root / "soda_v2_tree.json"
        if tree_path.exists():
            tree_path.unlink()
        for f in self._contracts_dir.glob("*.json"):
            f.unlink()

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _safe(name: str) -> str:
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


# ── SQLite implementation (optional — zero extra deps) ────────────────────────

class SqliteContractRepository(IContractRepository):
    """
    Implementación SQLite — habilita consultas, reanudación y la UI de estado.
    Sin dependencias externas (usa la stdlib sqlite3).

    Schema:
        projects(project_id TEXT PK, created_at TEXT, updated_at TEXT)
        contracts(contract_id TEXT, project_id TEXT, status TEXT, data TEXT (JSON), updated_at TEXT)
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self) -> None:
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id  TEXT PRIMARY KEY,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS contracts (
                    contract_id TEXT NOT NULL,
                    project_id  TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'pending',
                    data        TEXT NOT NULL,
                    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (contract_id, project_id),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );
                CREATE INDEX IF NOT EXISTS idx_contracts_project
                    ON contracts(project_id);
            """)

    # ── IContractRepository ───────────────────────────────────────────────

    def save(self, contract: object) -> None:
        cid = getattr(contract, "contract_id", None)
        status = getattr(getattr(contract, "status", None), "value", str(getattr(contract, "status", "pending")))
        project_id = getattr(contract, "parent_id", None) or "default"
        data = contract.model_dump_json()
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO projects(project_id) VALUES(?)", (project_id,)
            )
            c.execute(
                """INSERT INTO contracts(contract_id, project_id, status, data, updated_at)
                   VALUES(?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(contract_id, project_id) DO UPDATE SET
                     status=excluded.status,
                     data=excluded.data,
                     updated_at=excluded.updated_at""",
                (cid, project_id, status, data)
            )

    def load(self, contract_id: str) -> Optional[object]:
        with self._conn() as c:
            row = c.execute(
                "SELECT data FROM contracts WHERE contract_id=? ORDER BY updated_at DESC LIMIT 1",
                (contract_id,)
            ).fetchone()
        if not row:
            return None
        from kernel.core.models_v2 import SodaContract
        return SodaContract.model_validate_json(row["data"])

    def save_tree(self, project_id: str, pool: Dict[str, object]) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO projects(project_id) VALUES(?)", (project_id,)
            )
            c.execute(
                "UPDATE projects SET updated_at=datetime('now') WHERE project_id=?", (project_id,)
            )
            for cid, contract in pool.items():
                status = getattr(getattr(contract, "status", None), "value",
                                 str(getattr(contract, "status", "pending")))
                data = contract.model_dump_json()
                c.execute(
                    """INSERT INTO contracts(contract_id, project_id, status, data, updated_at)
                       VALUES(?, ?, ?, ?, datetime('now'))
                       ON CONFLICT(contract_id, project_id) DO UPDATE SET
                         status=excluded.status,
                         data=excluded.data,
                         updated_at=excluded.updated_at""",
                    (cid, project_id, status, data)
                )

    def load_tree(self, project_id: str) -> Dict[str, object]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT contract_id, data FROM contracts WHERE project_id=?",
                (project_id,)
            ).fetchall()
        if not rows:
            return {}
        from kernel.core.models_v2 import SodaContract
        result = {}
        for row in rows:
            try:
                result[row["contract_id"]] = SodaContract.model_validate_json(row["data"])
            except Exception:
                pass
        return result

    def list_projects(self) -> List[str]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT project_id FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        return [r["project_id"] for r in rows]

    def delete_project(self, project_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM contracts WHERE project_id=?", (project_id,))
            c.execute("DELETE FROM projects WHERE project_id=?", (project_id,))

    # ── Extra queries (UI / Telegram) ─────────────────────────────────────

    def pending_contracts(self, project_id: str) -> List[str]:
        """Contract IDs not yet completed — used for resumption."""
        with self._conn() as c:
            rows = c.execute(
                """SELECT contract_id FROM contracts
                   WHERE project_id=? AND UPPER(status) NOT IN ('COMPLETED', 'DECOMPOSED')
                   ORDER BY updated_at""",
                (project_id,)
            ).fetchall()
        return [r["contract_id"] for r in rows]

    def project_summary(self, project_id: str) -> dict:
        """Quick stats for the UI status panel."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT status, COUNT(*) as n FROM contracts WHERE project_id=? GROUP BY status",
                (project_id,)
            ).fetchall()
        return {r["status"]: r["n"] for r in rows}


# ── Factory ───────────────────────────────────────────────────────────────────

def make_contract_repository(
    workspace: Path,
    backend: str = "json",
) -> IContractRepository:
    """
    Factory — selecciona la implementación correcta.
    backend: "json" | "sqlite"
    """
    if backend == "sqlite":
        return SqliteContractRepository(workspace / "soda_contracts.db")
    return JsonContractRepository(workspace)
