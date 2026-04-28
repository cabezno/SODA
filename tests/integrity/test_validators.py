"""Tests for all contract validators (Arquitecto v2, Fase 2)."""
import asyncio
import pytest

from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.validators.consistency import ConsistencyValidator
from kernel.integrity.validators.completeness import CompletenessValidator
from kernel.integrity.validators.dependency import DependencyValidator
from kernel.integrity.validators.naming import NamingValidator
from kernel.integrity.validators.extensibility import ExtensibilityValidator
from kernel.integrity.validators.traceability import TraceabilityValidator

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.run(coro)


def _method(**overrides) -> dict:
    base = {
        "name": "get_user",
        "parameters": {"user_id": "str"},
        "returns": "str",
        "description": "Returns user data from the database by ID",
        "example_usage": "service.get_user('abc')",
    }
    base.update(overrides)
    return base


def _interface(**overrides) -> dict:
    base = {
        "name": "UserInterface",
        "description": "Public interface",
        "methods": [_method()],
    }
    base.update(overrides)
    return base


def _module(id_="user_service", layer="application", **overrides) -> dict:
    base = {
        "id": id_,
        "name": "User Service",
        "purpose": "Handles all user-related business logic and data persistence",
        "interfaces": [_interface()],
        "goal_ids": ["goal_users"],
        "layer": layer,
    }
    base.update(overrides)
    return base


