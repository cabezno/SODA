"""Tests for Architect (Arquitecto v2, Fase 3).

The Architect makes Claude API calls, so tests use a mock ClaudeDriver
to avoid real API calls. We validate:
- Correct model is selected per complexity level
- Prompt loading works
- JSON parsing (with and without markdown fences) works
- MasterContract is correctly assembled from driver response
- Refinement loop path works
- Error propagation works
"""
import asyncio
import json
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kernel.intelligence.architect import Architect, _PROMPTS_DIR
from kernel.intelligence.complexity_classifier import (
    MODEL_ASSIGNMENT_BY_COMPLEXITY,
    ComplexityLevel,
)
from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.audit_schemas import AuditReport, Issue, ValidatorResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


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


def _minimal_contract_dict(
    complexity="simple",
    model="claude-haiku-4-5-20251001",
) -> dict:
    return {
        "project_id": "proj_test",
        "project_name": "Test Project",
        "version": "1.0.0",
        "complexity_level": complexity,
        "model_used": model,
        "modules": [{
            "id": "main_service",
            "name": "Main Service",
            "purpose": "Handles all core business logic and data persistence operations",
            "interfaces": [{
                "name": "MainInterface",
                "description": "Core operations",
                "methods": [{
                    "name": "get_item",
                    "parameters": {"item_id": "str"},
                    "returns": "str",
                    "description": "Returns item data from storage by its unique identifier",
                    "example_usage": "service.get_item('abc')",
                }],
            }],
            "goal_ids": ["goal_main"],
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
                "id": "ext_metadata",
                "type": "metadata_field",
                "location": "Entity model",
                "contract": "Must be a JSON-serializable dict with string keys only",
                "description": "Extensible metadata on entities",
                "example_use_case": "Custom tags",
            },
            {
                "id": "ext_events",
                "type": "event_channel",
                "location": "Event bus",
                "contract": "Must follow CloudEvents spec with subject and type fields",
                "description": "Reserved event channel for future integrations",
                "example_use_case": "Webhook delivery",
            },
        ],
        "error_types": [
            {
                "name": "NotFoundError",
                "code": "NOT_FOUND",
                "message_template": "Resource {id} not found",
                "recoverable": False,
            },
            {
                "name": "ValidationError",
                "code": "VALIDATION_FAILED",
                "message_template": "Validation failed: {reason}",
                "recoverable": True,
            },
            {
                "name": "AuthError",
                "code": "AUTH_FAILED",
                "message_template": "Authentication failed for {user}",
                "recoverable": False,
            },
        ],
    }


def _make_driver(response_content: str, error_code: str | None = None):
    """Create a mock ClaudeDriver that returns the given content."""
    driver = MagicMock()
    driver.call = AsyncMock(return_value=FakeDriverResponse(
        content=response_content,
        error_code=error_code,
    ))
    return driver


def _make_audit_report(status="failed") -> AuditReport:
    """Create a minimal AuditReport with one error."""
    issue = Issue(
        severity="error",
        rule="unique_module_ids",
        location="modules[svc]",
        description="ID duplicado",
        suggestion="Usar IDs únicos",
    )
    validator_result = ValidatorResult(
        validator_name="consistency_validator",
        status="failed",
        issues=[issue],
    )
    return AuditReport(
        contract_id="proj_test",
        results=[validator_result],
        overall_status=status,
    )


# ---------------------------------------------------------------------------
# Test: prompt files exist
# ---------------------------------------------------------------------------

def test_all_prompt_files_exist():
    for filename in [
        "architect_simple.md",
        "architect_medium.md",
        "architect_complex.md",
        "architect_refinement.md",
    ]:
        path = _PROMPTS_DIR / filename
        assert path.exists(), f"Missing prompt file: {path}"
        assert path.stat().st_size > 100, f"Prompt file too small: {path}"


def test_prompt_files_have_required_sections():
    for filename, expected_keyword in [
        ("architect_simple.md", "MasterContract"),
        ("architect_medium.md", "MasterContract"),
        ("architect_complex.md", "MasterContract"),
        ("architect_refinement.md", "Refinamiento"),
    ]:
        content = (_PROMPTS_DIR / filename).read_text(encoding="utf-8")
        assert expected_keyword in content, (
            f"{filename} missing expected keyword: {expected_keyword}"
        )


# ---------------------------------------------------------------------------
# Test: model selection
# ---------------------------------------------------------------------------

def test_correct_model_for_simple():
    driver = _make_driver(json.dumps(_minimal_contract_dict()))
    architect = Architect(driver)
    run(architect.generate_master_contract({}, ComplexityLevel.SIMPLE))
    _, kwargs = driver.call.call_args
    assert kwargs.get("model") == MODEL_ASSIGNMENT_BY_COMPLEXITY["simple"]


def test_correct_model_for_medium():
    driver = _make_driver(json.dumps(
        _minimal_contract_dict("medium", MODEL_ASSIGNMENT_BY_COMPLEXITY["medium"])
    ))
    architect = Architect(driver)
    run(architect.generate_master_contract({}, ComplexityLevel.MEDIUM))
    _, kwargs = driver.call.call_args
    assert kwargs.get("model") == MODEL_ASSIGNMENT_BY_COMPLEXITY["medium"]


def test_correct_model_for_complex():
    driver = _make_driver(json.dumps(
        _minimal_contract_dict("complex", MODEL_ASSIGNMENT_BY_COMPLEXITY["complex"])
    ))
    architect = Architect(driver)
    run(architect.generate_master_contract({}, ComplexityLevel.COMPLEX))
    _, kwargs = driver.call.call_args
    assert kwargs.get("model") == MODEL_ASSIGNMENT_BY_COMPLEXITY["complex"]


