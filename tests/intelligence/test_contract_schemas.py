"""Tests for MasterContract Pydantic schemas (Arquitecto v2, Fase 1)."""
import pytest
from pydantic import ValidationError

from kernel.intelligence.contract_schemas import (
    ArchitecturalDecision,
    Constant,
    DataType,
    ErrorType,
    EventChannel,
    ExtensionPoint,
    Interface,
    InterfaceMethod,
    MasterContract,
    Module,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _method(**overrides) -> dict:
    base = {
        "name": "get_user",
        "parameters": {"user_id": "str"},
        "returns": "User",
        "description": "Retrieves a user by their ID from the database",
        "example_usage": "service.get_user('abc123')",
    }
    base.update(overrides)
    return base


def _interface(**overrides) -> dict:
    base = {
        "name": "UserServiceInterface",
        "description": "Public interface for user operations",
        "methods": [_method()],
    }
    base.update(overrides)
    return base


def _module(**overrides) -> dict:
    base = {
        "id": "user_service",
        "name": "User Service",
        "purpose": "Handles all user-related business logic and persistence operations",
        "interfaces": [_interface()],
        "goal_ids": ["goal_user_management"],
        "layer": "application",
    }
    base.update(overrides)
    return base


def _extension_point(id_: str = "ext_middleware") -> dict:
    return {
        "id": id_,
        "type": "middleware_slot",
        "location": "HTTP request pipeline",
        "contract": "Must implement process(request) -> response interface and be stateless",
        "description": "Slot for custom middleware in the HTTP pipeline",
        "example_use_case": "Add rate limiting middleware",
    }


def _error_type(name: str = "UserNotFoundError", code: str = "USER_NOT_FOUND") -> dict:
    return {
        "name": name,
        "code": code,
        "message_template": "User with id {user_id} not found",
        "recoverable": False,
    }


def _minimal_contract(**overrides) -> dict:
    base = {
        "project_id": "proj_001",
        "project_name": "Test Project",
        "complexity_level": "simple",
        "model_used": "claude-haiku-4-5-20251001",
        "modules": [_module()],
        "extension_points": [
            _extension_point("ext_01"),
            _extension_point("ext_02"),
            _extension_point("ext_03"),
        ],
        "error_types": [
            _error_type("NotFoundError", "NOT_FOUND"),
            _error_type("ValidationError", "VALIDATION_ERROR"),
            _error_type("AuthError", "AUTH_FAILED"),
        ],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# MasterContract — valid cases
# ---------------------------------------------------------------------------

def test_minimal_contract_is_valid():
    contract = MasterContract(**_minimal_contract())
    assert contract.project_id == "proj_001"
    assert contract.version == "1.0.0"
    assert len(contract.modules) == 1


def test_contract_generated_at_is_set():
    contract = MasterContract(**_minimal_contract())
    assert contract.generated_at  # non-empty timestamp


def test_contract_accepts_optional_fields():
    data = _minimal_contract()
    data["data_types"] = [
        {
            "name": "UserProfile",
            "kind": "object",
            "fields": {"id": "str", "email": "str"},
            "description": "Represents a user's profile data in the system",
            "used_by_modules": ["user_service"],
        }
    ]
    data["constants"] = [
        {
            "name": "MAX_RETRY_COUNT",
            "value": "3",
            "type": "int",
            "description": "Maximum number of retry attempts",
        }
    ]
    contract = MasterContract(**data)
    assert len(contract.data_types) == 1
    assert len(contract.constants) == 1


# ---------------------------------------------------------------------------
# MasterContract — invalid cases (schema validation)
# ---------------------------------------------------------------------------

def test_contract_requires_at_least_one_module():
    with pytest.raises(ValidationError):
        MasterContract(**_minimal_contract(modules=[]))


def test_contract_requires_at_least_three_extension_points():
    with pytest.raises(ValidationError):
        MasterContract(**_minimal_contract(extension_points=[_extension_point()]))


def test_contract_requires_at_least_three_error_types():
    with pytest.raises(ValidationError):
        MasterContract(**_minimal_contract(error_types=[_error_type()]))


def test_contract_rejects_invalid_complexity_level():
    with pytest.raises(ValidationError):
        MasterContract(**_minimal_contract(complexity_level="extreme"))


# ---------------------------------------------------------------------------
# Module validation
# ---------------------------------------------------------------------------

def test_module_id_must_be_snake_case():
    with pytest.raises(ValidationError):
        Module(**_module(id="UserService"))  # PascalCase not allowed


def test_module_id_must_be_lowercase():
    with pytest.raises(ValidationError):
        Module(**_module(id="USER_SERVICE"))


def test_module_id_allows_underscores():
    m = Module(**_module(id="user_service_v2"))
    assert m.id == "user_service_v2"


def test_module_requires_at_least_one_interface():
    with pytest.raises(ValidationError):
        Module(**_module(interfaces=[]))


def test_module_requires_at_least_one_goal_id():
    with pytest.raises(ValidationError):
        Module(**_module(goal_ids=[]))


def test_module_layer_must_be_valid():
    with pytest.raises(ValidationError):
        Module(**_module(layer="business"))  # not in Literal


def test_module_layer_valid_values():
    for layer in ("domain", "application", "infrastructure", "presentation"):
        m = Module(**_module(layer=layer))
        assert m.layer == layer


# ---------------------------------------------------------------------------
# Interface validation
# ---------------------------------------------------------------------------

def test_interface_requires_at_least_one_method():
    with pytest.raises(ValidationError):
        Interface(**_interface(methods=[]))


# ---------------------------------------------------------------------------
# InterfaceMethod validation
# ---------------------------------------------------------------------------

def test_method_description_too_short_raises():
    with pytest.raises(ValidationError):
        InterfaceMethod(**_method(description="Short"))


def test_method_accepts_async_flag():
    m = InterfaceMethod(**_method(is_async=True))
    assert m.is_async is True


# ---------------------------------------------------------------------------
# EventChannel validation
# ---------------------------------------------------------------------------

def test_event_channel_requires_dotted_name():
    with pytest.raises(ValidationError):
        EventChannel(
            name="usercreated",  # missing dot
            payload_schema="UserCreatedEvent",
            description="User was created",
        )


def test_event_channel_valid_dotted_name():
    ec = EventChannel(
        name="user.created",
        payload_schema="UserCreatedEvent",
        description="Fired when a new user registers",
    )
    assert ec.name == "user.created"


# ---------------------------------------------------------------------------
# DataType validation
# ---------------------------------------------------------------------------

def test_data_type_description_too_short_raises():
    with pytest.raises(ValidationError):
        DataType(name="User", kind="object", description="Short")


def test_data_type_kind_must_be_valid():
    with pytest.raises(ValidationError):
        DataType(name="User", kind="class", description="A user in the system model here")


# ---------------------------------------------------------------------------
# ExtensionPoint validation
# ---------------------------------------------------------------------------

def test_extension_point_type_must_be_valid():
    with pytest.raises(ValidationError):
        ExtensionPoint(
            id="ext_01",
            type="unknown_type",
            location="pipeline",
            contract="implement process()",
            description="test",
            example_use_case="test",
        )


# ---------------------------------------------------------------------------
# ErrorType validation
# ---------------------------------------------------------------------------

def test_error_type_http_status_must_be_4xx_or_5xx():
    with pytest.raises(ValidationError):
        ErrorType(
            name="SomeError",
            code="SOME_ERROR",
            message_template="Something went wrong",
            recoverable=False,
            http_status=200,  # invalid
        )


def test_error_type_valid_http_status():
    e = ErrorType(
        name="SomeError",
        code="SOME_ERROR",
        message_template="Something went wrong for {reason}",
        recoverable=True,
        http_status=404,
    )
    assert e.http_status == 404


# ---------------------------------------------------------------------------
# model_dump_json round-trip
# ---------------------------------------------------------------------------

def test_contract_serializes_to_json():
    contract = MasterContract(**_minimal_contract())
    json_str = contract.model_dump_json()
    assert "proj_001" in json_str
    assert "user_service" in json_str


def test_contract_round_trips_through_json():
    original = MasterContract(**_minimal_contract())
    json_str = original.model_dump_json()
    restored = MasterContract.model_validate_json(json_str)
    assert restored.project_id == original.project_id
    assert restored.modules[0].id == original.modules[0].id
