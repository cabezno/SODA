"""
Unit tests for deterministic SODA V2 components — no API calls.
Run with: python -m pytest tests/test_unit_v2.py -v
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

import types
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Stub out heavy optional dependencies that may not be installed
for _mod in ("docker", "anthropic", "google.generativeai", "ollama",
             "telegram", "telegram.ext", "pywebview", "chromadb",
             "watchdog", "watchdog.observers", "watchdog.events",
             "github", "git"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from kernel.dependency_graph import DependencyGraph, ExecutionPlan
from kernel.code_generator import CodeGenerator, PYTHON_EXTENSIONS
from kernel.lineage.branching import BranchManager
from kernel.intelligence.context_health_monitor import ContextHealthMonitor
from kernel.orchestrator import SodaOrchestrator, Project, ProjectState
from kernel.project_validator import ProjectValidator
from kernel.drivers.provider_hub import AIProviderHub
from kernel.execution.project_runner import ProjectRunner, RuntimeSmoke
from kernel.projects.project_manager import ProjectManager
from kernel.projects.project_types import ProjectTypeRegistry
from kernel.capabilities.capability_packs import CapabilityPackRegistry
from kernel.capabilities.skill_manager import SkillManager
from kernel.capabilities.profile_manager import ProfileManager
from kernel.git_manager import GitManager
from kernel.integrity.goal_integrity_validator import GoalIntegrityValidator
from kernel.monitoring.usage_monitor import UsageMonitor
from kernel.monitoring.alert_manager import AlertManager
from kernel.execution.stack_detector import StackDetector
from kernel.execution.port_manager import PortManager
from kernel.external.web_researcher import WebResearchResult, WebResearcher
from kernel.external.system_actions import SystemActionsExecutor
from kernel.external.tool_registry import ExternalToolRegistry
from kernel.intelligence.reference_analyzer import ReferenceAnalyzer
from kernel.vision.vision_capturer import VisionCapturer
from kernel.vision.visual_inspector import VisualInspector
from kernel.orchestration.intensity_orchestrator import IntensityOrchestrator
from kernel.communication.project_chat import ProjectChat
from kernel.communication.telegram_gateway import TelegramGateway
from kernel.goals.goal_tree import GoalNode, GoalTree, build_file_goal_node
from kernel.goals.metadata_injector import MetadataInjector


# ---------------------------------------------------------------------------
# Metadata and Code Generation
# ---------------------------------------------------------------------------

class TestMetadataInjector:
    def test_ensure_metadata_adds_header_when_missing(self):
        injector = MetadataInjector()
        result = injector.ensure_metadata("print('ok')\n", "api__main")
        assert "# --- METADATA SODA ---" in result
        assert "# goal_id: api__main" in result
        assert "print('ok')" in result

    def test_ensure_metadata_preserves_existing_header(self):
        injector = MetadataInjector()
        content = (
            "# --- METADATA SODA ---\n"
            "# goal_id: api__main\n"
            "# goal_hash: abc123\n"
            "# --- FIN METADATA ---\n"
            "print('ok')\n"
        )
        result = injector.ensure_metadata(content, "api__main")
        assert result == content


class TestGoalTree:
    def test_from_architecture_creates_module_and_file_goals(self):
        architecture = {
            "modulos": [
                {
                    "nombre": "api",
                    "responsabilidad": "REST endpoints",
                    "dependencias": [],
                    "archivos_principales": ["api/main.py"],
                }
            ]
        }
        tree = GoalTree.from_architecture("proj_demo", "Build a todo API", architecture)
        assert tree.root_id == "proj_demo__root"
        assert tree.get_goal("module__api").type == "category"
        assert tree.get_goal("api__api_main_py").implemented_by == ["api/main.py"]

    def test_modify_and_remove_goal(self):
        tree = GoalTree(root_id="root")
        tree.add_goal(GoalNode(id="root", parent_id=None, type="category", description="Root"))
        tree.add_goal(GoalNode(id="child", parent_id="root", type="objective", description="Old"))
        tree.modify_goal("child", description="New")
        assert tree.get_goal("child").description == "New"
        tree.remove_goal("child")
        with pytest.raises(KeyError, match="Unknown goal"):
            tree.get_goal("child")


# ---------------------------------------------------------------------------
# DependencyGraph
# ---------------------------------------------------------------------------

def make_modulos(*pairs):
    """pairs: (nombre, [dep1, dep2])"""
    return [{"nombre": n, "dependencias": d} for n, d in pairs]


class TestDependencyGraph:
    def test_linear_chain(self):
        mods = make_modulos(("A", []), ("B", ["A"]), ("C", ["B"]))
        graph = DependencyGraph(mods)
        plan = graph.build_execution_plan()
        assert plan.order == ["A", "B", "C"]
        assert plan.parallelizable is False

    def test_parallel_roots(self):
        mods = make_modulos(("A", []), ("B", []), ("C", ["A", "B"]))
        graph = DependencyGraph(mods)
        plan = graph.build_execution_plan()
        assert set(plan.levels[0]) == {"A", "B"}
        assert plan.levels[1] == ["C"]
        assert plan.parallelizable is True

    def test_cycle_broken_automatically(self):
        mods = make_modulos(("A", ["B"]), ("B", ["A"]))
        plan = DependencyGraph(mods).build_execution_plan()
        assert set(plan.order) == {"A", "B"}
        assert len(plan.broken_edges) == 1

    def test_ignores_external_deps(self):
        mods = make_modulos(("A", []), ("B", ["X"]))
        plan = DependencyGraph(mods).build_execution_plan()
        assert set(plan.order) == {"A", "B"}


# ---------------------------------------------------------------------------
# Core Managers
# ---------------------------------------------------------------------------

class TestBranchManager:
    def setup_method(self):
        self.bm = BranchManager(Path("/fake/projects"))

    def test_structural_with_regen_branches(self):
        assert self.bm.should_branch("structural", True) is True

    def test_cosmetic_never_branches(self):
        assert self.bm.should_branch("cosmetic", True) is False


class TestContextHealthMonitor:
    def _monitor(self):
        return ContextHealthMonitor(notify_fn=lambda *_: None)

    def test_initial_status_healthy(self):
        m = self._monitor()
        assert m.status().level == 0

    def test_record_increments_tokens(self):
        m = self._monitor()
        m.record("req", "claude", 1.0, "a" * 400, True)
        assert m._total_tokens == 100

    def test_high_error_rate_warns(self):
        m = self._monitor()
        for _ in range(9):
            m.record("req", "ollama", 1.0, "Error: timeout", False)
        m.record("req", "ollama", 1.0, "ok", True)
        assert m.status().level >= 2


class TestProjectManager:
    def test_load_metadata(self, tmp_path):
        manager = ProjectManager(tmp_path)
        project_dir = tmp_path / "projects" / "demo"
        project_dir.mkdir(parents=True)
        (project_dir / "metadata.json").write_text('{"id":"demo"}', encoding="utf-8")
        meta = manager.load_metadata("demo")
        assert meta["id"] == "demo"


class TestGitManager:
    def test_ensure_repo_runs_git_init(self, tmp_path):
        ws = tmp_path / "w"
        ws.mkdir(parents=True)
        with patch("kernel.git_manager.subprocess.run") as run_mock:
            GitManager.ensure_repo(ws)
            run_mock.assert_called_once()


# ---------------------------------------------------------------------------
# Monitoring and Alerts
# ---------------------------------------------------------------------------

class TestUsageMonitorDashboard:
    def test_grouped_summary(self, tmp_path):
        monitor = UsageMonitor(tmp_path / "usage.db")
        monitor.record(
            provider="claude", 
            model="sonnet", 
            tokens_input=100, 
            tokens_output=200, 
            latency_ms=1000, 
            cost_usd=0.01, 
            error_code=None,
            metadata={}
        )
        grouped = monitor.grouped_summary()
        assert len(grouped) == 1
        assert grouped[0]["provider"] == "claude"

class TestAlertManager:
    def test_alert_manager_thresholds(self, tmp_path):
        """Bloque D Fix: Aligned with new $999,999 thresholds in V2."""
        monitor = UsageMonitor(tmp_path / "usage.db")
        manager = AlertManager(monitor)
        
        # Bypass budget by recording massive cost to trigger alert despite high thresholds
        monitor.record(
            provider="claude", 
            model="sonnet", 
            tokens_input=1, 
            tokens_output=1, 
            latency_ms=1, 
            cost_usd=1_000_000.0, 
            error_code=None,
            metadata={}
        )
        
        alerts = manager.evaluate()
        assert any(item["kind"] == "cost" for item in alerts)


# ---------------------------------------------------------------------------
# Intelligence Routers
# ---------------------------------------------------------------------------

class TestFileComplexityRouter:
    def setup_method(self):
        from kernel.intelligence.file_complexity_router import FileComplexityRouter
        self.router = FileComplexityRouter()

    def test_classification(self):
        assert self.router.classify("auth/jwt.py", {"name": "auth"}) == "complex"
        assert self.router.classify("utils/helper.py", {"name": "utils"}) == "simple"

    def test_effective_levels_complex_v2(self):
        """Bloque D Fix: V2 complex routing starts from gemini."""
        base = ["qwen", "gemini", "claude"]
        levels = self.router.effective_levels("complex", base)
        assert levels == ["gemini"]


# ---------------------------------------------------------------------------
# SODA V2 Specific Tests (Motor Recursivo)
# ---------------------------------------------------------------------------

class TestFinopsRouterV2:
    def test_ultra_profile_alignment(self):
        from kernel.intelligence.finops_router import FinopsRouter
        lineup = FinopsRouter.get_lineup("ultra")
        assert lineup.layer2_architect == "deepseek-chat"
        assert lineup.layer5_qa == "claude-3-5-sonnet-20241022"
        assert lineup.parallel_agents == 4

    def test_escalation_path(self):
        from kernel.intelligence.finops_router import FinopsRouter
        # Flash -> Pro (step-up within 2.5 tier)
        assert FinopsRouter.escalate_model("gemini-2.5-flash") == "gemini-2.5-pro"
        # Pro -> Flash 3 (escalate to 3.x tier)
        assert FinopsRouter.escalate_model("gemini-2.5-pro") == "gemini-3-flash-preview"
        # 3.x Pro -> DeepSeek (cross-provider escalation)
        assert FinopsRouter.escalate_model("gemini-3.1-pro-preview") == "deepseek-chat"


class TestRecursiveEngineLogic:
    @pytest.mark.anyio
    @pytest.mark.parametrize("anyio_backend", ["asyncio"])
    async def test_topological_generation_order(self, anyio_backend):
        from kernel.orchestration.recursive_engine import SodaRecursiveEngine
        from kernel.core.models_v2 import SodaContract, ContractStatus

        # Mock contracts
        c1 = MagicMock(spec=SodaContract, contract_id="DB", is_atomic=True, dependencies=[])
        c1.status = ContractStatus.PENDING_EXECUTION
        c2 = MagicMock(spec=SodaContract, contract_id="API", is_atomic=True, dependencies=["DB"])
        c2.status = ContractStatus.PENDING_EXECUTION
        
        pool = {"DB": c1, "API": c2}
        lineup = MagicMock()
        lineup.parallel_agents = 2
        engine = SodaRecursiveEngine(MagicMock(), MagicMock(), lineup)
        
        # Intercept execute_bottom_up order
        order = []

        async def fake_initial(contract, code_map):
            order.append(contract.contract_id)
            return {f"{contract.contract_id}.py": f"class {contract.contract_id}: pass"}

        with patch.object(engine, "_run_layer3", side_effect=lambda c: c), \
             patch.object(engine, "_initial_generation", side_effect=fake_initial), \
             patch.object(engine, "_audit_and_repair_module", new=AsyncMock(side_effect=lambda c, f: f)), \
             patch.object(engine, "_generate_integration_layer", new=AsyncMock()), \
             patch.object(engine, "_generate_docker_compose", new=AsyncMock()):
            await engine.execute_bottom_up(pool)
            
        assert order == ["DB", "API"]

    def test_format_validation_error_pydantic(self):
        from kernel.orchestration.recursive_engine import SodaRecursiveEngine
        engine = SodaRecursiveEngine(None, None, MagicMock())
        
        # Simulate pydantic error
        try:
            from kernel.core.models_v2 import SodaContract
            SodaContract(contract_id="x") # missing required fields
        except ValidationError as e:
            msg = engine._format_validation_error(e)
            assert "Tu respuesta JSON no cumple el esquema" in msg
            assert "Error en 'title'" in msg
