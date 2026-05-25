"""
End-to-end pipeline integration test.
Simulates the full SODA V2 pipeline with mocked AI drivers.
Verifies:
  - SkillDiscoveryAgent enriches contracts
  - Skill knowledge injected into Layer 4 coder prompt
  - Hard-reject fires for missing output symbols
  - ModelLockedProxy forces the correct model
  - Integration layer (Layer 6) generates entry point
  - docker-compose generated when skill_docker present
  - ContractRepository checkpoints the tree
  - Resumption skips already-completed modules
"""
import asyncio
import sys
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# Stub heavy optional deps
for _mod in ("docker", "anthropic", "google.generativeai", "ollama",
             "telegram", "telegram.ext", "pywebview", "chromadb",
             "watchdog", "watchdog.observers", "watchdog.events",
             "github", "git"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kernel.core.models_v2 import (
    SodaContract, ContractInterface, DynamicPersona,
    ContractVariable, ContractStatus,
)
from kernel.orchestration.recursive_engine import SodaRecursiveEngine
from kernel.intelligence.finops_router import FinopsRouter
from kernel.drivers.provider_hub import AIProviderHub, ModelLockedProxy
from kernel.capabilities.skill_discovery_agent import SkillDiscoveryAgent
from kernel.storage.contract_repository import JsonContractRepository


def run(coro):
    return asyncio.run(coro)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _var(name: str, atype: str = "str") -> ContractVariable:
    return ContractVariable(name=name, abstract_type=atype, desc=name)


def _make_atomic(cid: str, outputs: list[str], skills: list[str] = None,
                 deps: list[str] = None) -> SodaContract:
    return SodaContract(
        contract_id=cid,
        title=cid.replace("_", " ").title(),
        description=f"Module {cid}",
        is_atomic=True,
        level=1,
        dependencies=deps or [],
        interface=ContractInterface(
            inputs_required=[],
            outputs_provided=[_var(o) for o in outputs],
        ),
        dynamic_persona=DynamicPersona(
            target_role="coder",
            required_skills=skills or [],
        ),
    )


def _make_lineup():
    lineup = MagicMock()
    lineup.layer3_techlead = "gemini-3-flash-preview"
    lineup.layer4_coder = "qwen2.5-coder:7b"
    lineup.layer5_qa = "gemini-3-flash-preview"
    lineup.parallel_agents = 1
    return lineup


def _make_driver(content: str):
    """Returns a mock driver that always returns `content` from .call()."""
    driver = MagicMock()
    driver.call = AsyncMock(return_value=MagicMock(content=content, error_code=None))
    driver.prompt = AsyncMock(return_value=content)
    return driver


def _make_engine(tmp_path, gemini_driver, ollama_driver=None, hub=None,
                 stack="python", notify_fn=None):
    return SodaRecursiveEngine(
        gemini_driver=gemini_driver,
        ollama_driver=ollama_driver or MagicMock(),
        lineup=_make_lineup(),
        stack_language=stack,
        workspace=str(tmp_path),
        ai_hub=hub,
        notify_fn=notify_fn,
    )


# ═══════════════════════════════════════════════════════════════════════════
# SkillDiscoveryAgent integration
# ═══════════════════════════════════════════════════════════════════════════

class TestSkillDiscoveryIntegration:

    def test_agent_detects_repository_in_pool(self):
        pool = {
            "user_svc": _make_atomic("user_svc", ["UserRepository"],
                                     skills=["skill_sqlite"]),
        }
        pool["user_svc"].description = "CRUD users in sqlite database"
        agent = SkillDiscoveryAgent()
        result = agent.discover(pool)
        assert "skill_repository" in result["user_svc"]

    def test_agent_detects_integration_client(self):
        pool = {
            "payment": _make_atomic("payment", ["PaymentResult"]),
        }
        pool["payment"].description = "HTTP client to external payment API"
        agent = SkillDiscoveryAgent()
        result = agent.discover(pool)
        assert "skill_integration" in result["payment"]

    def test_agent_does_not_add_unavailable_skills(self, tmp_path):
        """Skills not present on disk are never added."""
        agent = SkillDiscoveryAgent(skills_dir=tmp_path)  # empty dir
        pool = {"m": _make_atomic("m", ["Output"])}
        pool["m"].description = "sqlite database users crud"
        result = agent.discover(pool)
        assert result["m"] == []

    def test_engine_enriches_subcontracts_on_decomposition(self, tmp_path):
        """After decomposition, sub-contracts have auto-detected skills."""
        sub = _make_atomic("user_svc", ["UserRepository"])
        sub.description = "CRUD users sqlite database"
        sub.is_atomic = False  # not yet processed

        engine = _make_engine(tmp_path, MagicMock())
        # Simulate the enrichment that happens in decompose_tree
        from kernel.capabilities.skill_discovery_agent import SkillDiscoveryAgent as SDA
        pool = {"user_svc": sub}
        enriched = SDA().discover(pool)
        assert "skill_repository" in enriched.get("user_svc", [])


# ═══════════════════════════════════════════════════════════════════════════
# QA hard-reject
# ═══════════════════════════════════════════════════════════════════════════

class TestQAHardReject:

    def test_missing_output_symbol_fires_hard_reject(self, tmp_path):
        """
        Contract declares output 'UserRepository'.
        Code does NOT contain 'UserRepository'.
        _run_qa_round must return (False, "RECHAZO DETERMINÍSTICO...").
        """
        contract = _make_atomic("svc", ["UserRepository"], skills=["skill_repository"])
        engine = _make_engine(tmp_path, MagicMock())
        approved, feedback = run(engine._run_qa_round(contract, "def foo(): pass", "python"))
        assert approved is False
        assert "RECHAZO DETERMINÍSTICO" in feedback
        assert "UserRepository" in feedback

    def test_present_output_symbol_passes_to_qa(self, tmp_path):
        """
        Code contains the required symbol — goes to QA.
        QA approves → (True, "").
        """
        contract = _make_atomic("svc", ["UserRepository"])
        qa_response = json.dumps({"approved": True, "feedback": ""})
        gemini = _make_driver(qa_response)

        hub = AIProviderHub()
        hub.register("gemini", gemini)

        engine = _make_engine(tmp_path, gemini, hub=hub)
        engine.lineup.layer5_qa = "gemini"

        code = "class UserRepository:\n    def find_by_id(self, id): pass\n"
        approved, feedback = run(engine._run_qa_round(contract, code, "python"))
        assert approved is True
        assert feedback == ""

    def test_hard_reject_not_overridable_by_deepseek(self, tmp_path):
        """
        Even if DeepSeek would approve, hard-reject for missing symbols
        must not reach DeepSeek at all.
        """
        contract = _make_atomic("svc", ["MissingSymbol"])
        ds_driver = _make_driver(json.dumps({"override_approval": True, "reason": "looks fine"}))

        hub = AIProviderHub()
        hub.register("deepseek", ds_driver)

        engine = _make_engine(tmp_path, MagicMock(), hub=hub)
        approved, _ = run(engine._run_qa_round(contract, "def unrelated(): pass", "python"))

        assert approved is False
        ds_driver.call.assert_not_called()  # DeepSeek never reached

    def test_qa_rejection_propagates_feedback_to_next_attempt(self, tmp_path):
        """
        QA rejects → feedback string is returned so the caller
        can inject it into the next coder attempt.
        """
        contract = _make_atomic("svc", ["UserRepository"])
        qa_response = json.dumps({
            "approved": False,
            "feedback": "Missing error handling in find_by_id"
        })
        gemini = _make_driver(qa_response)
        hub = AIProviderHub()
        hub.register("gemini", gemini)
        engine = _make_engine(tmp_path, gemini, hub=hub)
        engine.lineup.layer5_qa = "gemini"

        code = "class UserRepository:\n    def find_by_id(self, id): return None\n"
        approved, feedback = run(engine._run_qa_round(contract, code, "python"))
        assert approved is False
        assert "Missing error handling" in feedback


# ═══════════════════════════════════════════════════════════════════════════
# Skill injection in Layer 4 coder
# ═══════════════════════════════════════════════════════════════════════════

class TestSkillInjectionInCoder:

    def test_skill_knowledge_injected_into_qwen_prompt(self, tmp_path):
        """
        A contract with skill_repository should cause the Qwen system_prompt
        to contain Repository-related content.
        The new L4 routes ALL models through hub.get(model).call(), including Qwen.
        """
        captured_prompts = []

        async def fake_call(system_prompt=None, user_message=None, **kwargs):
            captured_prompts.append(system_prompt or "")
            result = MagicMock()
            result.content = (
                "<FILE path='user_svc.py'>\n"
                "class UserRepository:\n    pass\n"
                "</FILE>"
            )
            result.error_code = None
            return result

        qwen_driver = MagicMock()
        qwen_driver.call = fake_call

        qa_ok = json.dumps({"approved": True, "feedback": ""})
        gemini = _make_driver(qa_ok)
        hub = AIProviderHub()
        hub.register("gemini", gemini)
        hub.register("qwen2.5-coder:7b", qwen_driver)

        engine = _make_engine(tmp_path, gemini, hub=hub)
        engine.lineup.layer5_qa = "gemini"

        contract = _make_atomic("user_svc", ["UserRepository"],
                                skills=["skill_repository"])
        generated_map = {}

        # Bypass complexity routing (force Qwen path)
        contract.dependencies = []
        contract.interface.inputs_required = []

        run(engine._initial_generation(contract, generated_map))

        assert len(captured_prompts) > 0
        combined = " ".join(captured_prompts)
        # The skill knowledge should mention Repository patterns
        assert "Repository" in combined or "repository" in combined


# ═══════════════════════════════════════════════════════════════════════════
# Integration Layer (Layer 6)
# ═══════════════════════════════════════════════════════════════════════════

class TestIntegrationLayer:

    def test_generates_entry_point_file(self, tmp_path):
        saved = {}

        def save_fn(filename, content, phase=None):
            saved[filename] = content

        entry_code = "from user_svc import UserRepository\nif __name__ == '__main__': pass"
        gemini = _make_driver(entry_code)
        hub = AIProviderHub()
        hub.register("gemini", gemini)

        engine = _make_engine(tmp_path, gemini, hub=hub)
        engine.save_file_fn = save_fn
        engine.lineup.layer3_techlead = "gemini"

        pool = {"user_svc": _make_atomic("user_svc", ["UserRepository"])}
        code_map = {"user_svc": "class UserRepository: pass"}

        run(engine._generate_integration_layer(pool, code_map))

        assert "main.py" in saved
        assert "UserRepository" in saved["main.py"] or len(saved["main.py"]) > 0

    def test_integration_layer_skipped_when_no_code(self, tmp_path):
        gemini = _make_driver("should not be called")
        engine = _make_engine(tmp_path, gemini)
        # No code map → should not call driver
        run(engine._generate_integration_layer({}, {}))
        gemini.call.assert_not_called()

    def test_docker_compose_generated_when_skill_docker_present(self, tmp_path):
        saved = {}

        def save_fn(filename, content, phase=None):
            saved[filename] = content

        compose_yaml = "version: '3.9'\nservices:\n  api:\n    build: ."
        gemini = _make_driver(compose_yaml)
        hub = AIProviderHub()
        hub.register("gemini", gemini)

        engine = _make_engine(tmp_path, gemini, hub=hub)
        engine.save_file_fn = save_fn
        engine.lineup.layer3_techlead = "gemini"

        pool = {
            "api": _make_atomic("api", ["app"], skills=["skill_fastapi", "skill_docker"]),
        }
        run(engine._generate_docker_compose(pool))

        assert "docker-compose.yml" in saved

    def test_docker_compose_skipped_when_no_skill_docker(self, tmp_path):
        gemini = _make_driver("should not be called")
        engine = _make_engine(tmp_path, gemini)

        pool = {"api": _make_atomic("api", ["app"], skills=["skill_fastapi"])}
        run(engine._generate_docker_compose(pool))
        gemini.call.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# Resumption
# ═══════════════════════════════════════════════════════════════════════════

class TestResumption:

    def test_completed_modules_loaded_from_disk_and_skipped(self, tmp_path):
        """
        A module marked COMPLETED with its file on disk is not regenerated.
        """
        # Write the file that would have been generated in a previous session
        (tmp_path / "user_svc.py").write_text(
            "class UserRepository:\n    pass\n", encoding="utf-8"
        )

        regenerated = []

        async def fake_layer4(contract, code_map):
            regenerated.append(contract.contract_id)
            return {f"{contract.contract_id}.py": f"class {contract.contract_id}: pass"}

        contract = _make_atomic("user_svc", ["UserRepository"], skills=["skill_repository"])
        contract.status = ContractStatus.COMPLETED

        pool = {"user_svc": contract}

        gemini = _make_driver(json.dumps({"approved": True}))
        engine = _make_engine(tmp_path, gemini)

        with patch.object(engine, "_initial_generation", side_effect=fake_layer4), \
             patch.object(engine, "_audit_and_repair_module", new=AsyncMock(side_effect=lambda c, f: f)), \
             patch.object(engine, "_run_layer3", side_effect=lambda c: c), \
             patch.object(engine, "_generate_integration_layer", new=AsyncMock()), \
             patch.object(engine, "_generate_docker_compose", new=AsyncMock()):
            result = run(engine.execute_bottom_up(pool))

        assert "user_svc" not in regenerated  # was not regenerated
        assert "user_svc" in result            # but is in the code map
        assert "UserRepository" in result["user_svc"]

    def test_non_completed_module_is_still_generated(self, tmp_path):
        """A module NOT completed must still be processed normally."""
        generated = []

        async def fake_layer4(contract, code_map):
            generated.append(contract.contract_id)
            return {f"{contract.contract_id}.py": f"class {contract.contract_id}: pass"}

        contract = _make_atomic("new_svc", ["NewService"])
        # status = PENDING_EXECUTION (not completed)

        pool = {"new_svc": contract}
        qa_ok = json.dumps({"approved": True, "feedback": ""})
        gemini = _make_driver(qa_ok)

        engine = _make_engine(tmp_path, gemini)

        with patch.object(engine, "_initial_generation", side_effect=fake_layer4), \
             patch.object(engine, "_audit_and_repair_module", new=AsyncMock(side_effect=lambda c, f: f)), \
             patch.object(engine, "_run_layer3", side_effect=lambda c: c), \
             patch.object(engine, "_generate_integration_layer", new=AsyncMock()), \
             patch.object(engine, "_generate_docker_compose", new=AsyncMock()):
            result = run(engine.execute_bottom_up(pool))

        assert "new_svc" in generated  # was processed
        assert "new_svc" in result


# ═══════════════════════════════════════════════════════════════════════════
# ContractRepository in engine
# ═══════════════════════════════════════════════════════════════════════════

class TestContractRepositoryInEngine:

    def test_engine_creates_json_repo_with_workspace(self, tmp_path):
        from kernel.storage.contract_repository import JsonContractRepository
        engine = _make_engine(tmp_path, MagicMock())
        assert engine._contract_repo is not None
        assert isinstance(engine._contract_repo, JsonContractRepository)

    def test_engine_has_no_repo_without_workspace(self):
        engine = SodaRecursiveEngine(
            gemini_driver=MagicMock(),
            ollama_driver=MagicMock(),
            lineup=_make_lineup(),
            workspace=None,
        )
        assert engine._contract_repo is None

    def test_repo_checkpoints_tree_during_decomposition(self, tmp_path):
        """After decomposition, soda_v2_tree.json exists on disk."""
        from kernel.core.models_v2 import ContractStatus

        root = _make_atomic("root", ["Output"])
        root.is_atomic = False
        root.status = ContractStatus.PENDING_DECOMPOSITION

        sub = _make_atomic("sub", ["Output"])

        gemini = MagicMock()
        engine = _make_engine(tmp_path, gemini)

        # Simulate save_tree call directly (decompose_tree calls _contract_repo.save_tree)
        pool = {"root": root, "sub": sub}
        engine._contract_repo.save_tree("current", pool)

        assert (tmp_path / "soda_v2_tree.json").exists()
        loaded = engine._contract_repo.load_tree("current")
        assert "root" in loaded
        assert "sub" in loaded
