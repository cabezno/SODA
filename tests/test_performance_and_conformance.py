"""Tests for PerformanceTracker and ConformanceVerifier."""
import asyncio
import json
import io
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from kernel.monitoring.performance_tracker import PerformanceTracker
from kernel.intelligence.conformance_verifier import ConformanceVerifier


def run(coro):
    return asyncio.run(coro)


# ── Helpers ──────────────────────────────────────────────────────────────────

@dataclass
class FakeDriverResponse:
    content: str
    error_code: Optional[str] = None
    tokens_input: int = 10
    tokens_output: int = 20
    latency_ms: int = 100
    model_used: str = "claude-haiku-4-5-20251001"
    cost_usd: float = 0.0001
    metadata: dict = field(default_factory=dict)


def _make_driver(content: str, error_code: Optional[str] = None):
    driver = MagicMock()
    driver.call = AsyncMock(return_value=FakeDriverResponse(content=content, error_code=error_code))
    return driver


def _simple_architecture() -> dict:
    return {
        "modulos": [
            {
                "nombre": "auth_service",
                "descripcion": "Handles authentication",
                "archivos": ["auth_service.py"],
                "interfaces": [],
            },
            {
                "nombre": "user_model",
                "descripcion": "User data model",
                "archivos": ["user_model.py"],
                "interfaces": [],
            },
        ]
    }


# ═══════════════════════════════════════════════════════════════════════════
# PerformanceTracker
# ═══════════════════════════════════════════════════════════════════════════

class TestPerformanceTracker:

    def test_records_qwen_l1_success(self):
        t = PerformanceTracker()
        t.record_file_generated(provider="qwen", level=1, validated=True)
        assert len(t._files) == 1
        assert t._files[0].provider == "qwen"
        assert t._files[0].level == 1
        assert t._files[0].validated is True

    def test_records_escalation_to_claude(self):
        t = PerformanceTracker()
        t.record_file_generated(provider="claude", level=4, validated=True)
        assert t._files[0].provider == "claude"

    def test_records_failed_file(self):
        t = PerformanceTracker()
        t.record_file_generated(provider="none", level=6, validated=False)
        assert not t._files[0].validated

    def test_multiple_files_accumulated(self):
        t = PerformanceTracker()
        t.record_file_generated("qwen", 1, True)
        t.record_file_generated("qwen", 2, True)
        t.record_file_generated("claude", 4, True)
        assert len(t._files) == 3

    def test_records_contract_result(self):
        t = PerformanceTracker()
        t.record_contract_result("approved", 2, "claude-sonnet-4-6")
        assert t._architect_status == "approved"
        assert t._architect_attempts == 2
        assert t._architect_model == "claude-sonnet-4-6"

    def test_records_conformance_compliant(self):
        t = PerformanceTracker()
        t.record_conformance(fixed=False)
        assert t._conformance_compliant == 1
        assert t._conformance_fixed == 0

    def test_records_conformance_fixed(self):
        t = PerformanceTracker()
        t.record_conformance(fixed=True)
        assert t._conformance_fixed == 1
        assert t._conformance_compliant == 0

    def test_records_conformance_skipped(self):
        t = PerformanceTracker()
        t.record_conformance(fixed=False, skipped=True)
        assert t._conformance_skipped == 1
        assert t._conformance_compliant == 0

    def test_records_gemini_phases(self):
        t = PerformanceTracker()
        t.record_gemini_phase("capabilities")
        t.record_gemini_phase("architecture")
        assert t._gemini_phases == ["capabilities", "architecture"]

    def test_print_report_empty_does_not_crash(self, capsys):
        t = PerformanceTracker()
        t.print_report()
        out = capsys.readouterr().out
        assert "SODA" in out

    def test_print_report_shows_qwen_stats(self, capsys):
        t = PerformanceTracker()
        t.record_file_generated("qwen", 1, True)
        t.record_file_generated("qwen", 2, True)
        t.record_file_generated("claude", 4, True)
        t.print_report()
        out = capsys.readouterr().out
        assert "Qwen" in out
        assert "Archivos intentados" in out

    def test_print_report_shows_architect_section(self, capsys):
        t = PerformanceTracker()
        t.record_contract_result("approved", 1)
        t.print_report()
        out = capsys.readouterr().out
        assert "Arquitecto v2" in out
        assert "aprobado" in out

    def test_print_report_shows_conformance_section(self, capsys):
        t = PerformanceTracker()
        t.record_conformance(fixed=False)
        t.record_conformance(fixed=True)
        t.print_report()
        out = capsys.readouterr().out
        assert "Conformidad" in out
        assert "Conformes" in out
        assert "Corregidos" in out

    def test_print_report_shows_gemini_phases(self, capsys):
        t = PerformanceTracker()
        t.record_gemini_phase("capabilities")
        t.record_gemini_phase("evolution")
        t.print_report()
        out = capsys.readouterr().out
        assert "Gemini" in out
        assert "CAP" in out
        assert "EVOLUTION" in out

    def test_percentage_calculation_correct(self, capsys):
        t = PerformanceTracker()
        # 2 L1 successes, 1 escalation → 66.7%, 33.3%
        t.record_file_generated("qwen", 1, True)
        t.record_file_generated("qwen", 1, True)
        t.record_file_generated("claude", 4, True)
        t.print_report()
        out = capsys.readouterr().out
        assert "66.7%" in out
        assert "33.3%" in out


