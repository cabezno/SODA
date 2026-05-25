"""
Tests for ContractRepository — JSON and SQLite backends.
Verifica: save, load, save_tree, load_tree, list_projects, delete_project,
          reanudación (pending_contracts), factory.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Stub heavy optional deps
for _mod in ("docker", "anthropic", "google.generativeai", "ollama",
             "telegram", "telegram.ext", "pywebview", "chromadb",
             "watchdog", "watchdog.observers", "watchdog.events",
             "github", "git"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from kernel.storage.contract_repository import (
    JsonContractRepository,
    SqliteContractRepository,
    make_contract_repository,
    IContractRepository,
)
from kernel.core.models_v2 import (
    SodaContract, ContractStatus, ContractInterface, DynamicPersona
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_contract(contract_id: str, title: str = "Test", status=ContractStatus.PENDING_DECOMPOSITION) -> SodaContract:
    return SodaContract(
        contract_id=contract_id,
        title=title,
        description="A test contract",
        is_atomic=True,
        level=0,
        status=status,
        interface=ContractInterface(inputs_required=[], outputs_provided=[]),
        dynamic_persona=DynamicPersona(target_role="coder", required_skills=[]),
    )


# ═══════════════════════════════════════════════════════════════════════════
# JsonContractRepository
# ═══════════════════════════════════════════════════════════════════════════

class TestJsonContractRepository:

    def _repo(self, tmp_path) -> JsonContractRepository:
        return JsonContractRepository(tmp_path)

    # ── save / load ───────────────────────────────────────────────────────

    def test_save_and_load_roundtrip(self, tmp_path):
        repo = self._repo(tmp_path)
        c = _make_contract("auth_svc")
        repo.save(c)
        loaded = repo.load("auth_svc")
        assert loaded is not None
        assert loaded.contract_id == "auth_svc"
        assert loaded.title == "Test"

    def test_load_nonexistent_returns_none(self, tmp_path):
        repo = self._repo(tmp_path)
        assert repo.load("ghost") is None

    def test_save_updates_existing(self, tmp_path):
        repo = self._repo(tmp_path)
        c = _make_contract("svc", title="Original")
        repo.save(c)
        c2 = _make_contract("svc", title="Updated")
        repo.save(c2)
        loaded = repo.load("svc")
        assert loaded.title == "Updated"

    # ── save_tree / load_tree ─────────────────────────────────────────────

    def test_save_tree_creates_json_file(self, tmp_path):
        repo = self._repo(tmp_path)
        pool = {"a": _make_contract("a"), "b": _make_contract("b")}
        repo.save_tree("proj1", pool)
        assert (tmp_path / "soda_v2_tree.json").exists()

    def test_load_tree_roundtrip(self, tmp_path):
        repo = self._repo(tmp_path)
        pool = {"a": _make_contract("a", "Alpha"), "b": _make_contract("b", "Beta")}
        repo.save_tree("proj1", pool)
        loaded = repo.load_tree("proj1")
        assert set(loaded.keys()) == {"a", "b"}
        assert loaded["a"].title == "Alpha"

    def test_load_tree_empty_when_no_file(self, tmp_path):
        repo = self._repo(tmp_path)
        assert repo.load_tree("ghost") == {}

    def test_save_tree_also_writes_individual_contracts(self, tmp_path):
        repo = self._repo(tmp_path)
        pool = {"svc_x": _make_contract("svc_x")}
        repo.save_tree("p", pool)
        individual_file = tmp_path / "contracts" / "svc_x.json"
        assert individual_file.exists()

    # ── list_projects / delete_project ────────────────────────────────────

    def test_list_projects_returns_workspace_when_tree_exists(self, tmp_path):
        repo = self._repo(tmp_path)
        repo.save_tree("p", {"a": _make_contract("a")})
        projects = repo.list_projects()
        assert len(projects) == 1

    def test_list_projects_empty_when_no_tree(self, tmp_path):
        repo = self._repo(tmp_path)
        assert repo.list_projects() == []

    def test_delete_project_removes_tree_and_contracts(self, tmp_path):
        repo = self._repo(tmp_path)
        pool = {"x": _make_contract("x")}
        repo.save_tree("p", pool)
        repo.delete_project("p")
        assert repo.load_tree("p") == {}
        assert not (tmp_path / "soda_v2_tree.json").exists()

    # ── Factory ───────────────────────────────────────────────────────────

    def test_factory_json_backend(self, tmp_path):
        repo = make_contract_repository(tmp_path, backend="json")
        assert isinstance(repo, JsonContractRepository)

    def test_factory_implements_interface(self, tmp_path):
        repo = make_contract_repository(tmp_path)
        assert isinstance(repo, IContractRepository)


# ═══════════════════════════════════════════════════════════════════════════
# SqliteContractRepository
# ═══════════════════════════════════════════════════════════════════════════

class TestSqliteContractRepository:

    def _repo(self, tmp_path) -> SqliteContractRepository:
        return SqliteContractRepository(tmp_path / "test.db")

    # ── save / load ───────────────────────────────────────────────────────

    def test_save_and_load_roundtrip(self, tmp_path):
        repo = self._repo(tmp_path)
        c = _make_contract("db_svc", "DB Service")
        repo.save(c)
        loaded = repo.load("db_svc")
        assert loaded is not None
        assert loaded.contract_id == "db_svc"
        assert loaded.title == "DB Service"

    def test_load_nonexistent_returns_none(self, tmp_path):
        repo = self._repo(tmp_path)
        assert repo.load("nope") is None

    def test_save_upserts_on_conflict(self, tmp_path):
        repo = self._repo(tmp_path)
        c = _make_contract("svc", "V1")
        repo.save(c)
        c2 = _make_contract("svc", "V2")
        repo.save(c2)
        loaded = repo.load("svc")
        assert loaded.title == "V2"

    # ── save_tree / load_tree ─────────────────────────────────────────────

    def test_save_and_load_tree(self, tmp_path):
        repo = self._repo(tmp_path)
        pool = {
            "api": _make_contract("api", "API"),
            "db": _make_contract("db", "DB"),
        }
        repo.save_tree("proj_A", pool)
        loaded = repo.load_tree("proj_A")
        assert set(loaded.keys()) == {"api", "db"}

    def test_load_tree_empty_for_unknown_project(self, tmp_path):
        repo = self._repo(tmp_path)
        assert repo.load_tree("unknown") == {}

    def test_save_tree_multiple_projects_isolated(self, tmp_path):
        repo = self._repo(tmp_path)
        repo.save_tree("proj_1", {"a": _make_contract("a")})
        repo.save_tree("proj_2", {"b": _make_contract("b"), "c": _make_contract("c")})
        assert len(repo.load_tree("proj_1")) == 1
        assert len(repo.load_tree("proj_2")) == 2

    # ── list_projects / delete_project ────────────────────────────────────

    def test_list_projects(self, tmp_path):
        repo = self._repo(tmp_path)
        repo.save_tree("proj_X", {"x": _make_contract("x")})
        repo.save_tree("proj_Y", {"y": _make_contract("y")})
        projects = repo.list_projects()
        assert "proj_X" in projects
        assert "proj_Y" in projects

    def test_list_projects_empty_initially(self, tmp_path):
        repo = self._repo(tmp_path)
        assert repo.list_projects() == []

    def test_delete_project(self, tmp_path):
        repo = self._repo(tmp_path)
        repo.save_tree("del_me", {"a": _make_contract("a")})
        repo.delete_project("del_me")
        assert repo.load_tree("del_me") == {}
        assert "del_me" not in repo.list_projects()

    # ── Extra queries (resumption / UI) ──────────────────────────────────

    def test_pending_contracts_excludes_completed(self, tmp_path):
        repo = self._repo(tmp_path)
        pool = {
            "done": _make_contract("done", status=ContractStatus.COMPLETED),
            "todo": _make_contract("todo", status=ContractStatus.PENDING_EXECUTION),
        }
        repo.save_tree("p", pool)
        pending = repo.pending_contracts("p")
        assert "todo" in pending
        assert "done" not in pending

    def test_project_summary_counts_by_status(self, tmp_path):
        repo = self._repo(tmp_path)
        pool = {
            "a": _make_contract("a", status=ContractStatus.COMPLETED),
            "b": _make_contract("b", status=ContractStatus.COMPLETED),
            "c": _make_contract("c", status=ContractStatus.PENDING_EXECUTION),
        }
        repo.save_tree("p", pool)
        summary = repo.project_summary("p")
        # ContractStatus enum stores values as uppercase (e.g. 'COMPLETED')
        assert summary.get("COMPLETED", 0) == 2

    # ── Factory ───────────────────────────────────────────────────────────

    def test_factory_sqlite_backend(self, tmp_path):
        repo = make_contract_repository(tmp_path, backend="sqlite")
        assert isinstance(repo, SqliteContractRepository)

    def test_schema_created_on_init(self, tmp_path):
        import sqlite3
        repo = self._repo(tmp_path)
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        assert "projects" in tables
        assert "contracts" in tables
