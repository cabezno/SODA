"""Tests for ContractAuditor integration (Arquitecto v2, Fase 2)."""
import asyncio
import pytest

from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.contract_auditor import ContractAuditor


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _ext(id_="ext_01", ext_type="middleware_slot") -> dict:
    return {
        "id": id_,
        "type": ext_type,
        "location": "HTTP pipeline",
        "contract": "Must implement process(request) and return response object",
        "description": "Slot for HTTP middleware",
        "example_use_case": "Add rate limiting",
    }


def _err(name="NotFoundError", code="NOT_FOUND") -> dict:
    return {
        "name": name,
        "code": code,
        "message_template": "Resource {id} not found",
        "recoverable": False,
    }


def _method(**overrides) -> dict:
    base = {
        "name": "get_item",
        "parameters": {"item_id": "str"},
        "returns": "str",
        "description": "Returns item data by its unique identifier",
        "example_usage": "service.get_item('abc')",
    }
    base.update(overrides)
    return base


def _interface(**overrides) -> dict:
    base = {
        "name": "ItemInterface",
        "description": "Item operations",
        "methods": [_method()],
    }
    base.update(overrides)
    return base


def _valid_contract(**overrides) -> MasterContract:
    base = {
        "project_id": "proj_audit_test",
        "project_name": "Audit Test",
        "complexity_level": "simple",
        "model_used": "claude-haiku-4-5-20251001",
        "modules": [{
            "id": "item_service",
            "name": "Item Service",
            "purpose": "Handles item creation and retrieval with full validation",
            "interfaces": [_interface()],
            "goal_ids": ["goal_items"],
            "layer": "application",
        }],
        "extension_points": [_ext("e1"), _ext("e2"), _ext("e3")],
        "error_types": [
            _err("NotFound", "NOT_FOUND"),
            _err("Validation", "VALIDATION_FAILED"),
            _err("Auth", "AUTH_ERROR"),
        ],
    }
    base.update(overrides)
    return MasterContract(**base)


# ---------------------------------------------------------------------------
# ContractAuditor
# ---------------------------------------------------------------------------

def test_auditor_passes_valid_contract():
    auditor = ContractAuditor()
    report = run(auditor.audit(_valid_contract()))
    assert report.overall_status in ("passed", "passed_with_warnings")
    assert report.contract_id == "proj_audit_test"


def test_auditor_runs_all_validators():
    auditor = ContractAuditor()
    report = run(auditor.audit(_valid_contract()))
    validator_names = {r.validator_name for r in report.results}
    expected = {
        "consistency_validator",
        "completeness_validator",
        "dependency_validator",
        "naming_validator",
        "extensibility_validator",
        "traceability_validator",
    }
    assert expected.issubset(validator_names)


def test_auditor_fails_contract_with_errors():
    # Duplicate module IDs → consistency error
    contract = _valid_contract(modules=[
        {
            "id": "item_service",
            "name": "Item Service",
            "purpose": "Handles item creation, retrieval, and search operations",
            "interfaces": [_interface()],
            "goal_ids": ["goal_items"],
            "layer": "application",
        },
        {
            "id": "item_service",  # duplicate
            "name": "Another Item Service",
            "purpose": "A second module with the same ID causing conflict",
            "interfaces": [_interface()],
            "goal_ids": ["goal_items"],
            "layer": "application",
        },
    ])
    auditor = ContractAuditor()
    report = run(auditor.audit(contract))
    assert report.overall_status == "failed"
    assert len(report.all_errors) > 0


def test_auditor_to_feedback_contains_errors():
    contract = _valid_contract(modules=[
        {
            "id": "dup",
            "name": "A",
            "purpose": "Handles all A-related operations in the system layer",
            "interfaces": [_interface()],
            "goal_ids": ["g1"],
            "layer": "application",
        },
        {
            "id": "dup",
            "name": "B",
            "purpose": "Handles all B-related operations in the system layer",
            "interfaces": [_interface()],
            "goal_ids": ["g1"],
            "layer": "application",
        },
    ])
    auditor = ContractAuditor()
    report = run(auditor.audit(contract))
    feedback = report.to_architect_feedback()
    assert "Errores críticos" in feedback
    assert "Feedback del Auditor" in feedback


def test_auditor_overall_status_passed_when_only_warnings():
    # All required types for extensibility present → no warnings there
    # But use only-middleware extension points → missing metadata_field + event_channel → warnings
    contract = _valid_contract(extension_points=[
        _ext("e1", "middleware_slot"),
        _ext("e2", "middleware_slot"),
        _ext("e3", "middleware_slot"),
    ])
    auditor = ContractAuditor()
    report = run(auditor.audit(contract))
    # Missing required types → warnings but not errors
    assert report.overall_status in ("passed_with_warnings",)


def test_auditor_with_goal_tree_full_mode():
    tree = {"id": "root", "children": [{"id": "goal_items"}]}
    auditor = ContractAuditor(goal_tree=tree)
    report = run(auditor.audit(_valid_contract()))
    assert report.overall_status in ("passed", "passed_with_warnings")


def test_auditor_with_goal_tree_catches_invalid_goal():
    tree = {"id": "root", "children": [{"id": "goal_items"}]}
    auditor = ContractAuditor(goal_tree=tree)
    contract = _valid_contract(modules=[{
        "id": "item_service",
        "name": "Item Service",
        "purpose": "Handles item creation, retrieval, and full lifecycle management",
        "interfaces": [_interface()],
        "goal_ids": ["nonexistent_goal_xyz"],
        "layer": "application",
    }])
    report = run(auditor.audit(contract))
    trace_result = next(
        r for r in report.results if r.validator_name == "traceability_validator"
    )
    errors = [i for i in trace_result.issues if i.rule == "goal_ids_valid"]
    assert len(errors) == 1


def test_auditor_report_has_timing():
    auditor = ContractAuditor()
    report = run(auditor.audit(_valid_contract()))
    for result in report.results:
        assert result.execution_time_ms >= 0


def test_auditor_all_errors_property():
    contract = _valid_contract(modules=[
        {
            "id": "svc",
            "name": "Svc",
            "purpose": "Handles all service operations with full lifecycle support",
            "interfaces": [_interface()],
            "goal_ids": ["g1"],
            "layer": "application",
        },
        {
            "id": "svc",
            "name": "Svc2",
            "purpose": "Another service with duplicate ID causing a conflict",
            "interfaces": [_interface()],
            "goal_ids": ["g1"],
            "layer": "application",
        },
    ])
    auditor = ContractAuditor()
    report = run(auditor.audit(contract))
    assert len(report.all_errors) > 0
    assert all(i.severity == "error" for i in report.all_errors)