# ═══════════════════════════════════════════════════════════════════════════
# ConformanceVerifier
# ═══════════════════════════════════════════════════════════════════════════

class TestConformanceVerifier:

    def test_compliant_file_not_rewritten(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        f = source / "auth_service.py"
        original = "class AuthService:\n    def login(self): pass\n"
        f.write_text(original)

        driver = _make_driver("COMPLIANT")
        tracker = PerformanceTracker()
        verifier = ConformanceVerifier(driver, tracker)

        arch = {"modulos": [{"nombre": "auth_service", "descripcion": "Auth", "archivos": ["auth_service.py"]}]}
        result = run(verifier.verify_project(arch, source))

        assert result["fixed"] == 0
        assert result["checked"] == 1
        assert f.read_text() == original  # unchanged
        assert tracker._conformance_compliant == 1

    def test_non_compliant_file_is_rewritten(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        f = source / "auth_service.py"
        f.write_text("# empty stub")

        corrected_code = "class AuthService:\n    def login(self, user, pwd): return True\n"
        driver = _make_driver(corrected_code)
        tracker = PerformanceTracker()
        verifier = ConformanceVerifier(driver, tracker)

        arch = {"modulos": [{"nombre": "auth_service", "descripcion": "Auth", "archivos": ["auth_service.py"]}]}
        result = run(verifier.verify_project(arch, source))

        assert result["fixed"] == 1
        assert f.read_text() == corrected_code
        assert tracker._conformance_fixed == 1

    def test_missing_file_is_skipped(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()

        driver = _make_driver("COMPLIANT")
        tracker = PerformanceTracker()
        verifier = ConformanceVerifier(driver, tracker)

        arch = {"modulos": [{"nombre": "ghost_module", "descripcion": "ghost", "archivos": ["ghost.py"]}]}
        result = run(verifier.verify_project(arch, source))

        assert result["skipped"] == 1
        assert result["fixed"] == 0
        assert tracker._conformance_skipped == 1
        driver.call.assert_not_called()

    def test_driver_error_leaves_file_unchanged(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        f = source / "auth.py"
        original = "# original"
        f.write_text(original)

        driver = _make_driver("", error_code="rate_limit")
        verifier = ConformanceVerifier(driver)

        arch = {"modulos": [{"nombre": "auth", "descripcion": "Auth", "archivos": ["auth.py"]}]}
        run(verifier.verify_project(arch, source))

        assert f.read_text() == original

    def test_conformance_model_used(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "mod.py").write_text("pass")

        driver = _make_driver("COMPLIANT")
        verifier = ConformanceVerifier(driver)

        arch = {"modulos": [{"nombre": "mod", "descripcion": "Module", "archivos": ["mod.py"]}]}
        run(verifier.verify_project(arch, source))

        call_kwargs = driver.call.call_args.kwargs
        assert call_kwargs.get("model") == "gemini-3-flash-preview"

    def test_strips_markdown_fences_from_correction(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        f = source / "svc.py"
        f.write_text("# stub")

        corrected_code = "class Svc:\n    pass\n"
        response_with_fences = f"```python\n{corrected_code}```"
        driver = _make_driver(response_with_fences)
        verifier = ConformanceVerifier(driver)

        arch = {"modulos": [{"nombre": "svc", "descripcion": "Service", "archivos": ["svc.py"]}]}
        run(verifier.verify_project(arch, source))

        assert f.read_text() == corrected_code

    def test_no_modules_returns_zero_counts(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        driver = _make_driver("COMPLIANT")
        verifier = ConformanceVerifier(driver)

        result = run(verifier.verify_project({"modulos": []}, source))
        assert result == {"checked": 0, "fixed": 0, "skipped": 0}
        driver.call.assert_not_called()

    def test_find_files_by_name_heuristic(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "auth_handler.py").write_text("# auth")
        (source / "unrelated.py").write_text("# other")

        driver = _make_driver("COMPLIANT")
        verifier = ConformanceVerifier(driver)

        # Module with no archivos — should find auth_handler.py by name
        arch = {"modulos": [{"nombre": "auth_service", "descripcion": "Auth", "archivos": []}]}
        result = run(verifier.verify_project(arch, source))

        assert result["checked"] == 1
        assert driver.call.call_count == 1

    def test_multiple_modules_all_processed(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "mod_a.py").write_text("class A: pass")
        (source / "mod_b.py").write_text("class B: pass")

        driver = _make_driver("COMPLIANT")
        tracker = PerformanceTracker()
        verifier = ConformanceVerifier(driver, tracker)

        arch = {
            "modulos": [
                {"nombre": "mod_a", "descripcion": "A", "archivos": ["mod_a.py"]},
                {"nombre": "mod_b", "descripcion": "B", "archivos": ["mod_b.py"]},
            ]
        }
        result = run(verifier.verify_project(arch, source))

        assert result["checked"] == 2
        assert driver.call.call_count == 2
        assert tracker._conformance_compliant == 2

    def test_content_truncated_at_limit(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        big_file = source / "big.py"
        big_file.write_text("x" * 20_000)

        driver = _make_driver("COMPLIANT")
        verifier = ConformanceVerifier(driver)

        arch = {"modulos": [{"nombre": "big", "descripcion": "Big", "archivos": ["big.py"]}]}
        run(verifier.verify_project(arch, source))

        user_msg = driver.call.call_args.kwargs["user_message"]
        assert "truncado" in user_msg
        assert len(user_msg) < 15_000

    # ── v2 paths: topology + master_contract ─────────────────────────────

    def test_verify_with_topology_uses_archivos_principales(self, tmp_path):
        """topology.modulos[].archivos_principales is the v2 source of file paths."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "api.py").write_text("class APIService: pass")

        driver = _make_driver("COMPLIANT")
        tracker = PerformanceTracker()
        verifier = ConformanceVerifier(driver, tracker)

        topology = {"modulos": [{"id": "api_service", "archivos_principales": ["api.py"]}]}
        # Empty legacy arch — verifier must use topology
        result = run(verifier.verify_project({"modulos": []}, source, topology=topology))

        assert result["checked"] == 1
        assert tracker._conformance_compliant == 1

    def test_verify_with_master_contract_enriches_prompt(self, tmp_path):
        """master_contract typed interfaces are included in the Haiku prompt."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "auth.py").write_text("class AuthService: pass")

        driver = _make_driver("COMPLIANT")
        verifier = ConformanceVerifier(driver)

        master_contract = {
            "modules": [{
                "id": "auth_service",
                "interfaces": [{"name": "login", "parameters": {"user": "str"}, "returns": "bool"}],
                "archivos_principales": ["auth.py"],
            }]
        }
        arch = {"modulos": [{"nombre": "auth_service", "archivos": ["auth.py"]}]}
        result = run(verifier.verify_project(arch, source, master_contract=master_contract))

        assert result["checked"] == 1
        # Typed interface should appear in the user message sent to Haiku
        user_msg = driver.call.call_args.kwargs["user_message"]
        assert "login" in user_msg

    def test_verify_topology_and_master_contract_combined(self, tmp_path):
        """When both topology and master_contract are provided, topology drives file paths
        and master_contract enriches the interface check."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "svc.py").write_text("def process(data): return data")

        driver = _make_driver("COMPLIANT")
        tracker = PerformanceTracker()
        verifier = ConformanceVerifier(driver, tracker)

        topology = {"modulos": [{"id": "svc", "archivos_principales": ["svc.py"]}]}
        master_contract = {
            "modules": [{
                "id": "svc",
                "interfaces": [{"name": "process", "parameters": {"data": "dict"}, "returns": "dict"}],
                "archivos_principales": ["svc.py"],
            }]
        }
        result = run(verifier.verify_project({"modulos": []}, source,
                                             master_contract=master_contract, topology=topology))

        assert result["checked"] == 1
        assert tracker._conformance_compliant == 1
