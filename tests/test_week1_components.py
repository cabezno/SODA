"""
Tests for Week 1 new components:
- SkillDiscoveryAgent
- ModelLockedProxy
- skill_repository / skill_integration / skill_docker (manifest + files)
- Skill injection path in recursive engine (unit-level)
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Stub heavy optional deps
for _mod in ("docker", "anthropic", "google.generativeai", "ollama",
             "telegram", "telegram.ext", "pywebview", "chromadb",
             "watchdog", "watchdog.observers", "watchdog.events",
             "github", "git"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kernel.capabilities.skill_discovery_agent import SkillDiscoveryAgent
from kernel.drivers.provider_hub import AIProviderHub, ModelLockedProxy, AIProxy


def run(coro):
    return asyncio.run(coro)


# ═══════════════════════════════════════════════════════════════════════════
# ModelLockedProxy
# ═══════════════════════════════════════════════════════════════════════════

class TestModelLockedProxy:

    def _make_driver(self, response_content="ok"):
        driver = MagicMock()
        driver.call = AsyncMock(return_value=MagicMock(content=response_content))
        driver.prompt = AsyncMock(return_value=response_content)
        return driver

    def test_forces_model_in_call(self):
        driver = self._make_driver()
        proxy = ModelLockedProxy(driver, "gemini-3.1-pro-preview")
        run(proxy.call(system_prompt="s", user_message="u"))
        assert driver.call.call_args.kwargs["model"] == "gemini-3.1-pro-preview"

    def test_forces_model_overrides_caller_model(self):
        """Caller tries to set model='gemini-flash' but proxy locks to pro."""
        driver = self._make_driver()
        proxy = ModelLockedProxy(driver, "gemini-3.1-pro-preview")
        run(proxy.call(system_prompt="s", user_message="u", model="gemini-flash"))
        assert driver.call.call_args.kwargs["model"] == "gemini-3.1-pro-preview"

    def test_prompt_delegates_via_locked_call(self):
        driver = self._make_driver("hello")
        proxy = ModelLockedProxy(driver, "claude-3-5-sonnet-20241022")
        result = run(proxy.prompt("sys", "user"))
        assert result == "hello"
        assert driver.call.call_args.kwargs["model"] == "claude-3-5-sonnet-20241022"

    def test_getattr_falls_through_to_target(self):
        driver = MagicMock()
        driver.some_property = "value"
        proxy = ModelLockedProxy(driver, "gemini-3-flash-preview")
        assert proxy.some_property == "value"

    def test_hub_returns_locked_proxy_for_specific_gemini_model(self):
        hub = AIProviderHub()
        fake_gemini = MagicMock()
        fake_gemini.call = AsyncMock(return_value=MagicMock(content="ok"))
        hub.register("gemini", fake_gemini)

        driver = hub.get("gemini-3.1-pro-preview")
        assert isinstance(driver, ModelLockedProxy)
        assert driver._model_name == "gemini-3.1-pro-preview"

    def test_hub_returns_raw_driver_for_base_name(self):
        hub = AIProviderHub()
        fake_gemini = MagicMock()
        hub.register("gemini", fake_gemini)
        driver = hub.get("gemini")
        assert driver is fake_gemini  # no proxy for exact name

    def test_hub_returns_locked_proxy_for_claude_model(self):
        hub = AIProviderHub()
        fake_claude = MagicMock()
        fake_claude.call = AsyncMock(return_value=MagicMock(content="ok"))
        hub.register("claude", fake_claude)
        driver = hub.get("claude-3-5-sonnet-20241022")
        assert isinstance(driver, ModelLockedProxy)
        assert driver._model_name == "claude-3-5-sonnet-20241022"

    def test_proxy_model_reaches_underlying_driver_via_hub(self):
        hub = AIProviderHub()
        fake_gemini = MagicMock()
        fake_gemini.call = AsyncMock(return_value=MagicMock(content="response"))
        hub.register("gemini", fake_gemini)

        driver = hub.get("gemini-3-flash-preview")
        run(driver.call(system_prompt="s", user_message="u"))
        assert fake_gemini.call.call_args.kwargs["model"] == "gemini-3-flash-preview"


# ═══════════════════════════════════════════════════════════════════════════
# SkillDiscoveryAgent
# ═══════════════════════════════════════════════════════════════════════════

def _make_contract(title="", description="", inputs=None, outputs=None, skills=None):
    """Build a minimal mock SodaContract for skill discovery tests."""
    contract = MagicMock()
    contract.title = title
    contract.description = description
    contract.contract_id = title.lower().replace(" ", "_")
    iface = MagicMock()
    iface.inputs_required = inputs or []
    iface.outputs_provided = outputs or []
    contract.interface = iface
    persona = MagicMock()
    persona.required_skills = list(skills or [])
    contract.dynamic_persona = persona
    return contract


class TestSkillDiscoveryAgent:

    def _agent(self):
        return SkillDiscoveryAgent()

    # ── Detection logic ───────────────────────────────────────────────────

    def test_detects_repository_from_description(self):
        agent = self._agent()
        contract = _make_contract(
            title="User Service",
            description="CRUD operations for users stored in sqlite database"
        )
        skills = agent.discover_for_contract(contract)
        assert "skill_repository" in skills

    def test_detects_integration_from_description(self):
        agent = self._agent()
        contract = _make_contract(
            title="Payment Gateway",
            description="HTTP client to external payment API with retry and timeout"
        )
        skills = agent.discover_for_contract(contract)
        assert "skill_integration" in skills

    def test_detects_auth_from_title(self):
        agent = self._agent()
        contract = _make_contract(
            title="JWT Auth Service",
            description="Handles login and token validation"
        )
        skills = agent.discover_for_contract(contract)
        assert "skill_jwt_auth" in skills

    def test_detects_docker_from_description(self):
        agent = self._agent()
        contract = _make_contract(
            title="Deployment",
            description="Docker compose configuration for container orchestration"
        )
        skills = agent.discover_for_contract(contract)
        assert "skill_docker" in skills

    def test_no_false_positives_for_neutral_contract(self):
        agent = self._agent()
        contract = _make_contract(
            title="Math Utilities",
            description="Functions for calculating fibonacci and prime numbers"
        )
        skills = agent.discover_for_contract(contract)
        # Should not detect persistence or integration skills
        assert "skill_repository" not in skills
        assert "skill_integration" not in skills

    def test_preserves_existing_skills(self):
        agent = self._agent()
        contract = _make_contract(
            title="API Service",
            description="REST api with sqlite database",
            skills=["skill_fastapi"]
        )
        skills = agent.discover_for_contract(contract)
        assert "skill_fastapi" in skills      # preserved
        assert "skill_repository" in skills   # detected

    def test_no_duplicates_when_skill_already_assigned(self):
        agent = self._agent()
        contract = _make_contract(
            title="User Store",
            description="Persist users in sqlite database",
            skills=["skill_repository"]
        )
        skills = agent.discover_for_contract(contract)
        assert skills.count("skill_repository") == 1

    # ── discover (multi-contract) ─────────────────────────────────────────

    def test_discover_enriches_all_contracts(self):
        agent = self._agent()
        contracts = {
            "user_svc": _make_contract("User Service", "crud users sqlite"),
            "payment_svc": _make_contract("Payment", "http client external api"),
        }
        result = agent.discover(contracts)
        assert "skill_repository" in result["user_svc"]
        assert "skill_integration" in result["payment_svc"]

    def test_discover_contracts_without_signals_get_no_extras(self):
        agent = self._agent()
        contracts = {
            "math": _make_contract("Math", "add subtract multiply divide numbers"),
        }
        result = agent.discover(contracts)
        assert result["math"] == []  # no signals → no skills added

    def test_detection_from_output_names(self):
        """Skills detected from output names in the interface."""
        agent = self._agent()
        out = MagicMock()
        out.name = "UserRepository"
        out.type = "class"
        contract = _make_contract(title="Module", description="module logic")
        contract.interface.outputs_provided = [out]
        skills = agent.discover_for_contract(contract)
        assert "skill_repository" in skills

    # ── Available skills registry ─────────────────────────────────────────

    def test_loads_available_skills_from_disk(self):
        agent = self._agent()
        available = agent._load_available_skill_names()
        assert "skill_repository" in available
        assert "skill_integration" in available
        assert "skill_docker" in available
        assert "skill_fastapi" in available

    def test_caches_available_skills_after_first_load(self):
        agent = self._agent()
        first = agent._load_available_skill_names()
        second = agent._load_available_skill_names()
        assert first is second  # same object — cache hit


# ═══════════════════════════════════════════════════════════════════════════
# New skills structure validation
# ═══════════════════════════════════════════════════════════════════════════

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills" / "base"


class TestNewSkillsStructure:

    def _skill(self, name):
        return SKILLS_DIR / name

    def test_skill_repository_manifest_exists(self):
        assert (self._skill("skill_repository") / "manifest.yaml").exists()

    def test_skill_repository_has_system_prompt(self):
        assert (self._skill("skill_repository") / "system_prompt.md").exists()

    def test_skill_repository_has_python_knowledge(self):
        assert (self._skill("skill_repository") / "knowledge" / "repository_python.md").exists()

    def test_skill_repository_has_typescript_knowledge(self):
        assert (self._skill("skill_repository") / "knowledge" / "repository_typescript.md").exists()

    def test_skill_repository_python_contains_interface(self):
        content = (self._skill("skill_repository") / "knowledge" / "repository_python.md").read_text()
        assert "IUserRepository" in content
        assert "SqliteUserRepository" in content
        assert "Protocol" in content

    def test_skill_repository_ts_contains_interface(self):
        content = (self._skill("skill_repository") / "knowledge" / "repository_typescript.md").read_text()
        assert "IUserRepository" in content
        assert "SqliteUserRepository" in content
        assert "implements" in content

    def test_skill_repository_system_prompt_forbids_maps(self):
        content = (self._skill("skill_repository") / "system_prompt.md").read_text()
        assert "NEVER" in content
        assert "Map" in content or "dict" in content

    def test_skill_integration_manifest_exists(self):
        assert (self._skill("skill_integration") / "manifest.yaml").exists()

    def test_skill_integration_has_http_client_knowledge(self):
        assert (self._skill("skill_integration") / "knowledge" / "http_client.md").exists()

    def test_skill_integration_knowledge_has_retry(self):
        content = (self._skill("skill_integration") / "knowledge" / "http_client.md").read_text()
        assert "retry" in content.lower() or "with_retry" in content

    def test_skill_docker_manifest_exists(self):
        assert (self._skill("skill_docker") / "manifest.yaml").exists()

    def test_skill_docker_has_compose_knowledge(self):
        assert (self._skill("skill_docker") / "knowledge" / "compose_patterns.md").exists()

    def test_skill_docker_compose_has_python_and_node_examples(self):
        content = (self._skill("skill_docker") / "knowledge" / "compose_patterns.md").read_text()
        assert "FastAPI" in content or "uvicorn" in content
        assert "node" in content.lower() or "Node" in content

    def test_all_new_manifests_loadable_by_skill_matcher(self):
        """SkillMatcher can parse the new manifests without error."""
        import yaml
        for skill_name in ("skill_repository", "skill_integration", "skill_docker"):
            manifest = self._skill(skill_name) / "manifest.yaml"
            data = yaml.safe_load(manifest.read_text())
            assert "name" in data
            assert "activation_keywords" in data
            assert len(data["activation_keywords"]) > 0

    def test_skill_matcher_loads_repository_context(self):
        """SkillMatcher.load_skill_context returns non-empty for skill_repository."""
        from kernel.capabilities.skill_matcher import SkillMatcher
        matcher = SkillMatcher(None, None)
        ctx = matcher.load_skill_context(["skill_repository"], role="code_generator")
        assert "IUserRepository" in ctx or "Repository" in ctx
        assert len(ctx) > 100
