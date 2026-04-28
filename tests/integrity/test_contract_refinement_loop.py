"""Tests for ContractRefinementLoop (Arquitecto v2, Fase 4)."""
import asyncio
import json
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from kernel.intelligence.architect import Architect
from kernel.intelligence.complexity_classifier import ComplexityLevel
from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.audit_schemas import AuditReport, Issue, ValidatorResult
from kernel.integrity.contract_auditor import ContractAuditor
from kernel.orchestration.contract_refinement_loop import (
    ContractRefinementLoop,
    ContractResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.run(coro)


@dataclass
class FakeDriverResponse:
    content: str
    error_code: Optional[str] = None
    tokens_input: int = 100
    tokens_output: int = 200
    latency_ms: int = 500
    model_used: str = "claude-haiku-4-5-20251001"
    cost_usd: float = 0.001
    metadata: dict = field(default_factory=dict)


def _contract_dict(complexity="simple") -> dict:
    return {
        "project_id": "proj_loop_test",
        "project_name": "Loop Test Project",
        "version": "1.0.0",
        "complexity_level": complexity,
        "model_used": "claude-haiku-4-5-20251001",
        "modules": [{
            "id": "core_service",
            "name": "Core Service",
            "purpose": "Handles all core business logic and data persistence operations",
            "interfaces": [{
                "name": "CoreInterface",
                "description": "Core operations",
                "methods": [{
                    "name": "process",
                    "parameters": {"data": "str"},
                    "returns": "str",
                    "description": "Processes incoming data and returns the transformed result",
                    "example_usage": "service.process('input')",
                }],
            }],
            "goal_ids": ["goal_core"],
            "layer": "application",
        }],
        "extension_points": [
            {
                "id": "ext_middleware",
                "type": "middleware_slot",
                "location": "HTTP pipeline",
                "contract": "Must implement process(request) -> response and be stateless",
                "description": "HTTP middleware slot",
                "example_use_case": "Rate limiting",
            },
            {
                "id": "ext_meta",
                "type": "metadata_field",
                "location": "Entity",
                "contract": "Must be a JSON-serializable dict with string keys only",
                "description": "Metadata",
                "example_use_case": "Tags",
            },
            {
                "id": "ext_events",
                "type": "event_channel",
                "location": "Bus",
                "contract": "Must follow CloudEvents spec with subject and type fields",
                "description": "Events",
                "example_use_case": "Webhooks",
            },
        ],
        "error_types": [
            {
                "name": "NotFound",
                "code": "NOT_FOUND",
                "message_template": "Resource {id} not found",
                "recoverable": False,
            },
            {
                "name": "Validation",
                "code": "VALIDATION_ERROR",
                "message_template": "Validation failed for {field}",
                "recoverable": True,
            },
            {
                "name": "AuthFailed",
                "code": "AUTH_FAILED",
                "message_template": "Authentication required for {action}",
                "recoverable": False,
            },
        ],
    }


def _make_architect(contract_json: str | None = None, raises: Exception | None = None) -> Architect:
    """Architect that always returns the same contract JSON."""
    if contract_json is None:
        contract_json = json.dumps(_contract_dict())

    driver = MagicMock()
    if raises:
        driver.call = AsyncMock(side_effect=raises)
    else:
        driver.call = AsyncMock(return_value=FakeDriverResponse(content=contract_json))

    arch = Architect(driver)
    return arch


def _make_auditor(status: str = "passed") -> ContractAuditor:
    """Auditor that always returns the given status."""
    auditor = MagicMock(spec=ContractAuditor)

    issue = Issue(
        severity="error" if status == "failed" else "warning",
        rule="test_rule",
        location="test",
        description="Test issue",
        suggestion="Fix it",
    )
    validator_result = ValidatorResult(
        validator_name="mock_validator",
        status=status,
        issues=[issue] if status != "passed" else [],
    )
    report = AuditReport(
        contract_id="proj_loop_test",
        results=[validator_result],
        overall_status=status,
    )
    auditor.audit = AsyncMock(return_value=report)
    return auditor


# ---------------------------------------------------------------------------
# Test: approved on first attempt
# ---------------------------------------------------------------------------

def test_loop_approved_first_attempt():
    architect = _make_architect()
    auditor = _make_auditor("passed")
    loop = ContractRefinementLoop(architect, auditor, max_attempts=3)

    result = run(loop.execute({}, ComplexityLevel.SIMPLE))

    assert result.status == "approved"
    assert result.contract is not None
    assert len(result.attempts) == 1
    assert architect.driver.call.call_count == 1


def test_loop_approved_with_warnings_first_attempt():
    architect = _make_architect()
    auditor = _make_auditor("passed_with_warnings")
    loop = ContractRefinementLoop(architect, auditor, max_attempts=3)

    result = run(loop.execute({}, ComplexityLevel.SIMPLE))

    assert result.status == "approved_with_warnings"
    assert result.contract is not None
    assert len(result.attempts) == 1


# ---------------------------------------------------------------------------
# Test: approved after refinement
# ---------------------------------------------------------------------------

def test_loop_approved_after_one_refinement():
    """First attempt fails audit, second passes."""
    contract_json = json.dumps(_contract_dict())
    architect = _make_architect(contract_json)

    # First call returns "failed", second returns "passed"
    auditor = MagicMock(spec=ContractAuditor)
    failed_issue = Issue(
        severity="error", rule="test", location="x",
        description="Error", suggestion="Fix"
    )
    failed_result = ValidatorResult(
        validator_name="mock", status="failed", issues=[failed_issue]
    )
    failed_report = AuditReport(
        contract_id="proj_loop_test",
        results=[failed_result],
        overall_status="failed",
    )
    passed_result = ValidatorResult(
        validator_name="mock", status="passed", issues=[]
    )
    passed_report = AuditReport(
        contract_id="proj_loop_test",
        results=[passed_result],
        overall_status="passed",
    )
    auditor.audit = AsyncMock(side_effect=[failed_report, passed_report])

    loop = ContractRefinementLoop(architect, auditor, max_attempts=3)
    result = run(loop.execute({}, ComplexityLevel.SIMPLE))

    assert result.status == "approved"
    assert len(result.attempts) == 2
    assert architect.driver.call.call_count == 2  # generate + refine


# ---------------------------------------------------------------------------
# Test: exhausts all attempts
# ---------------------------------------------------------------------------

def test_loop_exhausts_attempts():
    architect = _make_architect()
    auditor = _make_auditor("failed")
    loop = ContractRefinementLoop(architect, auditor, max_attempts=3)

    result = run(loop.execute({}, ComplexityLevel.SIMPLE))

    assert result.status == "requires_user_intervention"
    assert len(result.attempts) == 3
    assert result.final_issues is not None


def test_loop_max_attempts_is_respected():
    architect = _make_architect()
    auditor = _make_auditor("failed")
    loop = ContractRefinementLoop(architect, auditor, max_attempts=2)

    result = run(loop.execute({}, ComplexityLevel.SIMPLE))

    assert len(result.attempts) == 2
    assert architect.driver.call.call_count == 2


# ---------------------------------------------------------------------------
# Test: error handling
# ---------------------------------------------------------------------------

def test_loop_continues_if_non_final_architect_error():
    """If generate fails on attempt 0 (not the last), loop should try again."""
    contract_json = json.dumps(_contract_dict())
    driver = MagicMock()
    # First call raises, second succeeds
    driver.call = AsyncMock(side_effect=[
        Exception("API timeout"),
        FakeDriverResponse(content=contract_json),
    ])
    architect = Architect(driver)
    auditor = _make_auditor("passed")
    loop = ContractRefinementLoop(architect, auditor, max_attempts=2)

    result = run(loop.execute({}, ComplexityLevel.SIMPLE))
    # Second attempt should succeed
    assert result.status == "approved"


def test_loop_escalates_if_all_attempts_fail_with_exceptions():
    """If generate fails on all attempts, escalate."""
    driver = MagicMock()
    driver.call = AsyncMock(side_effect=Exception("Persistent failure"))
    architect = Architect(driver)
    auditor = _make_auditor("passed")
    loop = ContractRefinementLoop(architect, auditor, max_attempts=2)

    result = run(loop.execute({}, ComplexityLevel.SIMPLE))
    assert result.status == "requires_user_intervention"


# ---------------------------------------------------------------------------
# Test: ContractResult structure
# ---------------------------------------------------------------------------

def test_result_has_attempts_list():
    architect = _make_architect()
    auditor = _make_auditor("passed")
    loop = ContractRefinementLoop(architect, auditor)

    result = run(loop.execute({}, ComplexityLevel.SIMPLE))

    assert isinstance(result.attempts, list)
    assert len(result.attempts) >= 1
    assert result.attempts[0].attempt_number == 1


def test_result_attempt_has_contract_and_report():
    architect = _make_architect()
    auditor = _make_auditor("passed")
    loop = ContractRefinementLoop(architect, auditor)

    result = run(loop.execute({}, ComplexityLevel.SIMPLE))

    attempt = result.attempts[0]
    assert isinstance(attempt.contract, MasterContract)
    assert isinstance(attempt.audit_report, AuditReport)
    assert attempt.timestamp  # non-empty ISO timestamp


def test_result_final_issues_set_on_intervention():
    architect = _make_architect()
    auditor = _make_auditor("failed")
    loop = ContractRefinementLoop(architect, auditor, max_attempts=2)

    result = run(loop.execute({}, ComplexityLevel.SIMPLE))

    assert result.status == "requires_user_intervention"
    assert result.final_issues is not None
    assert isinstance(result.final_issues, AuditReport)


def test_result_final_issues_none_on_approved():
    architect = _make_architect()
    auditor = _make_auditor("passed")
    loop = ContractRefinementLoop(architect, auditor)

    result = run(loop.execute({}, ComplexityLevel.SIMPLE))

    assert result.status == "approved"
    assert result.final_issues is None


# ---------------------------------------------------------------------------
# Test: integration with real validators (no mock auditor)
# ---------------------------------------------------------------------------

def test_loop_with_real_auditor_passes_valid_contract():
    architect = _make_architect(json.dumps(_contract_dict()))
    auditor = ContractAuditor(goal_tree={})
    loop = ContractRefinementLoop(architect, auditor, max_attempts=1)

    result = run(loop.execute({}, ComplexityLevel.SIMPLE))

    # The contract fixture is valid — should pass or pass_with_warnings
    assert result.status in ("approved", "approved_with_warnings")
    assert result.contract is not None