# ---------------------------------------------------------------------------
# Test: contract generation
# ---------------------------------------------------------------------------

def test_generate_returns_master_contract():
    contract_json = json.dumps(_minimal_contract_dict())
    driver = _make_driver(contract_json)
    architect = Architect(driver)
    contract = run(architect.generate_master_contract(
        blueprint={"nombre": "Test"},
        complexity=ComplexityLevel.SIMPLE,
    ))
    assert isinstance(contract, MasterContract)
    assert contract.project_id == "proj_test"
    assert contract.complexity_level == "simple"


def test_generate_sets_complexity_and_model():
    contract_json = json.dumps(_minimal_contract_dict())
    driver = _make_driver(contract_json)
    architect = Architect(driver)
    contract = run(architect.generate_master_contract(
        blueprint={},
        complexity=ComplexityLevel.SIMPLE,
    ))
    assert contract.complexity_level == "simple"
    assert contract.model_used == MODEL_ASSIGNMENT_BY_COMPLEXITY["simple"]


def test_generate_strips_markdown_fences():
    contract_dict = _minimal_contract_dict()
    fenced = f"```json\n{json.dumps(contract_dict)}\n```"
    driver = _make_driver(fenced)
    architect = Architect(driver)
    contract = run(architect.generate_master_contract({}, ComplexityLevel.SIMPLE))
    assert isinstance(contract, MasterContract)


def test_generate_strips_plain_fences():
    contract_dict = _minimal_contract_dict()
    fenced = f"```\n{json.dumps(contract_dict)}\n```"
    driver = _make_driver(fenced)
    architect = Architect(driver)
    contract = run(architect.generate_master_contract({}, ComplexityLevel.SIMPLE))
    assert isinstance(contract, MasterContract)


def test_generate_raises_on_api_error():
    driver = _make_driver("ERROR:AUTH: bad key", error_code="AUTH")
    architect = Architect(driver)
    with pytest.raises(RuntimeError, match="AUTH"):
        run(architect.generate_master_contract({}, ComplexityLevel.SIMPLE))


def test_generate_raises_on_invalid_json():
    driver = _make_driver("this is not json at all")
    architect = Architect(driver)
    with pytest.raises(Exception):
        run(architect.generate_master_contract({}, ComplexityLevel.SIMPLE))


# ---------------------------------------------------------------------------
# Test: contract refinement
# ---------------------------------------------------------------------------

def test_refine_returns_master_contract():
    original = MasterContract(**_minimal_contract_dict())
    refined_json = json.dumps(_minimal_contract_dict())
    driver = _make_driver(refined_json)
    architect = Architect(driver)
    audit = _make_audit_report("failed")

    result = run(architect.refine_contract(original, audit, ComplexityLevel.SIMPLE))
    assert isinstance(result, MasterContract)


def test_refine_uses_same_model_as_generation():
    original = MasterContract(**_minimal_contract_dict())
    driver = _make_driver(json.dumps(_minimal_contract_dict()))
    architect = Architect(driver)
    audit = _make_audit_report()

    run(architect.refine_contract(original, audit, ComplexityLevel.MEDIUM))
    _, kwargs = driver.call.call_args
    assert kwargs.get("model") == MODEL_ASSIGNMENT_BY_COMPLEXITY["medium"]


def test_refine_raises_on_api_error():
    original = MasterContract(**_minimal_contract_dict())
    driver = _make_driver("ERROR:RATE_LIMIT: quota exceeded", error_code="RATE_LIMIT")
    architect = Architect(driver)
    audit = _make_audit_report()
    with pytest.raises(RuntimeError, match="RATE_LIMIT"):
        run(architect.refine_contract(original, audit, ComplexityLevel.SIMPLE))


# ---------------------------------------------------------------------------
# Test: prompt content is passed to driver
# ---------------------------------------------------------------------------

def test_generate_passes_system_prompt_to_driver():
    driver = _make_driver(json.dumps(_minimal_contract_dict()))
    architect = Architect(driver)
    run(architect.generate_master_contract(
        blueprint={"nombre": "My App"},
        complexity=ComplexityLevel.SIMPLE,
    ))
    _, kwargs = driver.call.call_args
    system_prompt = kwargs.get("system_prompt", "")
    assert "MasterContract" in system_prompt or "Arquitecto" in system_prompt


def test_generate_includes_blueprint_in_user_message():
    driver = _make_driver(json.dumps(_minimal_contract_dict()))
    architect = Architect(driver)
    blueprint = {"nombre": "Mi App Especial"}
    run(architect.generate_master_contract(
        blueprint=blueprint,
        complexity=ComplexityLevel.SIMPLE,
    ))
    _, kwargs = driver.call.call_args
    user_message = kwargs.get("user_message", "")
    assert "Mi App Especial" in user_message


def test_refine_includes_feedback_in_user_message():
    original = MasterContract(**_minimal_contract_dict())
    driver = _make_driver(json.dumps(_minimal_contract_dict()))
    architect = Architect(driver)
    audit = _make_audit_report("failed")

    run(architect.refine_contract(original, audit, ComplexityLevel.SIMPLE))
    _, kwargs = driver.call.call_args
    user_message = kwargs.get("user_message", "")
    assert "Feedback del Auditor" in user_message
    assert "Errores críticos" in user_message