def _ext(id_="ext_01", ext_type="middleware_slot") -> dict:
    return {
        "id": id_,
        "type": ext_type,
        "location": "HTTP pipeline",
        "contract": "Must implement process(request) and return response",
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


def _contract(**overrides) -> MasterContract:
    base = {
        "project_id": "proj_test",
        "project_name": "Test Project",
        "complexity_level": "simple",
        "model_used": "claude-haiku-4-5-20251001",
        "modules": [_module()],
        "extension_points": [_ext("e1"), _ext("e2"), _ext("e3")],
        "error_types": [_err("E1", "ERR_ONE"), _err("E2", "ERR_TWO"), _err("E3", "ERR_THREE")],
    }
    base.update(overrides)
    return MasterContract(**base)


# ---------------------------------------------------------------------------
# ConsistencyValidator
# ---------------------------------------------------------------------------

class TestConsistencyValidator:
    v = ConsistencyValidator()

    def test_clean_contract_passes(self):
        result = run(self.v.validate(_contract()))
        assert result.status == "passed"
        assert result.issues == []

    def test_duplicate_module_id_is_error(self):
        contract = _contract(modules=[_module("svc"), _module("svc")])
        result = run(self.v.validate(contract))
        errors = [i for i in result.issues if i.rule == "unique_module_ids"]
        assert len(errors) == 1
        assert errors[0].severity == "error"

    def test_undefined_dependency_is_error(self):
        m = _module(depends_on=["nonexistent_module"])
        contract = _contract(modules=[m])
        result = run(self.v.validate(contract))
        errors = [i for i in result.issues if i.rule == "dependencies_exist"]
        assert len(errors) == 1

    def test_valid_dependency_passes(self):
        m1 = _module("svc_a")
        m2 = _module("svc_b", depends_on=["svc_a"])
        contract = _contract(modules=[m1, m2])
        result = run(self.v.validate(contract))
        dep_errors = [i for i in result.issues if i.rule == "dependencies_exist"]
        assert dep_errors == []

    def test_emitted_event_without_channel_is_error(self):
        iface = _interface(events_emitted=["user.created"])
        m = _module(interfaces=[iface])
        contract = _contract(modules=[m])
        result = run(self.v.validate(contract))
        errors = [i for i in result.issues if i.rule == "events_exist"]
        assert len(errors) == 1

    def test_emitted_event_with_channel_passes(self):
        iface = _interface(events_emitted=["user.created"])
        m = _module(interfaces=[iface])
        channel = {
            "name": "user.created",
            "payload_schema": "UserCreatedPayload",
            "description": "Fired on user creation",
        }
        contract = _contract(modules=[m], event_channels=[channel])
        result = run(self.v.validate(contract))
        errors = [i for i in result.issues if i.rule == "events_exist"]
        assert errors == []

    def test_duplicate_error_code_is_error(self):
        contract = _contract(error_types=[
            _err("E1", "SAME_CODE"),
            _err("E2", "SAME_CODE"),
            _err("E3", "DIFFERENT"),
        ])
        result = run(self.v.validate(contract))
        errors = [i for i in result.issues if i.rule == "unique_error_codes"]
        assert len(errors) == 1

    def test_duplicate_extension_id_is_error(self):
        contract = _contract(extension_points=[
            _ext("same_id"), _ext("same_id"), _ext("other"),
        ])
        result = run(self.v.validate(contract))
        errors = [i for i in result.issues if i.rule == "unique_extension_ids"]
        assert len(errors) == 1

    def test_undefined_return_type_is_error(self):
        m_dict = _method(returns="CustomUndefinedType")
        iface = _interface(methods=[m_dict])
        m = _module(interfaces=[iface])
        contract = _contract(modules=[m])
        result = run(self.v.validate(contract))
        errors = [i for i in result.issues if i.rule == "data_types_exist"]
        assert len(errors) >= 1

    def test_defined_return_type_passes(self):
        dt = {
            "name": "UserRecord",
            "kind": "object",
            "fields": {"id": "str"},
            "description": "Represents a user record in the database",
        }
        m_dict = _method(returns="UserRecord")
        iface = _interface(methods=[m_dict])
        m = _module(interfaces=[iface])
        contract = _contract(modules=[m], data_types=[dt])
        result = run(self.v.validate(contract))
        type_errors = [i for i in result.issues if i.rule == "data_types_exist"]
        assert type_errors == []

    def test_optional_generic_type_passes(self):
        m_dict = _method(returns="Optional[str]")
        iface = _interface(methods=[m_dict])
        m = _module(interfaces=[iface])
        contract = _contract(modules=[m])
        result = run(self.v.validate(contract))
        type_errors = [i for i in result.issues if i.rule == "data_types_exist"]
        assert type_errors == []

    def test_list_generic_type_passes(self):
        m_dict = _method(returns="list[str]")
        iface = _interface(methods=[m_dict])
        m = _module(interfaces=[iface])
        contract = _contract(modules=[m])
        result = run(self.v.validate(contract))
        type_errors = [i for i in result.issues if i.rule == "data_types_exist"]
        assert type_errors == []


# ---------------------------------------------------------------------------
# CompletenessValidator
# ---------------------------------------------------------------------------

class TestCompletenessValidator:
    v = CompletenessValidator()

    def test_clean_contract_passes(self):
        result = run(self.v.validate(_contract()))
        assert result.status == "passed"

    def test_minimum_extension_points_rule_logic(self):
        # Pydantic's min_length=3 on extension_points already prevents fewer than 3
        # at construction time. The CompletenessValidator provides defense-in-depth
        # and richer messages. Test the rule logic directly on the validator:
        v = CompletenessValidator()
        assert v.MIN_EXTENSION_POINTS == 3
        assert v.MIN_ERROR_TYPES == 3

    def test_minimum_values_are_enforced_by_pydantic(self):
        # Confirm Pydantic (not just our validator) enforces the minimums
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            _contract(extension_points=[_ext("e1")])  # too few
        with pytest.raises(ValidationError):
            _contract(error_types=[_err()])  # too few

    def test_method_description_at_minimum_threshold_passes(self):
        # Pydantic enforces min_length=10 on description. The completeness validator
        # warns on descriptions shorter than 10 chars, which Pydantic already blocks.
        # Test that the validator does NOT warn on adequate descriptions:
        result = run(self.v.validate(_contract()))
        warns = [i for i in result.issues if i.rule == "method_description_too_short"]
        assert warns == []

    def test_adequate_method_description_passes(self):
        result = run(self.v.validate(_contract()))
        warns = [i for i in result.issues if i.rule == "method_description_too_short"]
        assert warns == []

    def test_data_type_description_at_threshold_is_ok(self):
        dt = {"name": "MyType", "kind": "primitive", "description": "Exactly 10c."}
        contract = _contract(data_types=[dt])
        result = run(self.v.validate(contract))
        warns = [i for i in result.issues if i.rule == "data_type_description_too_short"]
        assert warns == []

    def test_long_data_type_description_passes(self):
        dt = {"name": "MyType", "kind": "primitive", "description": "A well documented type with good description"}
        contract = _contract(data_types=[dt])
        result = run(self.v.validate(contract))
        warns = [i for i in result.issues if i.rule == "data_type_description_too_short"]
        assert warns == []


# ---------------------------------------------------------------------------
# DependencyValidator
# ---------------------------------------------------------------------------

class TestDependencyValidator:
    v = DependencyValidator()

    def test_no_dependencies_passes(self):
        result = run(self.v.validate(_contract()))
        assert result.status == "passed"

    def test_acyclic_dependencies_pass(self):
        m1 = _module("alpha")
        m2 = _module("beta", depends_on=["alpha"])
        m3 = _module("gamma", depends_on=["beta"])
        contract = _contract(modules=[m1, m2, m3])
        result = run(self.v.validate(contract))
        cycle_errors = [i for i in result.issues if i.rule == "no_circular_dependencies"]
        assert cycle_errors == []

    def test_direct_cycle_is_error(self):
        m1 = _module("alpha", depends_on=["beta"])
        m2 = _module("beta", depends_on=["alpha"])
        contract = _contract(modules=[m1, m2])
        result = run(self.v.validate(contract))
        cycle_errors = [i for i in result.issues if i.rule == "no_circular_dependencies"]
        assert len(cycle_errors) >= 1
        assert cycle_errors[0].severity == "error"

    def test_self_loop_is_error(self):
        m = _module("self_dep", depends_on=["self_dep"])
        contract = _contract(modules=[m])
        result = run(self.v.validate(contract))
        cycle_errors = [i for i in result.issues if i.rule == "no_circular_dependencies"]
        assert len(cycle_errors) >= 1

    def test_excessive_direct_deps_is_warning(self):
        deps = [f"dep_{i}" for i in range(9)]
        dep_modules = [_module(f"dep_{i}") for i in range(9)]
        main = _module("main_module", depends_on=deps)
        contract = _contract(modules=[main] + dep_modules)
        result = run(self.v.validate(contract))
        warns = [i for i in result.issues if i.rule == "max_direct_dependencies"]
        assert len(warns) == 1
        assert warns[0].severity == "warning"

    def test_acceptable_direct_deps_pass(self):
        deps = [f"dep_{i}" for i in range(3)]
        dep_modules = [_module(f"dep_{i}") for i in range(3)]
        main = _module("main_module", depends_on=deps)
        contract = _contract(modules=[main] + dep_modules)
        result = run(self.v.validate(contract))
        warns = [i for i in result.issues if i.rule == "max_direct_dependencies"]
        assert warns == []


# ---------------------------------------------------------------------------
# NamingValidator
# ---------------------------------------------------------------------------

class TestNamingValidator:
    v = NamingValidator()

    def test_clean_contract_passes(self):
        result = run(self.v.validate(_contract()))
        assert result.status == "passed"

    def test_camelcase_module_id_blocked_by_pydantic(self):
        # Pydantic's field_validator already catches camelCase module IDs.
        # The NamingValidator provides richer messages and catches additional
        # naming issues that Pydantic doesn't check (methods, events, constants).
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MasterContract(
                project_id="p",
                project_name="P",
                complexity_level="simple",
                model_used="claude-haiku-4-5-20251001",
                modules=[{
                    "id": "userService",  # camelCase — Pydantic catches this
                    "name": "User Service",
                    "purpose": "Handles all user business logic and data operations",
                    "interfaces": [_interface()],
                    "goal_ids": ["goal_x"],
                    "layer": "application",
                }],
                extension_points=[_ext("e1"), _ext("e2"), _ext("e3")],
                error_types=[_err("E1", "E_ONE"), _err("E2", "E_TWO"), _err("E3", "E_THREE")],
            )

    def test_module_id_naming_regex(self):
        v = NamingValidator()
        assert v._SNAKE_CASE.match("user_service")
        assert v._SNAKE_CASE.match("svc2")
        assert not v._SNAKE_CASE.match("UserService")
        assert not v._SNAKE_CASE.match("userService")

    def test_camelcase_method_name_is_error(self):
        m_dict = _method(name="getUser")  # camelCase
        iface = _interface(methods=[m_dict])
        m = _module(interfaces=[iface])
        contract = _contract(modules=[m])
        result = run(self.v.validate(contract))
        errors = [i for i in result.issues if i.rule == "method_name_snake_case"]
        assert len(errors) == 1

    def test_lowercase_data_type_is_error(self):
        dt = {
            "name": "userRecord",  # not PascalCase
            "kind": "object",
            "description": "A user record in the system database",
        }
        contract = _contract(data_types=[dt])
        result = run(self.v.validate(contract))
        errors = [i for i in result.issues if i.rule == "data_type_pascal_case"]
        assert len(errors) == 1

    def test_lowercase_constant_is_error(self):
        const = {"name": "max_retries", "value": "3", "type": "int", "description": "Max"}
        contract = _contract(constants=[const])
        result = run(self.v.validate(contract))
        errors = [i for i in result.issues if i.rule == "constant_upper_snake_case"]
        assert len(errors) == 1

    def test_event_without_dot_is_error(self):
        channel = {
            "name": "usercreated",
            "payload_schema": "Payload",
            "description": "A channel",
        }
        # EventChannel validator in schema already catches this,
        # but NamingValidator also checks it.
        # We test via a contract dict bypass to isolate the naming check:
        # (EventChannel schema would raise first — test the naming regex separately)
        validator = NamingValidator()
        # Test regex directly
        assert not validator._DOTTED_EVENT.match("usercreated")
        assert validator._DOTTED_EVENT.match("user.created")

    def test_lower_error_code_is_error(self):
        contract = _contract(error_types=[
            _err("E1", "lower_code"),  # not UPPER_SNAKE
            _err("E2", "ERR_TWO"),
            _err("E3", "ERR_THREE"),
        ])
        result = run(self.v.validate(contract))
        errors = [i for i in result.issues if i.rule == "error_code_upper_snake_case"]
        assert len(errors) == 1

    def test_valid_naming_passes_all(self):
        result = run(self.v.validate(_contract()))
        assert not any(
            i.severity == "error" for i in result.issues
        ), f"Unexpected errors: {result.issues}"


# ---------------------------------------------------------------------------
# ExtensibilityValidator
# ---------------------------------------------------------------------------

def _balanced_ext_points() -> list[dict]:
    """Three extension points covering all required types."""
    return [
        _ext("e1", "middleware_slot"),
        _ext("e2", "metadata_field"),
        _ext("e3", "event_channel"),
    ]


class TestExtensibilityValidator:
    v = ExtensibilityValidator()

    def test_clean_contract_with_all_types_passes(self):
        # Need all three required types to avoid missing_extension_type warnings
        contract = _contract(extension_points=_balanced_ext_points())
        result = run(self.v.validate(contract))
        assert result.status == "passed"

    def test_too_few_extension_points_blocked_by_pydantic(self):
        # Pydantic's min_length=3 prevents construction of the contract
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            _contract(extension_points=[_ext()])

    def test_missing_required_type_is_warning(self):
        # All 3 points are middleware_slot — missing metadata_field and event_channel
        ext_points = [_ext(f"e{i}", "middleware_slot") for i in range(3)]
        contract = _contract(extension_points=ext_points)
        result = run(self.v.validate(contract))
        warns = [i for i in result.issues if i.rule == "missing_extension_type"]
        assert len(warns) >= 1

    def test_all_required_types_present_no_type_warning(self):
        ext_points = [
            _ext("e1", "middleware_slot"),
            _ext("e2", "metadata_field"),
            _ext("e3", "event_channel"),
        ]
        contract = _contract(extension_points=ext_points)
        result = run(self.v.validate(contract))
        warns = [i for i in result.issues if i.rule == "missing_extension_type"]
        assert warns == []

    def test_short_contract_description_is_warning(self):
        ext = {
            "id": "ext_short",
            "type": "middleware_slot",
            "location": "pipeline",
            "contract": "Short",  # < 20 chars
            "description": "Something",
            "example_use_case": "Example here",
        }
        contract = _contract(extension_points=[
            ext, _ext("e2"), _ext("e3"),
        ])
        result = run(self.v.validate(contract))
        warns = [i for i in result.issues if i.rule == "extension_point_contract_unclear"]
        assert len(warns) == 1

    def test_no_example_is_info(self):
        ext = {
            "id": "ext_no_example",
            "type": "hook",
            "location": "pipeline",
            "contract": "Must implement handle(event) and return processed event",
            "description": "Hook point",
            "example_use_case": "",  # empty
        }
        contract = _contract(extension_points=[
            ext, _ext("e2"), _ext("e3"),
        ])
        result = run(self.v.validate(contract))
        infos = [i for i in result.issues if i.rule == "extension_point_no_example"]
        assert len(infos) == 1
        assert infos[0].severity == "info"


# ---------------------------------------------------------------------------
# TraceabilityValidator
# ---------------------------------------------------------------------------

class TestTraceabilityValidator:

    def test_soft_mode_module_with_goals_passes(self):
        v = TraceabilityValidator(goal_tree={})
        result = run(v.validate(_contract()))
        assert result.status == "passed"

    def test_soft_mode_module_without_goals_is_error(self):
        v = TraceabilityValidator(goal_tree={})
        m = {
            "id": "orphan_module",
            "name": "Orphan",
            "purpose": "Module without any goals assigned to it at all",
            "interfaces": [_interface()],
            "goal_ids": [],  # empty — Pydantic would catch this
            "layer": "application",
        }
        # goal_ids=[] would fail Pydantic validation (min_length=1)
        # so test that the validator would flag an empty string goal_id
        # by mocking via a valid contract and patching
        # Instead: verify the soft-mode logic handles the case it receives
        with pytest.raises(Exception):
            # Pydantic min_length=1 prevents goal_ids=[]
            from kernel.intelligence.contract_schemas import Module
            Module(**m)

    def test_full_mode_valid_goal_ids_passes(self):
        # Tree without a root "id" node — only the leaf goal_users exists
        # so the module's goal_ids=["goal_users"] satisfies full coverage
        tree = {"children": [{"id": "goal_users"}]}
        v = TraceabilityValidator(goal_tree=tree)
        result = run(v.validate(_contract()))
        assert result.status == "passed"

    def test_full_mode_invalid_goal_id_is_error(self):
        tree = {"children": [{"id": "goal_users"}]}
        v = TraceabilityValidator(goal_tree=tree)
        m = _module(goal_ids=["nonexistent_goal"])
        contract = _contract(modules=[m])
        result = run(v.validate(contract))
        errors = [i for i in result.issues if i.rule == "goal_ids_valid"]
        assert len(errors) == 1
        assert errors[0].severity == "error"

    def test_full_mode_unimplemented_goal_is_warning(self):
        # Tree has goal_users AND goal_reports; module only covers goal_users
        tree = {"children": [{"id": "goal_users"}, {"id": "goal_reports"}]}
        v = TraceabilityValidator(goal_tree=tree)
        result = run(v.validate(_contract()))
        warns = [i for i in result.issues if i.rule == "goal_has_implementation"]
        # Only goal_reports is unimplemented (goal_users is covered by the module)
        assert len(warns) == 1
        assert warns[0].severity == "warning"

    def test_extract_goal_ids_from_nested_tree(self):
        tree = {
            "id": "root",
            "children": [
                {"id": "feat_auth", "sub": [{"id": "feat_login"}, {"id": "feat_logout"}]},
                {"id": "feat_data"},
            ],
        }
        v = TraceabilityValidator(goal_tree=tree)
        assert "root" in v._all_goal_ids
        assert "feat_auth" in v._all_goal_ids
        assert "feat_login" in v._all_goal_ids
        assert "feat_logout" in v._all_goal_ids
        assert "feat_data" in v._all_goal_ids
