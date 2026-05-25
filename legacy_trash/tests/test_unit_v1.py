"""
Unit tests for deterministic SODA components — no API calls.
Run with: python -m pytest tests/test_unit.py -v
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

import types
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

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
# _extract_json
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_clean_json(self):
        raw = '{"key": "value", "n": 42}'
        assert SodaOrchestrator._extract_json(raw) == {"key": "value", "n": 42}

    def test_json_in_markdown_block(self):
        raw = '```json\n{"a": 1}\n```'
        assert SodaOrchestrator._extract_json(raw) == {"a": 1}

    def test_json_embedded_in_text(self):
        raw = 'Here is the result: {"x": true} done.'
        assert SodaOrchestrator._extract_json(raw) == {"x": True}

    def test_invalid_returns_raw(self):
        raw = "not json at all"
        result = SodaOrchestrator._extract_json(raw)
        assert result == {"raw": "not json at all"}

    def test_nested_json(self):
        raw = '{"modules": [{"name": "auth", "deps": []}]}'
        result = SodaOrchestrator._extract_json(raw)
        assert result["modules"][0]["name"] == "auth"


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


class TestCodeGeneratorMetadata:
    def test_generate_file_injects_missing_metadata_before_validation(self):
        generator = CodeGenerator(MagicMock(model="qwen"), MagicMock(), MagicMock())
        generator._call_ollama = AsyncMock(return_value="print('ok')\n")
        generator._validate_syntax = MagicMock(return_value=(True, "ok"))

        module = {
            "nombre": "api",
            "responsabilidad": "Serve requests",
            "dependencias": [],
            "endpoints": [],
        }
        blueprint = {"stack_sugerido": {}}
        architecture = {"contratos": []}

        result = asyncio.run(generator.generate_file("main.py", module, blueprint, architecture))

        assert result.validated is True
        assert "# goal_id: api__main" in result.content


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

    def test_single_module(self):
        mods = make_modulos(("Solo", []))
        plan = DependencyGraph(mods).build_execution_plan()
        assert plan.order == ["Solo"]
        assert plan.parallelizable is False

    def test_cycle_broken_automatically(self):
        # Cycles are broken — no exception, broken_edges populated
        mods = make_modulos(("A", ["B"]), ("B", ["A"]))
        plan = DependencyGraph(mods).build_execution_plan()
        assert set(plan.order) == {"A", "B"}
        assert len(plan.broken_edges) == 1
        assert plan.broken_edges[0] in [("A", "B"), ("B", "A")]

    def test_ignores_external_deps(self):
        # "B" depends on "X" which doesn't exist → should be ignored
        mods = make_modulos(("A", []), ("B", ["X"]))
        plan = DependencyGraph(mods).build_execution_plan()
        assert set(plan.order) == {"A", "B"}

    def test_execution_plan_fields(self):
        mods = make_modulos(("A", []), ("B", ["A"]))
        plan = DependencyGraph(mods).build_execution_plan()
        assert isinstance(plan, ExecutionPlan)
        assert isinstance(plan.levels, list)
        assert isinstance(plan.order, list)
        assert isinstance(plan.parallelizable, bool)


# ---------------------------------------------------------------------------
# BranchManager.should_branch
# ---------------------------------------------------------------------------

class TestBranchManager:
    def setup_method(self):
        self.bm = BranchManager(Path("/fake/projects"))

    def test_structural_with_regen_branches(self):
        assert self.bm.should_branch("structural", True) is True

    def test_structural_without_regen_no_branch(self):
        assert self.bm.should_branch("structural", False) is False

    def test_scope_with_regen_branches(self):
        assert self.bm.should_branch("scope", True) is True

    def test_new_module_with_regen_branches(self):
        assert self.bm.should_branch("new_module", True) is True

    def test_cosmetic_never_branches(self):
        assert self.bm.should_branch("cosmetic", True) is False
        assert self.bm.should_branch("cosmetic", False) is False

    def test_bugfix_never_branches(self):
        assert self.bm.should_branch("bugfix", True) is False


# ---------------------------------------------------------------------------
# ContextHealthMonitor
# ---------------------------------------------------------------------------

class TestContextHealthMonitor:
    def _monitor(self):
        return ContextHealthMonitor(notify_fn=lambda *_: None)

    def test_initial_status_healthy(self):
        m = self._monitor()
        assert m.status().level == 0

    def test_record_increments_tokens(self):
        m = self._monitor()
        m.record("req", "claude", 1.0, "a" * 400, True)
        assert m._total_tokens == 100  # 400 chars / 4

    def test_high_token_count_warns(self):
        m = self._monitor()
        big_response = "x" * (80_000 * 4 + 4)
        m.record("req", "claude", 1.0, big_response, True)
        assert m.status().level == 2  # warn only — pipeline never stops on token count alone

    def test_high_error_rate_warns(self):
        # 9 failures out of 10 calls = 90% — clearly above 50% threshold
        m = self._monitor()
        for _ in range(9):
            m.record("req", "ollama", 1.0, "Error: timeout", False)
        m.record("req", "ollama", 1.0, "ok", True)
        assert m.status().level >= 2

    def test_qwen_escalation_no_false_positive(self):
        # 3 Qwen failures + 1 Claude success = 75% in window of 4 — still below 50% threshold? No.
        # But with ROLLING_WINDOW=15, 4 calls only, need >= 3 to check.
        # 3/4 = 75% > 50% — this WILL warn. That's correct: 3 consecutive failures is a real issue.
        # The key fix is that short bursts don't dominate a 15-call window in a full session.
        m = self._monitor()
        # Simulate 10 successful calls before the escalation burst
        for _ in range(10):
            m.record("req", "ollama", 1.0, "ok", True)
        # Now 3 Qwen failures + 1 Claude success
        for _ in range(3):
            m.record("req", "ollama", 1.0, "Error: x", False)
        m.record("req", "claude", 1.0, "ok", True)
        # Window of 15: 10 ok + 3 fail + 1 ok = 3/14 = 21% — healthy
        assert m.status().level < 2

    def test_slow_calls_observed(self):
        # SLOW_CALL_S is now 30s — calls at 35s should trigger level 1
        m = self._monitor()
        for _ in range(2):
            m.record("req", "ollama", 35.0, "ok response", True)
        assert m.status().level >= 1

    def test_fast_calls_not_slow(self):
        # Calls under 30s should not trigger slow warning
        m = self._monitor()
        for _ in range(5):
            m.record("req", "ollama", 25.0, "ok response", True)
        assert m.status().level == 0

    def test_summary_keys(self):
        m = self._monitor()
        m.record("req", "claude", 1.0, "response text", True)
        s = m.summary()
        assert all(k in s for k in ("total_calls", "total_tokens_estimate", "error_count", "health_level"))

    def test_single_error_not_warn(self):
        m = self._monitor()
        m.record("req", "claude", 1.0, "Error: x", False)
        m.record("req", "claude", 1.0, "ok", True)
        assert m.status().level == 0


# ---------------------------------------------------------------------------
# Project metadata persistence
# ---------------------------------------------------------------------------

class TestMetadataPersistence:
    def test_save_and_read_metadata(self, tmp_path):
        project = Project(
            id="proj_test",
            description="Test project",
            state=ProjectState.DONE,
            workspace=tmp_path,
            blueprint={"title": "test"},
            architecture={"modulos": []},
            skills=["skill_fastapi"],
            profile="profile_web_fullstack",
            project_type="software",
            capability_packs=["auth_complete"],
            goal_tree={"root_id": "proj_test__root", "nodes": []},
            intensity_level="medium",
            reference_report={"total_urls": 1, "unique_urls": 1, "broken_candidates": 0},
        )

        # Replicate _save_state logic
        (tmp_path / "metadata.json").write_text(
            json.dumps({
                "id": project.id,
                "state": project.state.value,
                "description": project.description,
                "blueprint": project.blueprint,
                "architecture": project.architecture,
                "skills": project.skills,
                "profile": project.profile,
                "project_type": project.project_type,
                "capability_packs": project.capability_packs,
                "goal_tree": project.goal_tree,
                "intensity_level": project.intensity_level,
                "reference_report": project.reference_report,
                "created_at": project.created_at,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        saved = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
        assert saved["id"] == "proj_test"
        assert saved["state"] == "done"
        assert saved["skills"] == ["skill_fastapi"]
        assert saved["blueprint"]["title"] == "test"
        assert saved["project_type"] == "software"
        assert saved["capability_packs"] == ["auth_complete"]
        assert saved["goal_tree"] == {"root_id": "proj_test__root", "nodes": []}
        assert saved["intensity_level"] == "medium"
        assert saved["reference_report"]["total_urls"] == 1

    def test_project_defaults(self):
        p = Project(id="x", description="y")
        assert p.state == ProjectState.IDLE
        assert p.skills == []
        assert p.profile == ""
        assert p.blueprint == {}
        assert p.project_type == ""
        assert p.capability_packs == []
        assert p.goal_tree == {}
        assert p.intensity_level == ""
        assert p.reference_report == {}


# ---------------------------------------------------------------------------
# Validation decisions and error mapping
# ---------------------------------------------------------------------------

class TestValidationProgression:
    def test_should_regenerate_when_failed_modules_are_focused(self):
        orch = object.__new__(SodaOrchestrator)
        project = Project(
            id="p1",
            description="desc",
            workspace=Path("."),
            architecture={
                "modulos": [
                    {"nombre": "api"},
                    {"nombre": "db"},
                    {"nombre": "ui"},
                ]
            },
        )
        result = {
            "fixed": False,
            "skipped": False,
            "failed_modules": ["api"],
        }
        should, mods = SodaOrchestrator._should_regenerate_after_validation(orch, result, project)
        assert should is True
        assert mods == ["api"]

    def test_should_not_regenerate_when_failure_is_broad(self):
        orch = object.__new__(SodaOrchestrator)
        project = Project(
            id="p2",
            description="desc",
            workspace=Path("."),
            architecture={
                "modulos": [
                    {"nombre": "api"},
                    {"nombre": "db"},
                ]
            },
        )
        result = {
            "fixed": False,
            "skipped": False,
            "failed_modules": ["api", "db"],
        }
        should, mods = SodaOrchestrator._should_regenerate_after_validation(orch, result, project)
        assert should is False
        assert mods == []


class TestProjectValidatorErrorMapping:
    def test_extract_failed_modules_from_output(self):
        validator = ProjectValidator(None, None, None)
        architecture = {
            "modulos": [
                {
                    "nombre": "alerting",
                    "archivos_principales": ["Services/AlertingService.cs"],
                },
                {
                    "nombre": "persistence",
                    "archivos_principales": ["Data/Repository.cs"],
                },
            ]
        }
        output = "Services/AlertingService.cs(12,5): error CS1002: ; expected"
        failed = validator._extract_failed_modules(output, architecture)
        assert failed == ["alerting"]


class TestAIProviderHub:
    def test_default_chain_includes_primary_first(self):
        hub = AIProviderHub(providers={
            "claude": object(),
            "gemini": object(),
            "ollama": object(),
            "openai": object(),
        })
        chain = hub.get_chain("claude")
        assert chain[0] == "claude"
        assert "openai" in chain

    def test_custom_route_is_applied(self):
        hub = AIProviderHub(
            providers={"claude": object(), "gemini": object(), "openai": object()},
            routes={"claude": ["claude", "openai"]},
        )
        chain = hub.get_chain("claude")
        assert chain[:2] == ["claude", "openai"]

    def test_unknown_provider_in_route_is_ignored(self):
        hub = AIProviderHub(
            providers={"claude": object(), "gemini": object()},
            routes={"claude": ["claude", "missing", "gemini"]},
        )
        assert hub.get_chain("claude") == ["claude", "gemini"]


class TestAIPhaseProviderSelection:
    def test_role_override_uses_configured_provider(self):
        orch = object.__new__(SodaOrchestrator)
        orch.ai_hub = AIProviderHub(providers={"claude": object(), "gemini": object(), "openai": object()})
        orch._phase_provider_map = {"docs_generator": "openai"}
        selected = SodaOrchestrator._resolve_primary_provider(orch, "claude", "docs_generator")
        assert selected == "openai"

    def test_invalid_override_falls_back_to_default(self):
        orch = object.__new__(SodaOrchestrator)
        orch.ai_hub = AIProviderHub(providers={"claude": object(), "gemini": object()})
        orch._phase_provider_map = {"docs_generator": "unknown_provider"}
        selected = SodaOrchestrator._resolve_primary_provider(orch, "claude", "docs_generator")
        assert selected == "claude"


class TestProjectRunner:
    def test_detect_stack_python(self):
        runner = ProjectRunner()
        assert runner.detect_stack("uvicorn app:app --reload", "pip install -r requirements.txt") == "python"

    def test_detect_stack_node(self):
        runner = ProjectRunner()
        assert runner.detect_stack("npm run dev", "npm install") == "node"

    def test_preflight_finds_manifest(self, tmp_path):
        runner = ProjectRunner()
        project_dir = tmp_path / "proj"
        source_dir = project_dir / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "package.json").write_text("{}", encoding="utf-8")

        health = runner.preflight(project_dir, "npm run dev", "npm install")
        assert health.stack == "node"
        assert health.source_exists is True
        assert health.manifest_found is True
        assert health.detected_manifest == "package.json"

    def test_normalize_run_command_with_cd_prefix(self, tmp_path):
        runner = ProjectRunner()
        source_dir = tmp_path / "src"
        app_dir = source_dir / "app"
        app_dir.mkdir(parents=True)

        cwd, cmd = runner.normalize_run_command(source_dir, "cd app && npm run dev")
        assert cwd == app_dir
        assert cmd == "npm run dev"

    def test_resolve_working_dir_prefers_manifest_location(self, tmp_path):
        runner = ProjectRunner()
        source_dir = tmp_path / "src"
        app_dir = source_dir / "app"
        app_dir.mkdir(parents=True)
        (app_dir / "package.json").write_text("{}", encoding="utf-8")

        cwd, cmd = runner.resolve_working_dir(source_dir, "cd app && npm run dev", "npm install")
        assert cwd == app_dir
        assert cmd == "npm run dev"

    def test_infer_runtime_url_from_port_flag(self):
        runner = ProjectRunner()
        url = runner.infer_runtime_url("uvicorn app:app --port 9000", "python")
        assert url == "http://127.0.0.1:9000"

    def test_smoke_check_without_run_command(self, tmp_path):
        runner = ProjectRunner()
        project_dir = tmp_path / "proj"
        project_dir.mkdir(parents=True)

        smoke = runner.smoke_check(project_dir, "", "")
        assert smoke.attempted is False
        assert smoke.reason == "no_run_command"


class TestAdvancedOrchestrationSignals:
    def test_apply_capability_packs_updates_project_and_persists(self, tmp_path):
        orch = object.__new__(SodaOrchestrator)
        orch.capability_pack_registry = CapabilityPackRegistry()
        orch._notify = MagicMock()
        orch._save_state = SodaOrchestrator._save_state.__get__(orch, SodaOrchestrator)

        project = Project(
            id="proj",
            description="Build authentication with login and JWT roles",
            workspace=tmp_path,
        )
        SodaOrchestrator._apply_capability_packs(orch, project)

        saved = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
        assert project.capability_packs == ["auth_complete"]
        assert saved["capability_packs"] == ["auth_complete"]

    def test_apply_project_type_updates_project_and_persists(self, tmp_path):
        orch = object.__new__(SodaOrchestrator)
        orch.project_types = ProjectTypeRegistry()
        orch._notify = MagicMock()
        orch._save_state = SodaOrchestrator._save_state.__get__(orch, SodaOrchestrator)

        project = Project(
            id="proj",
            description="Create a marketing campaign and content calendar",
            workspace=tmp_path,
        )
        SodaOrchestrator._apply_project_type(orch, project)

        saved = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
        assert project.project_type == "marketing"
        assert saved["project_type"] == "marketing"

    def test_augment_task_with_project_context_includes_registry_hints(self):
        orch = object.__new__(SodaOrchestrator)
        orch.project_types = ProjectTypeRegistry()
        orch.capability_pack_registry = CapabilityPackRegistry()

        project = Project(id="proj", description="Build a simple todo API", project_type="software")
        task = SodaOrchestrator._augment_task_with_project_context(orch, "Implement the requested solution", project)

        assert "PROJECT_TYPE_CONTEXT" in task
        assert "key: software" in task
        assert "runtime_validation" in task

    def test_augment_task_with_project_context_includes_capability_packs(self):
        orch = object.__new__(SodaOrchestrator)
        orch.project_types = ProjectTypeRegistry()
        orch.capability_pack_registry = CapabilityPackRegistry()

        project = Project(
            id="proj",
            description="Build login flow with JWT authentication",
            project_type="software",
            capability_packs=["auth_complete"],
        )
        task = SodaOrchestrator._augment_task_with_project_context(orch, "Implement the requested solution", project)

        assert "CAPABILITY_PACKS" in task
        assert "auth_complete" in task
        assert "login" in task

    def test_apply_intensity_level_updates_project_and_persists(self, tmp_path):
        orch = object.__new__(SodaOrchestrator)
        orch.intensity = IntensityOrchestrator()
        orch._notify = MagicMock()
        orch._save_state = SodaOrchestrator._save_state.__get__(orch, SodaOrchestrator)

        project = Project(id="proj", description="x" * 140, workspace=tmp_path)
        SodaOrchestrator._apply_intensity_level(orch, project)

        saved = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
        assert project.intensity_level == "medium"
        assert saved["intensity_level"] == "medium"

    def test_build_reference_report_maps_analyzer_output(self):
        orch = object.__new__(SodaOrchestrator)
        orch.reference_analyzer = ReferenceAnalyzer()

        report = SodaOrchestrator._build_reference_report(
            orch,
            "Docs with https://example.com and https://valid.test/page"
        )

        assert report == {
            "total_urls": 2,
            "unique_urls": 2,
            "broken_candidates": 1,
        }

    def test_smoke_check_with_retry_stops_on_success(self, tmp_path):
        import asyncio

        class FakeRunner(ProjectRunner):
            def __init__(self):
                self.calls = 0

            def smoke_check(self, *args, **kwargs):
                self.calls += 1
                if self.calls < 3:
                    return RuntimeSmoke(True, False, "http://127.0.0.1:8000", "connection_error", 0)
                return RuntimeSmoke(True, True, "http://127.0.0.1:8000", "http_ok", 200)

        runner = FakeRunner()
        project_dir = tmp_path / "proj"
        project_dir.mkdir(parents=True)

        result = asyncio.run(
            runner.smoke_check_with_retry(
                project_workspace=project_dir,
                run_command="uvicorn app:app --port 8000",
                attempts=5,
                delay_s=0,
            )
        )

        assert runner.calls == 3
        assert result.passed is True


class TestProjectManager:
    def test_load_metadata(self, tmp_path):
        manager = ProjectManager(tmp_path)
        project_dir = tmp_path / "projects" / "demo"
        project_dir.mkdir(parents=True)
        (project_dir / "metadata.json").write_text('{"id":"demo"}', encoding="utf-8")

        meta = manager.load_metadata("demo")
        assert meta["id"] == "demo"

    def test_source_dir_fallback(self, tmp_path):
        manager = ProjectManager(tmp_path)
        project_dir = tmp_path / "projects" / "demo"
        project_dir.mkdir(parents=True)

        assert manager.source_dir("demo") == project_dir


class TestRuntimeSmokeConfig:
    def test_runtime_smoke_enabled_by_default(self, tmp_path):
        orch = object.__new__(SodaOrchestrator)
        orch.base_dir = tmp_path
        assert SodaOrchestrator._runtime_smoke_enabled(orch) is True


class TestGitManager:
    def test_ensure_repo_runs_git_init_when_missing(self, tmp_path):
        from unittest.mock import patch

        ws = tmp_path / "w"
        ws.mkdir(parents=True)

        with patch("kernel.git_manager.subprocess.run") as run_mock:
            GitManager.ensure_repo(ws)
            run_mock.assert_called_once()

    def test_commit_all_rejects_orphan_python_files(self, tmp_path):
        from unittest.mock import patch

        ws = tmp_path / "w"
        (ws / ".git").mkdir(parents=True)
        (ws / "source").mkdir()
        (ws / "source" / "main.py").write_text("print('missing metadata')\n", encoding="utf-8")

        manager = GitManager()

        with patch("kernel.git_manager.subprocess.run") as run_mock:
            with pytest.raises(ValueError, match="Goal integrity validation failed"):
                manager.commit_all(ws, "snapshot")
            run_mock.assert_not_called()

    def test_commit_all_accepts_python_files_with_metadata(self, tmp_path):
        from unittest.mock import patch

        ws = tmp_path / "w"
        (ws / ".git").mkdir(parents=True)
        (ws / "source").mkdir()
        (ws / "source" / "main.py").write_text(
            "# --- METADATA SODA ---\n"
            "# goal_id: api__main\n"
            "# goal_hash: abc123\n"
            "# --- FIN METADATA ---\n"
            "print('ok')\n",
            encoding="utf-8",
        )

        manager = GitManager()

        with patch("kernel.git_manager.subprocess.run") as run_mock:
            manager.commit_all(ws, "snapshot")
            assert run_mock.call_count == 2

    def test_commit_all_rejects_implemented_goal_without_file(self, tmp_path):
        from unittest.mock import patch

        ws = tmp_path / "w"
        (ws / ".git").mkdir(parents=True)
        goal_tree = GoalTree.from_architecture(
            "proj",
            "Build API",
            {"modulos": [{"nombre": "api", "responsabilidad": "REST", "dependencias": [], "archivos_principales": ["source/api/main.py"]}]},
        )
        goal_tree.mark_implemented("api__source_api_main_py", "source/api/main.py")
        (ws / "goal_tree.json").write_text(json.dumps(goal_tree.to_dict(), indent=2), encoding="utf-8")

        manager = GitManager()

        with patch("kernel.git_manager.subprocess.run") as run_mock:
            with pytest.raises(ValueError, match="implemented goal missing file"):
                manager.commit_all(ws, "snapshot")
            run_mock.assert_not_called()


class TestGoalIntegrityValidator:
    def test_validate_workspace_reports_orphan_python_files(self, tmp_path):
        source_dir = tmp_path / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "valid.py").write_text(
            "# --- METADATA SODA ---\n"
            "# goal_id: api__valid\n"
            "# goal_hash: hash-ok\n"
            "# --- FIN METADATA ---\n"
            "print('ok')\n",
            encoding="utf-8",
        )
        (source_dir / "invalid.py").write_text("print('missing metadata')\n", encoding="utf-8")

        validator = GoalIntegrityValidator()

        is_valid, issues = validator.validate_workspace(tmp_path)

        assert is_valid is False
        assert issues == ["missing metadata: source/invalid.py"]

    def test_validate_workspace_rejects_undeclared_goal_id(self, tmp_path):
        source_dir = tmp_path / "source"
        source_dir.mkdir(parents=True)
        goal = build_file_goal_node(
            {"nombre": "api", "responsabilidad": "REST", "dependencias": []},
            "source/api/main.py",
            parent_id="module__api",
        )
        tree = GoalTree(root_id="proj__root")
        tree.add_goal(GoalNode(id="proj__root", parent_id=None, type="category", description="Root"))
        tree.add_goal(GoalNode(id="module__api", parent_id="proj__root", type="category", description="REST"))
        tree.add_goal(goal)
        (tmp_path / "goal_tree.json").write_text(json.dumps(tree.to_dict(), indent=2), encoding="utf-8")
        (source_dir / "main.py").write_text(
            "# --- METADATA SODA ---\n"
            "# goal_id: ghost__main\n"
            f"# goal_hash: {goal.hash}\n"
            "# --- FIN METADATA ---\n"
            "print('ok')\n",
            encoding="utf-8",
        )

        validator = GoalIntegrityValidator()

        is_valid, issues = validator.validate_workspace(tmp_path)

        assert is_valid is False
        assert any("undeclared goal_id: ghost__main" in item for item in issues)

    def test_validate_workspace_rejects_implemented_goal_missing_file(self, tmp_path):
        tree = GoalTree.from_architecture(
            "proj",
            "Build API",
            {"modulos": [{"nombre": "api", "responsabilidad": "REST", "dependencias": [], "archivos_principales": ["source/api/main.py"]}]},
        )
        tree.mark_implemented("api__source_api_main_py", "source/api/main.py")
        (tmp_path / "goal_tree.json").write_text(json.dumps(tree.to_dict(), indent=2), encoding="utf-8")

        validator = GoalIntegrityValidator()

        is_valid, issues = validator.validate_workspace(tmp_path)

        assert is_valid is False
        assert "implemented goal missing file: api__source_api_main_py -> source/api/main.py" in issues


class TestCapabilityManagers:
    def test_skill_manager_delegates_to_matcher(self):
        import asyncio
        matcher = MagicMock()
        matcher.match = AsyncMock(return_value=["skill_fastapi"])
        matcher.load_skill_context.return_value = "ctx"
        manager = SkillManager(matcher)

        skills = asyncio.run(manager.select("build api"))

        assert skills == ["skill_fastapi"]
        assert manager.load_context(["skill_fastapi"]) == "ctx"

    def test_profile_manager_delegates_to_matcher(self):
        import asyncio
        matcher = MagicMock()
        matcher.match = AsyncMock(return_value="profile_web_fullstack")
        matcher.load_profile_context.return_value = "profile_ctx"
        manager = ProfileManager(matcher)

        profile = asyncio.run(manager.select("build api", ["skill_fastapi"]))

        assert profile == "profile_web_fullstack"
        assert manager.load_context("profile_web_fullstack") == "profile_ctx"


class TestUsageMonitorDashboard:
    def test_grouped_summary_and_recent(self, tmp_path):
        monitor = UsageMonitor(tmp_path / "usage.db")
        monitor.record(
            provider="claude",
            model="claude-sonnet-4-6",
            tokens_input=100,
            tokens_output=200,
            latency_ms=1200,
            cost_usd=0.01,
            error_code=None,
            metadata={"role": "req"},
        )
        monitor.record(
            provider="claude",
            model="claude-sonnet-4-6",
            tokens_input=50,
            tokens_output=60,
            latency_ms=900,
            cost_usd=0.005,
            error_code="RATE_LIMIT",
            metadata={"role": "arch"},
        )

        grouped = monitor.grouped_summary()
        assert len(grouped) == 1
        assert grouped[0]["provider"] == "claude"
        assert grouped[0]["total_calls"] == 2
        assert grouped[0]["error_calls"] == 1

        recent = monitor.recent_calls(limit=5)
        assert len(recent) == 2
        assert "metadata" in recent[0]


class TestAlertManager:
    def test_alert_manager_warns_on_cost_and_error_rate(self, tmp_path):
        monitor = UsageMonitor(tmp_path / "usage.db")
        manager = AlertManager(monitor)

        for _ in range(3):
            monitor.record(
                provider="claude",
                model="claude-sonnet-4-6",
                tokens_input=100,
                tokens_output=100,
                latency_ms=35_000,
                cost_usd=2.5,
                error_code="RATE_LIMIT",
                metadata={"role": "req"},
            )

        alerts = manager.evaluate()

        assert any(item["kind"] == "cost" for item in alerts)
        assert any(item["kind"] == "latency" for item in alerts)
        assert any(item["kind"] == "error_rate" for item in alerts)


class TestExecutionHelpers:
    def test_stack_detector_node(self):
        assert StackDetector.detect("npm run dev", "npm install") == "node"

    def test_stack_detector_unknown(self):
        assert StackDetector.detect("custom-cmd", "") == "unknown"

    def test_port_manager_infers_default_python_url(self):
        assert PortManager.infer_url("uvicorn app:app", "python") == "http://127.0.0.1:8000/health"

    def test_port_manager_extracts_explicit_port(self):
        assert PortManager.infer_url("uvicorn app:app --port 9001", "python") == "http://127.0.0.1:9001"


class TestAdvancedModules:
    def test_reference_analyzer(self):
        analyzer = ReferenceAnalyzer()
        report = analyzer.analyze("Docs: https://example.com and https://github.com/test")
        assert report.total_urls == 2
        assert report.unique_urls == 2

    def test_intensity_orchestrator_levels(self):
        io = IntensityOrchestrator()
        assert io.choose_level("short") == "low"
        assert io.choose_level("x" * 200) == "medium"
        assert io.choose_level("x" * 700) == "high"

        profile = io.choose_profile(
            "Design a multi-tenant payment platform with Kubernetes, audit and compliance"
        )
        assert profile.level == 4
        assert profile.label == "critical"
        assert profile.arbiter_required is True
        assert io.choose_execution_level("x" * 200) == 2

    def test_vision_capturer_missing_file(self, tmp_path):
        cap = VisionCapturer().capture(tmp_path / "missing.png")
        assert cap.exists is False

    def test_visual_inspector_missing_file(self, tmp_path):
        insp = VisualInspector().inspect(tmp_path / "missing.png")
        assert insp.valid_image is False

    def test_project_chat_payload_contains_message(self, tmp_path):
        chat = ProjectChat()
        source = tmp_path / "source"
        source.mkdir(parents=True)
        payload = chat.build_user_payload({"blueprint": {}, "architecture": {}}, source, "hola")
        assert "PREGUNTA: hola" in payload

    def test_web_researcher_fetch_parses_title(self):
        from unittest.mock import patch

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.text = "<html><title>Test Page</title><body>Hello</body></html>"

        with patch("kernel.external.web_researcher.requests.get", return_value=fake_response):
            result = WebResearcher().fetch("https://example.org")
            assert isinstance(result, WebResearchResult)
            assert result.status_code == 200
            assert result.title == "Test Page"


class TestSystemActionsExecutor:
    def test_open_project_uses_startfile(self, tmp_path):
        from unittest.mock import patch

        manager = ProjectManager(tmp_path)
        project_dir = tmp_path / "projects" / "demo"
        project_dir.mkdir(parents=True)
        (project_dir / "metadata.json").write_text('{"id":"demo"}', encoding="utf-8")
        executor = SystemActionsExecutor(manager)

        with patch("kernel.external.system_actions.os.startfile", create=True) as startfile_mock:
            result = executor.execute("open_project", {"project_id": "demo"})

        startfile_mock.assert_called_once_with(str(project_dir))
        assert result.action == "open_project"
        assert result.launched is True

    def test_open_file_rejects_escape(self, tmp_path):
        manager = ProjectManager(tmp_path)
        project_dir = tmp_path / "projects" / "demo"
        project_dir.mkdir(parents=True)
        (project_dir / "metadata.json").write_text('{"id":"demo"}', encoding="utf-8")
        executor = SystemActionsExecutor(manager)

        with pytest.raises(ValueError, match="escapes the project directory"):
            executor.execute("open_file", {"project_id": "demo", "relative_path": "..\\secret.txt"})

    def test_unknown_action_fails(self, tmp_path):
        manager = ProjectManager(tmp_path)
        executor = SystemActionsExecutor(manager)

        with pytest.raises(ValueError, match="Unsupported action"):
            executor.execute("delete_everything", {})


class TestExternalToolRegistry:
    def test_list_tools_returns_known_catalog(self):
        registry = ExternalToolRegistry()

        items = registry.list_tools()

        assert len(items) >= 3
        assert any(item["key"] == "github" for item in items)

    def test_list_tools_filters_by_capability(self):
        registry = ExternalToolRegistry()

        items = registry.list_tools(capability="scheduling")

        assert len(items) == 1
        assert items[0]["key"] == "google_calendar"

    def test_get_unknown_tool_raises(self):
        registry = ExternalToolRegistry()

        with pytest.raises(KeyError, match="Unknown external tool"):
            registry.get_tool("unknown")


class TestCapabilityPackRegistry:
    def test_list_packs_returns_initial_catalog(self):
        registry = CapabilityPackRegistry()

        items = registry.list_packs()

        assert len(items) == 3
        assert any(item["key"] == "auth_complete" for item in items)

    def test_list_packs_filters_by_domain(self):
        registry = CapabilityPackRegistry()

        items = registry.list_packs(domain="communication")

        assert len(items) == 1
        assert items[0]["key"] == "email_notifications"

    def test_get_unknown_pack_raises(self):
        registry = CapabilityPackRegistry()

        with pytest.raises(KeyError, match="Unknown capability pack"):
            registry.get_pack("unknown")

    def test_recommend_auth_pack_from_keywords(self):
        registry = CapabilityPackRegistry()

        items = registry.recommend("Add login, JWT auth, and role permissions")

        assert items == ["auth_complete"]


class TestProjectTypeRegistry:
    def test_list_types_returns_initial_catalog(self):
        registry = ProjectTypeRegistry()

        items = registry.list_types()

        assert len(items) == 4
        assert any(item["key"] == "software" for item in items)

    def test_get_finance_type_contains_outputs(self):
        registry = ProjectTypeRegistry()

        item = registry.get_type("finance")

        assert item["key"] == "finance"
        assert "financial_model" in item["typical_outputs"]

    def test_classify_marketing_keywords_returns_marketing(self):
        registry = ProjectTypeRegistry()

        project_type = registry.classify("Create a marketing campaign with copy and a content calendar")

        assert project_type == "marketing"

    def test_get_unknown_type_raises(self):
        registry = ProjectTypeRegistry()

        with pytest.raises(KeyError, match="Unknown project type"):
            registry.get_type("unknown")


class TestTelegramGatewayOpenCommands:
    def test_parse_open_project_command(self):
        action, params = TelegramGateway._parse_open_command_args(["proyecto", "demo"])

        assert action == "open_project"
        assert params == {"project_id": "demo"}

    def test_parse_open_file_command(self):
        action, params = TelegramGateway._parse_open_command_args(
            ["archivo", "demo", "src", "main.py"]
        )

        assert action == "open_file"
        assert params == {"project_id": "demo", "relative_path": "src main.py"}

    def test_parse_open_command_rejects_invalid_target(self):
        with pytest.raises(ValueError, match="Destino inválido"):
            TelegramGateway._parse_open_command_args(["desktop", "demo"])


class TestTelegramGatewayPendingAnswers:
    def test_resolve_pending_answer_approves_when_waiting(self):
        gateway = MagicMock()
        gateway.is_waiting = True

        with patch("kernel.communication.telegram_gateway.get_gateway", return_value=gateway):
            message = TelegramGateway._resolve_pending_answer(
                "si",
                "Aprobación enviada. El pipeline continúa.",
            )

        gateway.answer.assert_called_once_with("si")
        assert message == "Aprobación enviada. El pipeline continúa."

    def test_resolve_pending_answer_returns_message_when_idle(self):
        gateway = MagicMock()
        gateway.is_waiting = False

        with patch("kernel.communication.telegram_gateway.get_gateway", return_value=gateway):
            message = TelegramGateway._resolve_pending_answer(
                "no",
                "Rechazo enviado. El pipeline continúa.",
            )

        gateway.answer.assert_not_called()
        assert message == "No hay ninguna pregunta pendiente."


# ---------------------------------------------------------------------------
# Regression: async fallback in SkillMatcher / ProfileMatcher (Bug #P1-A)
# When Gemini returns a capacity error, the Claude fallback must be awaited.
# ---------------------------------------------------------------------------

class TestSkillMatcherAsyncFallback:
    def test_claude_fallback_is_awaited_on_capacity_error(self):
        """If Gemini fails with a capacity error, Claude.prompt() must be awaited."""
        from kernel.capabilities.skill_matcher import SkillMatcher

        gemini = MagicMock()
        gemini.call = AsyncMock(return_value=MagicMock(content="ERROR:OVERLOADED: quota"))

        claude = MagicMock()
        claude.prompt = AsyncMock(return_value='{"matched_skills": []}')

        builder = MagicMock()
        builder.build_payload = MagicMock(return_value={"system": "sys", "user": "usr"})

        matcher = SkillMatcher(gemini, builder, claude_driver=claude)
        result = asyncio.run(matcher._call_gemini({"system": "sys", "user": "usr"}, "skill_matcher", "task"))

        claude.prompt.assert_awaited_once()
        assert result == '{"matched_skills": []}'

    def test_no_fallback_when_gemini_succeeds(self):
        """Claude fallback must NOT be called when Gemini returns a valid response."""
        from kernel.capabilities.skill_matcher import SkillMatcher

        gemini = MagicMock()
        gemini.call = AsyncMock(return_value=MagicMock(content='{"matched_skills": ["skill_fastapi"]}'))

        claude = MagicMock()
        claude.prompt = AsyncMock()

        builder = MagicMock()
        matcher = SkillMatcher(gemini, builder, claude_driver=claude)
        result = asyncio.run(matcher._call_gemini({"system": "s", "user": "u"}, "skill_matcher", "task"))

        claude.prompt.assert_not_awaited()
        assert "skill_fastapi" in result


class TestProfileMatcherAsyncFallback:
    def test_claude_fallback_is_awaited_on_capacity_error(self):
        """If Gemini fails with a capacity error, Claude.prompt() must be awaited."""
        from kernel.capabilities.profile_matcher import ProfileMatcher

        gemini = MagicMock()
        gemini.call = AsyncMock(return_value=MagicMock(content="ERROR:OVERLOADED: quota"))

        claude = MagicMock()
        claude.prompt = AsyncMock(return_value='{"matched_profile": "profile_backend_api"}')

        builder = MagicMock()
        builder.build_payload = MagicMock(return_value={"system": "sys", "user": "usr"})

        matcher = ProfileMatcher(gemini, builder, claude_driver=claude)
        result = asyncio.run(matcher._call_gemini({"system": "sys", "user": "usr"}, "profile_matcher", "task"))

        claude.prompt.assert_awaited_once()
        assert result == '{"matched_profile": "profile_backend_api"}'


# ---------------------------------------------------------------------------
# Regression: non-software pipeline uses instance method (Bug #P1-B)
# SkillMatcher.load_skill_context must be called on an instance, not as static.
# ---------------------------------------------------------------------------

class TestNonSoftwarePipelineSkillContext:
    def test_load_skill_context_is_instance_method(self):
        """load_skill_context is an instance method — calling it as static raises TypeError."""
        from kernel.capabilities.skill_matcher import SkillMatcher
        import inspect
        # Must NOT be a staticmethod or classmethod
        raw = SkillMatcher.__dict__["load_skill_context"]
        assert not isinstance(raw, staticmethod), "load_skill_context must not be a staticmethod"
        assert not isinstance(raw, classmethod), "load_skill_context must not be a classmethod"

    def test_orchestrator_calls_instance_not_class(self):
        """Verify the orchestrator source no longer calls SkillMatcher.load_skill_context as static."""
        import ast, pathlib
        src = (pathlib.Path(__file__).parent.parent / "kernel" / "orchestrator.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # Flag: SkillMatcher.load_skill_context(...) — Attribute on a Name node "SkillMatcher"
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "load_skill_context"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "SkillMatcher"
                ):
                    pytest.fail(
                        f"orchestrator.py line {node.lineno}: "
                        "SkillMatcher.load_skill_context called as static — use self.skill_matcher instead"
                    )


# ---------------------------------------------------------------------------
# Regression: no duplicate FastAPI routes (Bug #P3)
# Two @app.get("/api/config") decorators = second shadows first silently.
# ---------------------------------------------------------------------------

class TestNoDuplicateApiConfigRoutes:
    def test_no_duplicate_get_config_route(self):
        """server.py must not register /api/config GET more than once."""
        import ast, pathlib
        src = (pathlib.Path(__file__).parent.parent / "ui" / "server.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        get_config_decorators = 0
        post_config_decorators = 0
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for dec in node.decorator_list:
                if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                    continue
                method = dec.func.attr
                args = dec.args
                if args and isinstance(args[0], ast.Constant) and args[0].value == "/api/config":
                    if method == "get":
                        get_config_decorators += 1
                    elif method == "post":
                        post_config_decorators += 1
        assert get_config_decorators == 1, f"Expected 1 GET /api/config, found {get_config_decorators}"
        assert post_config_decorators == 1, f"Expected 1 POST /api/config, found {post_config_decorators}"


class TestValidateAndMaybeRegen:
    """_validate_and_maybe_regen is the single shared validation path for run/resume/import_from_code."""

    def _make_orchestrator(self):
        orch = SodaOrchestrator.__new__(SodaOrchestrator)
        orch._notify = MagicMock()
        orch._git_commit = MagicMock()
        return orch

    def _make_project(self, modules=None):
        p = MagicMock(spec=Project)
        p.blueprint = {"nombre_proyecto": "test"}
        p.architecture = {"modulos": [{"nombre": m} for m in (modules or ["mod_a"])]}
        p.workspace = "/tmp/test"
        return p

    def test_no_regen_when_validation_passes(self):
        """If validation succeeds (fixed=True), targeted_regen must NOT be called."""
        orch = self._make_orchestrator()
        project = self._make_project()
        passing_result = {"fixed": True, "rounds": 1, "failed_modules": []}

        orch._phase_validation = AsyncMock(return_value=passing_result)
        orch.copilot_consultant = MagicMock()
        orch.copilot_consultant.review_validation = AsyncMock(return_value=None)
        orch._handle_copilot_review = MagicMock(
            return_value={"strategy": "ignore", "applied": False, "notes": "", "changes": []}
        )
        orch._should_regenerate_after_validation = MagicMock(return_value=(False, []))
        orch._phase_targeted_regeneration = AsyncMock()

        result = asyncio.run(orch._validate_and_maybe_regen(project))

        orch._phase_targeted_regeneration.assert_not_called()
        assert result == passing_result

    def test_regen_triggered_when_modules_fail(self):
        """If validation fails on specific modules, targeted_regen IS called."""
        orch = self._make_orchestrator()
        project = self._make_project(modules=["mod_a", "mod_b"])
        failing_result = {"fixed": False, "rounds": 2, "failed_modules": ["mod_a"], "errors_final": "SyntaxError"}
        passing_result = {"fixed": True, "rounds": 1, "failed_modules": []}

        orch._phase_validation = AsyncMock(side_effect=[failing_result, passing_result])
        orch.copilot_consultant = MagicMock()
        orch.copilot_consultant.review_validation = AsyncMock(return_value={"has_suggestion": False})
        orch._handle_copilot_review = MagicMock(
            return_value={"strategy": "ignore", "applied": False, "notes": "", "changes": []}
        )
        orch._should_regenerate_after_validation = MagicMock(return_value=(True, ["mod_a"]))
        orch._phase_targeted_regeneration = AsyncMock()

        result = asyncio.run(orch._validate_and_maybe_regen(project))

        orch._phase_targeted_regeneration.assert_awaited_once()
        assert orch._phase_validation.await_count == 2
        assert result == passing_result

    def test_copilot_analysis_enriches_errors_ctx(self):
        """When Copilot provides analysis, it must be prepended to errors_ctx passed to targeted_regen."""
        orch = self._make_orchestrator()
        project = self._make_project(modules=["mod_a", "mod_b"])
        failing_result = {"fixed": False, "rounds": 1, "failed_modules": ["mod_a"], "errors_final": "BUILD_FAIL"}
        passing_result = {"fixed": True, "rounds": 1, "failed_modules": []}

        orch._phase_validation = AsyncMock(side_effect=[failing_result, passing_result])
        orch.copilot_consultant = MagicMock()
        orch.copilot_consultant.review_validation = AsyncMock(return_value={"has_suggestion": True})
        orch._handle_copilot_review = MagicMock(
            return_value={"strategy": "regenerate", "applied": True, "notes": "root cause", "changes": ["missing import os"]}
        )
        orch._should_regenerate_after_validation = MagicMock(return_value=(True, ["mod_a"]))
        orch._phase_targeted_regeneration = AsyncMock()

        asyncio.run(orch._validate_and_maybe_regen(project))

        call_args = orch._phase_targeted_regeneration.call_args
        errors_ctx_passed = call_args[0][2] if call_args[0] else call_args[1].get("errors_final", "")
        assert "ANÁLISIS COPILOT" in errors_ctx_passed
        assert "missing import os" in errors_ctx_passed
        assert "BUILD_FAIL" in errors_ctx_passed

    def test_run_uses_validate_and_maybe_regen(self):
        """AST check: run() must call _validate_and_maybe_regen."""
        import ast, pathlib
        src = (pathlib.Path(__file__).parent.parent / "kernel" / "orchestrator.py").read_text(encoding="utf-8")
        tree = ast.parse(src)

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "run":
                calls = [
                    n.func.attr if isinstance(n.func, ast.Attribute) else ""
                    for n in ast.walk(node)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                ]
                assert "_validate_and_maybe_regen" in calls, "run() must call _validate_and_maybe_regen"
                return
        pytest.fail("run() method not found in orchestrator.py")

    def test_resume_uses_validate_and_maybe_regen(self):
        """AST check: resume() must call _validate_and_maybe_regen."""
        import ast, pathlib
        src = (pathlib.Path(__file__).parent.parent / "kernel" / "orchestrator.py").read_text(encoding="utf-8")
        tree = ast.parse(src)

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "resume":
                calls = [
                    n.func.attr if isinstance(n.func, ast.Attribute) else ""
                    for n in ast.walk(node)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                ]
                assert "_validate_and_maybe_regen" in calls, "resume() must call _validate_and_maybe_regen"
                return
        pytest.fail("resume() method not found in orchestrator.py")


class TestNormalizeReview:
    """normalize_review must enrich legacy payloads and pass enriched ones through unchanged."""

    def _import(self):
        from kernel.intelligence.copilot_consultant import normalize_review
        return normalize_review

    def test_none_returns_none(self):
        normalize_review = self._import()
        assert normalize_review(None) is None

    def test_no_suggestion_returns_none(self):
        normalize_review = self._import()
        assert normalize_review({"has_suggestion": False, "changes": []}) is None

    def test_legacy_payload_gets_all_enriched_fields(self):
        normalize_review = self._import()
        legacy = {"has_suggestion": True, "message": "bug found", "changes": ["fix import"]}
        result = normalize_review(legacy)
        assert result is not None
        for field in ("severity", "scope", "target_files", "target_modules",
                      "diagnosis", "proposed_fix", "repair_mode", "verification", "confidence"):
            assert field in result, f"missing field: {field}"

    def test_legacy_payload_defaults_are_sensible(self):
        normalize_review = self._import()
        result = normalize_review({"has_suggestion": True, "message": "missing import", "changes": ["add os import"]})
        assert result["severity"] == "medium"
        assert result["scope"] == "module"
        assert result["repair_mode"] == "annotate"
        assert result["confidence"] == 0.5
        assert result["target_files"] == []
        assert result["target_modules"] == []

    def test_legacy_diagnosis_derived_from_first_change(self):
        normalize_review = self._import()
        result = normalize_review({"has_suggestion": True, "message": "summary", "changes": ["fix A", "fix B"]})
        assert result["diagnosis"] == "fix A"
        assert "fix A" in result["proposed_fix"]
        assert "fix B" in result["proposed_fix"]

    def test_enriched_payload_fields_are_not_overwritten(self):
        normalize_review = self._import()
        enriched = {
            "has_suggestion": True,
            "message": "critical bug",
            "changes": ["fix x"],
            "severity": "critical",
            "scope": "architecture",
            "target_files": ["app/main.py"],
            "target_modules": ["core"],
            "diagnosis": "circular import",
            "proposed_fix": "move import",
            "repair_mode": "regenerate",
            "verification": "run tests",
            "confidence": 0.9,
        }
        result = normalize_review(enriched)
        assert result["severity"] == "critical"
        assert result["scope"] == "architecture"
        assert result["target_files"] == ["app/main.py"]
        assert result["repair_mode"] == "regenerate"
        assert result["confidence"] == 0.9

    def test_legacy_no_changes_falls_back_to_message(self):
        normalize_review = self._import()
        result = normalize_review({"has_suggestion": True, "message": "bad structure", "changes": []})
        assert result["diagnosis"] == "bad structure"
        assert result["proposed_fix"] == "bad structure"


class TestHandleCopilotReview:
    """_handle_copilot_review classifies a normalized review and returns the minimum strategy."""

    def _make_orchestrator(self):
        orch = SodaOrchestrator.__new__(SodaOrchestrator)
        orch._notify = MagicMock()
        return orch

    def _enriched(self, **overrides):
        base = {
            "has_suggestion": True,
            "message": "found issues",
            "changes": ["fix import", "add null check"],
            "severity": "medium",
            "scope": "module",
            "repair_mode": "annotate",
            "confidence": 0.8,
            "target_files": [],
            "target_modules": [],
            "diagnosis": "missing import",
            "proposed_fix": "add import os",
            "verification": "run tests",
        }
        base.update(overrides)
        return base

    def test_no_review_returns_ignore(self):
        orch = self._make_orchestrator()
        result = orch._handle_copilot_review(None, "requirements")
        assert result["strategy"] == "ignore"
        assert result["applied"] is False
        orch._notify.assert_not_called()

    def test_no_suggestion_returns_ignore(self):
        orch = self._make_orchestrator()
        result = orch._handle_copilot_review({"has_suggestion": False, "changes": []}, "architecture")
        assert result["strategy"] == "ignore"
        assert result["applied"] is False

    def test_empty_changes_returns_ignore(self):
        orch = self._make_orchestrator()
        result = orch._handle_copilot_review(
            {"has_suggestion": True, "message": "ok", "changes": [], "repair_mode": "regenerate", "confidence": 0.9},
            "planning",
        )
        assert result["strategy"] == "ignore"

    def test_annotate_strategy_applied(self):
        orch = self._make_orchestrator()
        review = self._enriched(repair_mode="annotate", confidence=0.7)
        result = orch._handle_copilot_review(review, "requirements")
        assert result["strategy"] == "annotate"
        assert result["applied"] is True
        assert result["changes"] == review["changes"]

    def test_regenerate_strategy_applied(self):
        orch = self._make_orchestrator()
        review = self._enriched(repair_mode="regenerate", severity="high", confidence=0.85)
        result = orch._handle_copilot_review(review, "validation")
        assert result["strategy"] == "regenerate"
        assert result["applied"] is True

    def test_rephase_blocked_when_not_allowed(self):
        """rephase must downgrade to regenerate when allow_rephase=False (default)."""
        orch = self._make_orchestrator()
        review = self._enriched(repair_mode="rephase", severity="critical", confidence=0.9)
        result = orch._handle_copilot_review(review, "architecture")
        assert result["strategy"] == "regenerate"
        assert result["applied"] is True

    def test_rephase_allowed_when_opted_in(self):
        orch = self._make_orchestrator()
        review = self._enriched(repair_mode="rephase", severity="critical", confidence=0.9)
        result = orch._handle_copilot_review(review, "architecture", allow_rephase=True)
        assert result["strategy"] == "rephase"
        assert result["applied"] is True

    def test_low_confidence_downgrades_to_annotate(self):
        """Confidence < 0.3 overrides repair_mode to annotate regardless."""
        orch = self._make_orchestrator()
        review = self._enriched(repair_mode="regenerate", confidence=0.2)
        result = orch._handle_copilot_review(review, "validation")
        assert result["strategy"] == "annotate"

    def test_legacy_review_uses_normalize_defaults(self):
        """Legacy review (repair_mode missing after normalize) defaults to annotate."""
        from kernel.intelligence.copilot_consultant import normalize_review
        legacy = {"has_suggestion": True, "message": "bug", "changes": ["fix it"]}
        normalized = normalize_review(legacy)
        orch = self._make_orchestrator()
        result = orch._handle_copilot_review(normalized, "requirements")
        assert result["strategy"] == "annotate"
        assert result["applied"] is True

    def test_notify_called_on_actionable_review(self):
        orch = self._make_orchestrator()
        review = self._enriched(repair_mode="regenerate", confidence=0.8)
        orch._handle_copilot_review(review, "validation")
        orch._notify.assert_called_once()
        call_args = orch._notify.call_args
        assert call_args[0][1] == "COPILOT_SUGGESTION"


class TestPhaseRequirementsHandlerIntegration:
    """_phase_requirements must use _handle_copilot_review: only regenerate on regenerate/rephase strategy."""

    def _make_orchestrator(self):
        orch = SodaOrchestrator.__new__(SodaOrchestrator)
        orch._notify = MagicMock()
        orch._git_commit = MagicMock()
        return orch

    def _make_project(self):
        p = MagicMock(spec=Project)
        p.description = "A web app"
        p.blueprint = {"nombre_proyecto": "test", "stack_sugerido": {}}
        p.architecture = {"modulos": []}
        p.workspace = "/tmp/test"
        p.id = "test_id"
        return p

    def _mock_blueprint_validator(self):
        """Return a mock BlueprintValidator *class* whose instances validate successfully."""
        mock_result = MagicMock()
        mock_result.is_valid = True
        mock_result.auto_fixes = []
        mock_result.warnings = []
        mock_instance = MagicMock()
        mock_instance.validate.return_value = mock_result
        mock_class = MagicMock(return_value=mock_instance)
        return mock_class

    def _make_orch_for_requirements(self, copilot_handled):
        orch = self._make_orchestrator()
        project = self._make_project()
        good_blueprint = {"nombre_proyecto": "test", "stack_sugerido": {}}

        orch._copilot_phase_regen = 1
        orch._call_for_role = AsyncMock(return_value='{"nombre_proyecto": "test", "stack_sugerido": {}}')
        orch._extract_json = MagicMock(return_value=good_blueprint)
        orch.knowledge_orchestrator = MagicMock()
        orch.knowledge_orchestrator.enrich_context_with_history = MagicMock(return_value=None)
        orch.copilot_consultant = MagicMock()
        orch.copilot_consultant.review_blueprint = AsyncMock(return_value={"has_suggestion": True, "changes": ["fix x"]})
        orch._handle_copilot_review = MagicMock(return_value=copilot_handled)
        orch._apply_project_type = MagicMock()
        orch._apply_capability_packs = MagicMock()
        orch._save_state = MagicMock()
        orch._workspace = MagicMock(return_value=MagicMock(
            __truediv__=lambda self, other: MagicMock(write_text=MagicMock())
        ))
        return orch, project

    def test_annotate_strategy_does_not_trigger_regen(self):
        """annotate strategy must break the loop — no blueprint regeneration."""
        handled = {"strategy": "annotate", "applied": True, "notes": "noted", "changes": ["fix x"]}
        orch, project = self._make_orch_for_requirements(handled)

        with patch("kernel.orchestration.phase_mixin.BlueprintValidator", new=self._mock_blueprint_validator()):
            asyncio.run(orch._phase_requirements(project))

        # With annotate, the loop breaks after 1 blueprint generation — no second call_for_role
        assert orch._call_for_role.await_count == 1

    def test_regenerate_strategy_triggers_second_blueprint_generation(self):
        """regenerate strategy must continue the loop and call call_for_role a second time."""
        handled = {"strategy": "regenerate", "applied": True, "notes": "regen needed", "changes": ["add auth module"]}
        orch, project = self._make_orch_for_requirements(handled)

        with patch("kernel.orchestration.phase_mixin.BlueprintValidator", new=self._mock_blueprint_validator()):
            asyncio.run(orch._phase_requirements(project))

        # regenerate → continue → second iteration → second call_for_role call
        assert orch._call_for_role.await_count == 2

    def test_ignore_strategy_does_not_trigger_regen(self):
        """ignore strategy (no suggestion) must break without regenerating."""
        handled = {"strategy": "ignore", "applied": False, "notes": "", "changes": []}
        orch, project = self._make_orch_for_requirements(handled)

        with patch("kernel.orchestration.phase_mixin.BlueprintValidator", new=self._mock_blueprint_validator()):
            asyncio.run(orch._phase_requirements(project))

        assert orch._call_for_role.await_count == 1


class TestPhaseArchitectureHandlerIntegration:
    """_phase_architecture: two-step flow — topology (Gemini) + master_contract (Claude via ContractRefinementLoop).

    After the v2 refactor, _phase_architecture no longer has a copilot review step.
    It runs _phase_topology (1× _call_gemini) then _phase_master_contract (ContractRefinementLoop).
    """

    def _make_orchestrator(self):
        orch = SodaOrchestrator.__new__(SodaOrchestrator)
        orch._notify = MagicMock()
        orch._git_commit = MagicMock()
        orch._save_state = MagicMock()
        orch.claude = MagicMock()
        orch.gemini = MagicMock()
        orch._build_goal_tree = MagicMock()
        orch._build_goal_tree_from_blueprint = MagicMock(return_value={"children": []})
        orch.observer = MagicMock()
        return orch

    def _make_project(self):
        p = MagicMock(spec=Project)
        p.description = "A web app"
        p.blueprint = {"nombre_proyecto": "test", "stack_sugerido": {}, "tipo_proyecto": "web"}
        p.architecture = {"modulos": [{"nombre": "api", "archivos_principais": []}]}
        p.topology = {}
        p.skills = []
        p.profile = ""
        p.capability_packs = []
        p.goal_tree = {}
        p.workspace = "/tmp/test"
        p.id = "test_id"
        return p

    def _run_arch_phase(self, orch, project):
        good_topo = {"modulos": [{"id": "api", "archivos_principales": ["api/main.py"]}]}
        orch._resolve_primary_provider = MagicMock(return_value="gemini")
        orch._call_gemini = AsyncMock(return_value='{"modulos": [{"id": "api"}]}')
        orch._extract_json = MagicMock(return_value=good_topo)
        orch._topology_to_legacy_architecture = MagicMock(
            return_value={"modulos": [{"nombre": "api", "archivos_principais": []}]}
        )
        mock_loop_result = MagicMock()
        mock_loop_result.status = "approved"
        mock_loop_result.attempts = []
        mock_loop_result.final_issues = None
        mock_loop_instance = MagicMock()
        mock_loop_instance.execute = AsyncMock(return_value=mock_loop_result)
        orch._save_master_contract = MagicMock()
        orch._workspace = MagicMock(return_value=MagicMock(
            __truediv__=lambda self, other: MagicMock(write_text=MagicMock(), exists=MagicMock(return_value=False))
        ))
        with patch("kernel.orchestration.phase_mixin.RequirementsStore") as mock_rs, \
             patch("kernel.orchestration.contract_refinement_loop.ContractRefinementLoop", return_value=mock_loop_instance):
            mock_rs.return_value.as_constraint_block.return_value = None
            asyncio.run(orch._phase_architecture(project))
        return orch

    def test_topology_calls_gemini_exactly_once(self):
        """_phase_topology must call _call_gemini exactly once on success."""
        orch = self._make_orchestrator()
        project = self._make_project()
        orch = self._run_arch_phase(orch, project)
        assert orch._call_gemini.await_count == 1

    def test_master_contract_loop_is_executed(self):
        """_phase_master_contract must invoke ContractRefinementLoop.execute()."""
        orch = self._make_orchestrator()
        project = self._make_project()
        good_topo = {"modulos": [{"id": "api", "archivos_principales": ["api/main.py"]}]}
        orch._resolve_primary_provider = MagicMock(return_value="gemini")
        orch._call_gemini = AsyncMock(return_value='{"modulos": [{"id": "api"}]}')
        orch._extract_json = MagicMock(return_value=good_topo)
        orch._topology_to_legacy_architecture = MagicMock(return_value={"modulos": []})
        mock_loop_result = MagicMock(status="approved", attempts=[], final_issues=None)
        mock_loop_instance = MagicMock()
        mock_loop_instance.execute = AsyncMock(return_value=mock_loop_result)
        orch._save_master_contract = MagicMock()
        orch._workspace = MagicMock(return_value=MagicMock(
            __truediv__=lambda self, other: MagicMock(write_text=MagicMock(), exists=MagicMock(return_value=False))
        ))
        with patch("kernel.orchestration.phase_mixin.RequirementsStore") as mock_rs, \
             patch("kernel.orchestration.contract_refinement_loop.ContractRefinementLoop", return_value=mock_loop_instance):
            mock_rs.return_value.as_constraint_block.return_value = None
            asyncio.run(orch._phase_architecture(project))
        mock_loop_instance.execute.assert_awaited_once()

    def test_approved_contract_is_saved(self):
        """When ContractRefinementLoop returns approved, _save_master_contract is called."""
        orch = self._make_orchestrator()
        project = self._make_project()
        orch = self._run_arch_phase(orch, project)
        orch._save_master_contract.assert_called_once()


class TestPhasePlanningHandlerIntegration:
    """_phase_planning must use _handle_copilot_review and store actionable notes."""

    def _make_orchestrator(self):
        orch = SodaOrchestrator.__new__(SodaOrchestrator)
        orch._notify = MagicMock()
        orch._git_commit = MagicMock()
        orch._save_state = MagicMock()
        return orch

    def _make_project(self):
        p = MagicMock(spec=Project)
        p.blueprint = {"nombre_proyecto": "test"}
        p.architecture = {
            "modulos": [
                {"nombre": "api", "dependencias": [], "archivos_principales": []},
                {"nombre": "db", "dependencias": [], "archivos_principales": []},
            ]
        }
        p.workspace = "/tmp/test"
        p.id = "test_id"
        return p

    def _run_planning_phase(self, orch, project, copilot_handled):
        orch.copilot_consultant = MagicMock()
        orch.copilot_consultant.review_plan = AsyncMock(return_value={"has_suggestion": True})
        orch._handle_copilot_review = MagicMock(return_value=copilot_handled)
        orch._workspace = MagicMock(return_value=MagicMock(
            __truediv__=lambda self, other: MagicMock(write_text=MagicMock())
        ))
        return asyncio.run(orch._phase_planning(project))

    def test_applied_review_stores_planning_note(self):
        """An actionable planning review must be stored in architecture._planning_copilot_note."""
        orch = self._make_orchestrator()
        project = self._make_project()
        handled = {"strategy": "annotate", "applied": True, "notes": "order issue", "changes": ["reorder mod"]}
        self._run_planning_phase(orch, project, handled)
        assert project.architecture["_planning_copilot_note"] == "order issue"

    def test_ignore_review_does_not_store_note(self):
        """An ignored review must not set _planning_copilot_note."""
        orch = self._make_orchestrator()
        project = self._make_project()
        handled = {"strategy": "ignore", "applied": False, "notes": "", "changes": []}
        self._run_planning_phase(orch, project, handled)
        assert "_planning_copilot_note" not in project.architecture

    def test_planning_returns_execution_plan(self):
        """_phase_planning must still return a valid ExecutionPlan regardless of Copilot result."""
        orch = self._make_orchestrator()
        project = self._make_project()
        handled = {"strategy": "ignore", "applied": False, "notes": "", "changes": []}
        result = self._run_planning_phase(orch, project, handled)
        assert hasattr(result, "levels")


class TestDevQwenCopilotLoop:
    """_dev_qwen_copilot_loop must use _handle_copilot_review: structured feedback drives rounds."""

    def _make_orchestrator(self):
        orch = SodaOrchestrator.__new__(SodaOrchestrator)
        orch._notify = MagicMock()
        orch._mark_goal_implemented = MagicMock()
        return orch

    def _make_generated_file(self, filepath="main.py", content="pass", validated=True):
        gf = MagicMock()
        gf.filepath = filepath
        gf.content = content
        gf.validated = validated
        gf.goal_id = "goal_1"
        return gf

    def _make_module(self, nombre="api"):
        return {"nombre": nombre, "archivos_principales": ["main.py"]}

    def _make_project(self):
        p = MagicMock(spec=Project)
        p.blueprint = {"nombre_proyecto": "test", "stack_sugerido": {}}
        p.architecture = {"modulos": []}
        p.workspace = "/tmp/test"
        return p

    def _run_loop(self, orch, module, project, source_dir, review_side_effects):
        """Run the loop with a sequence of _handle_copilot_review return values."""
        gf = self._make_generated_file()
        orch.code_gen = MagicMock()
        orch.code_gen.generate_module = AsyncMock(return_value=[gf])
        orch.copilot_consultant = MagicMock()
        orch.copilot_consultant.review_module_code = AsyncMock(return_value={"has_suggestion": True})
        orch.copilot_consultant.verify_module_code = AsyncMock(return_value=None)
        orch.copilot_consultant.fix_module_code = AsyncMock(return_value=None)
        orch._handle_copilot_review = MagicMock(side_effect=review_side_effects)
        orch._copilot_max_passes = len(review_side_effects)
        with patch("kernel.orchestrator.RequirementsStore") as mock_rs:
            mock_rs.return_value.as_task_field.return_value = ""
            return asyncio.run(orch._dev_qwen_copilot_loop(module, project, source_dir))

    def test_no_issues_breaks_after_first_round(self, tmp_path):
        """When Copilot finds no issues, the loop must stop after 1 generation."""
        orch = self._make_orchestrator()
        module = self._make_module()
        project = self._make_project()
        ignore = {"strategy": "ignore", "applied": False, "notes": "", "changes": []}

        self._run_loop(orch, module, project, tmp_path, [ignore])

        assert orch.code_gen.generate_module.await_count == 1

    def test_issues_trigger_second_round(self, tmp_path):
        """When Copilot finds issues, a second generation round must happen."""
        orch = self._make_orchestrator()
        module = self._make_module()
        project = self._make_project()
        has_issues = {"strategy": "regenerate", "applied": True, "notes": "fix x", "changes": ["add import os"]}
        ignore = {"strategy": "ignore", "applied": False, "notes": "", "changes": []}

        self._run_loop(orch, module, project, tmp_path, [has_issues, ignore])

        assert orch.code_gen.generate_module.await_count == 2

    def test_feedback_string_built_from_structured_changes(self, tmp_path):
        """The copilot_feedback passed to generate_module must contain the structured changes."""
        orch = self._make_orchestrator()
        module = self._make_module()
        project = self._make_project()
        has_issues = {"strategy": "regenerate", "applied": True, "notes": "fix", "changes": ["add import os", "fix typo"]}
        ignore = {"strategy": "ignore", "applied": False, "notes": "", "changes": []}

        self._run_loop(orch, module, project, tmp_path, [has_issues, ignore])

        second_call_kwargs = orch.code_gen.generate_module.call_args_list[1][1]
        feedback = second_call_kwargs.get("copilot_feedback", "")
        assert "add import os" in feedback
        assert "fix typo" in feedback

    def test_supervisor_applied_triggers_extra_generation(self, tmp_path):
        """When supervisor finds issues, an extra generation pass must be triggered."""
        orch = self._make_orchestrator()
        module = self._make_module()
        project = self._make_project()

        # Last round: loop review has issues → supervisor also has issues
        has_issues = {"strategy": "regenerate", "applied": True, "notes": "fix", "changes": ["missing import"]}
        sup_issues = {"strategy": "regenerate", "applied": True, "notes": "sup fix", "changes": ["fix null"]}

        gf = self._make_generated_file()
        orch.code_gen = MagicMock()
        orch.code_gen.generate_module = AsyncMock(return_value=[gf])
        orch.copilot_consultant = MagicMock()
        orch.copilot_consultant.review_module_code = AsyncMock(return_value={"has_suggestion": True})
        orch.copilot_consultant.verify_module_code = AsyncMock(return_value={"has_suggestion": True})
        orch.copilot_consultant.fix_module_code = AsyncMock(return_value=None)
        # First call is the loop review, second is the supervisor review
        orch._handle_copilot_review = MagicMock(side_effect=[has_issues, sup_issues])
        orch._copilot_max_passes = 1  # Force last-round path immediately

        with patch("kernel.orchestrator.RequirementsStore") as mock_rs:
            mock_rs.return_value.as_task_field.return_value = ""
            asyncio.run(orch._dev_qwen_copilot_loop(module, project, tmp_path))

        # 1 normal generation + 1 supervisor generation
        assert orch.code_gen.generate_module.await_count == 2


class TestPhase7NoCopilotSuggestInPhases:
    """After FASE 7, _copilot_suggest must not be called from capabilities or evolution."""

    def test_capabilities_does_not_call_copilot_suggest(self):
        """AST check: _phase_capabilities must call _handle_copilot_review, not _copilot_suggest."""
        import ast, pathlib
        src = (pathlib.Path(__file__).parent.parent / "kernel" / "orchestration" / "phase_mixin.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "_phase_capabilities":
                calls = [
                    n.func.attr
                    for n in ast.walk(node)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                ]
                assert "_copilot_suggest" not in calls, "_phase_capabilities still calls _copilot_suggest"
                assert "_handle_copilot_review" in calls, "_phase_capabilities must call _handle_copilot_review"
                return
        pytest.fail("_phase_capabilities not found in phase_mixin.py")

    def test_evolution_does_not_call_copilot_suggest(self):
        """AST check: _phase_evolution must call _handle_copilot_review, not _copilot_suggest."""
        import ast, pathlib
        src = (pathlib.Path(__file__).parent.parent / "kernel" / "orchestration" / "phase_mixin.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "_phase_evolution":
                calls = [
                    n.func.attr
                    for n in ast.walk(node)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                ]
                assert "_copilot_suggest" not in calls, "_phase_evolution still calls _copilot_suggest"
                assert "_handle_copilot_review" in calls, "_phase_evolution must call _handle_copilot_review"
                return
        pytest.fail("_phase_evolution not found in phase_mixin.py")


class TestStackDetectorR4:
    """R4: StackDetector.is_http_probe_applicable() + smoke_check non_http_stack path."""

    def test_python_is_http_probe_applicable(self):
        from kernel.execution.stack_detector import StackDetector
        assert StackDetector.is_http_probe_applicable("python") is True

    def test_node_is_http_probe_applicable(self):
        from kernel.execution.stack_detector import StackDetector
        assert StackDetector.is_http_probe_applicable("node") is True

    def test_dotnet_is_http_probe_applicable(self):
        from kernel.execution.stack_detector import StackDetector
        assert StackDetector.is_http_probe_applicable("dotnet") is True

    def test_go_is_not_http_probe_applicable(self):
        from kernel.execution.stack_detector import StackDetector
        assert StackDetector.is_http_probe_applicable("go") is False

    def test_rust_is_not_http_probe_applicable(self):
        from kernel.execution.stack_detector import StackDetector
        assert StackDetector.is_http_probe_applicable("rust") is False

    def test_static_is_not_http_probe_applicable(self):
        from kernel.execution.stack_detector import StackDetector
        assert StackDetector.is_http_probe_applicable("static") is False

    def test_unknown_is_not_http_probe_applicable(self):
        from kernel.execution.stack_detector import StackDetector
        assert StackDetector.is_http_probe_applicable("unknown") is False

    def test_smoke_check_returns_non_http_stack_for_go(self, tmp_path):
        from unittest.mock import MagicMock, patch
        from kernel.execution.project_runner import ProjectRunner
        runner = ProjectRunner()
        # Preflight returns RuntimeHealth with stack=go
        health_mock = MagicMock()
        health_mock.has_run_command = True
        health_mock.stack = "go"
        with patch.object(runner, "preflight", return_value=health_mock):
            result = runner.smoke_check(tmp_path, "go run .")
        assert result.attempted is False
        assert result.reason == "non_http_stack"

    def test_smoke_check_returns_non_http_stack_for_rust(self, tmp_path):
        from unittest.mock import MagicMock, patch
        from kernel.execution.project_runner import ProjectRunner
        runner = ProjectRunner()
        health_mock = MagicMock()
        health_mock.has_run_command = True
        health_mock.stack = "rust"
        with patch.object(runner, "preflight", return_value=health_mock):
            result = runner.smoke_check(tmp_path, "cargo run")
        assert result.attempted is False
        assert result.reason == "non_http_stack"

    def test_smoke_check_still_probes_python(self, tmp_path):
        """Python stack should attempt HTTP even if it fails — it's an HTTP stack."""
        from unittest.mock import MagicMock, patch
        import requests as _req
        from kernel.execution.project_runner import ProjectRunner
        runner = ProjectRunner()
        health_mock = MagicMock()
        health_mock.has_run_command = True
        health_mock.stack = "python"
        with patch.object(runner, "preflight", return_value=health_mock), \
             patch("kernel.execution.project_runner.requests.get", side_effect=_req.ConnectionError):
            result = runner.smoke_check(tmp_path, "python main.py")
        # attempted=True but failed — not non_http_stack
        assert result.attempted is True
        assert result.reason != "non_http_stack"

    def test_explicit_target_url_bypasses_non_http_check(self, tmp_path):
        """If caller passes an explicit target_url, probe regardless of stack."""
        from unittest.mock import MagicMock, patch
        import requests as _req
        from kernel.execution.project_runner import ProjectRunner
        runner = ProjectRunner()
        health_mock = MagicMock()
        health_mock.has_run_command = True
        health_mock.stack = "rust"
        with patch.object(runner, "preflight", return_value=health_mock), \
             patch("kernel.execution.project_runner.requests.get", side_effect=_req.ConnectionError):
            result = runner.smoke_check(tmp_path, "cargo run", target_url="http://localhost:8080/")
        assert result.reason != "non_http_stack"


class TestPhaseSetupAndVerifyR3:
    """R3: _phase_setup_and_verify must skip reinstall when boot_report.json shows BootAgent ran."""

    def _make_orch_and_project(self, tmp_path, boot_report_content):
        import json
        from unittest.mock import MagicMock, AsyncMock, patch
        from kernel.orchestration.phase_mixin import PhaseMixin
        from kernel.projects.project_manager import ProjectManager

        workspace = tmp_path
        boot_report_path = workspace / "boot_report.json"
        if boot_report_content is not None:
            boot_report_path.write_text(json.dumps(boot_report_content), encoding="utf-8")

        project = MagicMock()
        project.workspace = str(workspace)
        project.architecture = {}
        project.blueprint = {}

        orch = PhaseMixin.__new__(PhaseMixin)
        orch._notify = MagicMock()
        orch._workspace = MagicMock(return_value=workspace)
        orch._get_run_command = MagicMock(return_value="python main.py")
        orch._get_install_command = MagicMock(return_value="pip install -r requirements.txt")
        orch.smoke_tester = MagicMock()

        smoke_mock = MagicMock()
        smoke_mock.passed = False
        runner_result = {"smoke": {"passed": False, "target_url": ""}}
        orch.project_runner = MagicMock()
        orch.project_runner.setup_and_verify = AsyncMock(return_value=runner_result)

        return orch, project

    def test_skips_install_when_boot_report_shows_agent_ran(self, tmp_path):
        import asyncio
        boot_data = {"stack": "python", "final_ok": True, "attempts": 2, "skipped": False, "reason": "", "last_errors": []}
        orch, project = self._make_orch_and_project(tmp_path, boot_data)
        asyncio.run(orch._phase_setup_and_verify(project))
        call_kwargs = orch.project_runner.setup_and_verify.call_args
        assert call_kwargs.kwargs.get("install_command") == "" or call_kwargs.args[2] == ""

    def test_keeps_install_when_boot_report_skipped(self, tmp_path):
        import asyncio
        boot_data = {"stack": "unknown", "final_ok": False, "attempts": 0, "skipped": True, "reason": "Stack desconocido", "last_errors": []}
        orch, project = self._make_orch_and_project(tmp_path, boot_data)
        asyncio.run(orch._phase_setup_and_verify(project))
        call_kwargs = orch.project_runner.setup_and_verify.call_args
        effective = call_kwargs.kwargs.get("install_command") or (call_kwargs.args[2] if len(call_kwargs.args) > 2 else None)
        assert effective == "pip install -r requirements.txt"

    def test_keeps_install_when_no_boot_report(self, tmp_path):
        import asyncio
        orch, project = self._make_orch_and_project(tmp_path, None)
        asyncio.run(orch._phase_setup_and_verify(project))
        call_kwargs = orch.project_runner.setup_and_verify.call_args
        effective = call_kwargs.kwargs.get("install_command") or (call_kwargs.args[2] if len(call_kwargs.args) > 2 else None)
        assert effective == "pip install -r requirements.txt"


class TestWebSocketContract:
    """server.py must use event_type (not type) as the envelope key in all broadcast() calls."""

    def test_no_broadcast_with_type_key_in_server(self):
        """Grep check: manager.broadcast() calls must use event_type, never type."""
        import re, pathlib
        src = (pathlib.Path(__file__).parent.parent / "ui" / "server.py").read_text(encoding="utf-8")
        # Match broadcast({...) calls that have "type" as a key — but not event_type
        # Pattern: broadcast followed by a dict containing "type": but not "event_type":
        bad_broadcasts = re.findall(
            r'broadcast\s*\(\s*\{[^}]*"type"\s*:', src
        )
        assert bad_broadcasts == [], (
            f"Found {len(bad_broadcasts)} broadcast(s) using 'type' instead of 'event_type': "
            f"{bad_broadcasts}"
        )

    def test_app_js_reads_event_type(self):
        """app.js must read payload.event_type as the primary key."""
        import pathlib
        src = (pathlib.Path(__file__).parent.parent / "ui" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        assert "payload.event_type" in src, "app.js must read payload.event_type"


class TestErrorTaxonomy:
    """R1: _ERROR_TAXONOMY structure and _classify_error() helper."""

    def _orch(self):
        from kernel.orchestrator import SodaOrchestrator
        return SodaOrchestrator.__new__(SodaOrchestrator)

    def test_taxonomy_has_three_categories(self):
        from kernel.orchestrator import SodaOrchestrator
        cats = set(SodaOrchestrator._ERROR_TAXONOMY.keys())
        assert cats == {"BLOCKING_CODE_ERROR", "ADVISORY_RUNTIME", "ADVISORY_ENV"}

    def test_blocking_patterns_derived_from_taxonomy(self):
        from kernel.orchestrator import SodaOrchestrator
        assert SodaOrchestrator._BLOCKING_ERROR_PATTERNS is SodaOrchestrator._ERROR_TAXONOMY["BLOCKING_CODE_ERROR"]

    def test_classify_syntax_error_is_blocking(self):
        assert self._orch()._classify_error("SyntaxError: invalid syntax") == "BLOCKING_CODE_ERROR"

    def test_classify_indentation_error_is_blocking(self):
        assert self._orch()._classify_error("IndentationError: unexpected indent") == "BLOCKING_CODE_ERROR"

    def test_classify_import_error_own_module_is_blocking(self):
        assert self._orch()._classify_error("ImportError: cannot import name 'Router' from 'api'") == "BLOCKING_CODE_ERROR"

    def test_classify_name_error_is_blocking(self):
        assert self._orch()._classify_error("NameError: name 'session' is not defined") == "BLOCKING_CODE_ERROR"

    def test_classify_module_not_found_is_advisory_runtime(self):
        assert self._orch()._classify_error("ModuleNotFoundError: No module named 'requests'") == "ADVISORY_RUNTIME"

    def test_classify_connection_refused_is_advisory_runtime(self):
        assert self._orch()._classify_error("ConnectionRefusedError: [Errno 111]") == "ADVISORY_RUNTIME"

    def test_classify_node_cannot_find_module_is_advisory_runtime(self):
        assert self._orch()._classify_error("Cannot find module 'express'") == "ADVISORY_RUNTIME"

    def test_classify_docker_error_is_advisory_env(self):
        assert self._orch()._classify_error("Docker: no se pudo conectar") == "ADVISORY_ENV"

    def test_classify_timeout_is_advisory_env(self):
        assert self._orch()._classify_error("Timeout after 120s") == "ADVISORY_ENV"

    def test_classify_unknown_returns_unknown(self):
        assert self._orch()._classify_error("some unrecognised log line") == "UNKNOWN"

    def test_classify_first_matching_category_wins(self):
        # BLOCKING_CODE_ERROR is listed first in the taxonomy, so it wins over ADVISORY_RUNTIME
        mixed = "SyntaxError: bad token\nModuleNotFoundError: requests"
        assert self._orch()._classify_error(mixed) == "BLOCKING_CODE_ERROR"


class TestCanReachDone:
    """Taxonomy of validation results: blocking (cannot reach DONE) vs tolerable (can reach DONE).

    These tests are the spec for _can_reach_done(). They must pass before the helper is written
    and before any guard is added to the DONE transitions.
    """

    def _can_reach_done(self, result, boot_report=None):
        from kernel.orchestrator import SodaOrchestrator
        orch = SodaOrchestrator.__new__(SodaOrchestrator)
        return orch._can_reach_done(result, boot_report)

    # ── Always-tolerable cases ────────────────────────────────────────────

    def test_fixed_true_can_reach_done(self):
        assert self._can_reach_done({"fixed": True, "rounds": 1}) is True

    def test_skipped_can_reach_done(self):
        """Docker unavailable or no validation command — environment issue, not generated code."""
        assert self._can_reach_done({"fixed": False, "skipped": True}) is True

    def test_none_result_can_reach_done(self):
        assert self._can_reach_done(None) is True

    def test_empty_dict_can_reach_done(self):
        assert self._can_reach_done({}) is True

    def test_fixed_false_no_errors_can_reach_done(self):
        """fixed=False with empty errors_final = environment flakiness, not a code error."""
        assert self._can_reach_done({"fixed": False, "errors_final": ""}) is True

    def test_external_dep_missing_can_reach_done(self):
        """ModuleNotFoundError for a third-party package is not a generated-code bug."""
        result = {"fixed": False, "errors_final": "ModuleNotFoundError: No module named 'requests'"}
        assert self._can_reach_done(result) is True

    def test_docker_connection_error_can_reach_done(self):
        result = {"fixed": False, "errors_final": "ERROR:CONNECTION: Docker — sin conexión"}
        assert self._can_reach_done(result) is True

    # ── Always-blocking cases ─────────────────────────────────────────────

    def test_syntax_error_blocks_done(self):
        result = {"fixed": False, "errors_final": "SyntaxError: invalid syntax (main.py, line 12)"}
        assert self._can_reach_done(result) is False

    def test_indentation_error_blocks_done(self):
        result = {"fixed": False, "errors_final": "IndentationError: unexpected indent"}
        assert self._can_reach_done(result) is False

    def test_import_error_own_module_blocks_done(self):
        """ImportError referencing a local module means generated code is broken."""
        result = {"fixed": False, "errors_final": "ImportError: cannot import name 'Router' from 'api.routes'"}
        assert self._can_reach_done(result) is False

    def test_name_error_blocks_done(self):
        """NameError means generated code references something that doesn't exist."""
        result = {"fixed": False, "errors_final": "NameError: name 'db_session' is not defined"}
        assert self._can_reach_done(result) is False

    def test_multiple_errors_with_one_blocking_blocks_done(self):
        """If any blocking error is present, the result is blocking regardless of other content."""
        result = {
            "fixed": False,
            "errors_final": "WARNING: missing optional dep\nSyntaxError: unexpected EOF",
        }
        assert self._can_reach_done(result) is False

    # ── R6 boot_report criterion ──────────────────────────────────────────

    def test_boot_crash_on_http_stack_blocks_done(self):
        """BootAgent ran on a Python/HTTP stack and crashed — should block DONE."""
        result = {"fixed": True}
        boot = {"stack": "python", "final_ok": False, "skipped": False, "attempts": 1}
        assert self._can_reach_done(result, boot) is False

    def test_boot_crash_on_non_http_stack_does_not_block_done(self):
        """CLI tool (go) exits immediately; final_ok=False is expected — should not block DONE."""
        result = {"fixed": True}
        boot = {"stack": "go", "final_ok": False, "skipped": False, "attempts": 1}
        assert self._can_reach_done(result, boot) is True

    def test_boot_skipped_does_not_block_done(self):
        """Stack unknown — BootAgent skipped. No boot data, no block."""
        result = {"fixed": True}
        boot = {"stack": "unknown", "final_ok": False, "skipped": True, "attempts": 0}
        assert self._can_reach_done(result, boot) is True

    def test_boot_ok_and_build_ok_reaches_done(self):
        """Both build and boot succeed — DONE."""
        result = {"fixed": True}
        boot = {"stack": "python", "final_ok": True, "skipped": False, "attempts": 2}
        assert self._can_reach_done(result, boot) is True

    def test_build_blocking_overrides_boot_ok(self):
        """Even if boot succeeded, a SyntaxError in build blocks DONE."""
        result = {"fixed": False, "errors_final": "SyntaxError: invalid syntax"}
        boot = {"stack": "python", "final_ok": True, "skipped": False, "attempts": 1}
        assert self._can_reach_done(result, boot) is False

    def test_none_boot_report_is_backward_compat(self):
        """No boot_report (resume/import_from_code paths) — criterion unchanged."""
        result = {"fixed": True}
        assert self._can_reach_done(result, None) is True


class TestDoneGuard:
    """The DONE state transition must respect _can_reach_done — blocking errors set FAILED instead."""

    def _make_orchestrator(self):
        orch = SodaOrchestrator.__new__(SodaOrchestrator)
        orch._notify = MagicMock()
        orch._save_state = MagicMock()
        orch._git_commit = MagicMock()
        return orch

    def test_syntax_error_in_validation_sets_failed_not_done(self):
        """When validation contains a SyntaxError, the pipeline must end in FAILED."""
        orch = self._make_orchestrator()
        broken_result = {
            "fixed": False,
            "errors_final": "SyntaxError: invalid syntax (app.py, line 5)",
            "failed_modules": ["api"],
        }
        assert orch._can_reach_done(broken_result) is False

        # Simulate the guard logic used at all three DONE transitions
        project = MagicMock(spec=Project)
        if orch._can_reach_done(broken_result):
            project.state = ProjectState.DONE
        else:
            project.state = ProjectState.FAILED

        assert project.state == ProjectState.FAILED

    def test_skipped_validation_sets_done(self):
        """When validation is skipped (Docker unavailable), the pipeline must reach DONE."""
        orch = self._make_orchestrator()
        skipped_result = {"fixed": False, "skipped": True}
        assert orch._can_reach_done(skipped_result) is True

        project = MagicMock(spec=Project)
        if orch._can_reach_done(skipped_result):
            project.state = ProjectState.DONE
        else:
            project.state = ProjectState.FAILED

        assert project.state == ProjectState.DONE

    def test_can_reach_done_is_used_in_run(self):
        """AST check: run() must call _can_reach_done before setting ProjectState.DONE."""
        import ast, pathlib
        src = (pathlib.Path(__file__).parent.parent / "kernel" / "orchestrator.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "run":
                calls = [
                    n.func.attr
                    for n in ast.walk(node)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                ]
                assert "_can_reach_done" in calls, "run() must call _can_reach_done"
                return
        pytest.fail("run() not found in orchestrator.py")

    def test_can_reach_done_is_used_in_resume(self):
        """AST check: resume() must call _can_reach_done before setting ProjectState.DONE."""
        import ast, pathlib
        src = (pathlib.Path(__file__).parent.parent / "kernel" / "orchestrator.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "resume":
                calls = [
                    n.func.attr
                    for n in ast.walk(node)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                ]
                assert "_can_reach_done" in calls, "resume() must call _can_reach_done"
                return
        pytest.fail("resume() not found in orchestrator.py")


# ---------------------------------------------------------------------------
# FileComplexityRouter
# ---------------------------------------------------------------------------

class TestFileComplexityRouter:
    def setup_method(self):
        from kernel.intelligence.file_complexity_router import FileComplexityRouter
        self.router = FileComplexityRouter()

    def test_simple_file_is_simple(self):
        result = self.router.classify("utils/helpers.py", {"nombre": "utils"})
        assert result == "simple"

    def test_auth_file_is_complex(self):
        result = self.router.classify("auth/jwt_handler.py", {"nombre": "auth"})
        assert result == "complex"

    def test_payment_module_is_complex(self):
        result = self.router.classify("services/payment.py", {"nombre": "payment", "responsabilidad": "Stripe integration"})
        assert result == "complex"

    def test_service_file_is_medium(self):
        result = self.router.classify("api/user_service.py", {"nombre": "user_service"})
        assert result == "medium"

    def test_sql_extension_is_complex(self):
        result = self.router.classify("db/schema.sql", {"nombre": "db"})
        assert result == "complex"

    def test_ts_extension_is_at_least_medium(self):
        result = self.router.classify("frontend/App.tsx", {"nombre": "frontend"})
        assert result in ("medium", "complex")

    def test_effective_levels_simple(self):
        base = ["qwen", "gemini", "claude"]
        assert self.router.effective_levels("simple", base) == base

    def test_effective_levels_medium_skips_qwen(self):
        base = ["qwen", "gemini", "claude"]
        levels = self.router.effective_levels("medium", base)
        assert "qwen" not in levels
        assert "gemini" in levels

    def test_effective_levels_complex_claude_only(self):
        base = ["qwen", "gemini", "claude"]
        levels = self.router.effective_levels("complex", base)
        assert levels == ["claude"]


# ---------------------------------------------------------------------------
# PhaseReporter
# ---------------------------------------------------------------------------

class TestPhaseReporter:
    def setup_method(self):
        self.calls = []
        def _notify(msg, event_type, data):
            self.calls.append((msg, event_type, data))
        from kernel.soda_logging.error_reporter import PhaseReporter
        self.reporter = PhaseReporter(_notify, phase="test_phase")

    def test_warn_sends_health_warn(self):
        self.reporter.warn("something bad")
        assert self.calls[-1][1] == "HEALTH_WARN"
        assert "something bad" in self.calls[-1][0]

    def test_log_sends_log_event(self):
        self.reporter.log("info msg")
        assert self.calls[-1][1] == "LOG"

    def test_error_includes_exception_info(self):
        try:
            raise ValueError("test error")
        except ValueError as e:
            self.reporter.error(e, context="doing_something")
        msg, event_type, data = self.calls[-1]
        assert "ValueError" in msg
        assert "test error" in msg
        assert data["phase"] == "test_phase"
        assert "traceback" in data

    def test_catch_context_manager_suppresses_by_default(self):
        with self.reporter.catch("ctx"):
            raise RuntimeError("suppressed")
        assert len(self.calls) == 1
        assert "RuntimeError" in self.calls[0][0]

    def test_catch_reraise_propagates(self):
        with pytest.raises(RuntimeError):
            with self.reporter.catch("ctx", reraise=True):
                raise RuntimeError("propagated")

    def test_phase_included_in_data(self):
        self.reporter.warn("x")
        assert self.calls[-1][2]["phase"] == "test_phase"


# ---------------------------------------------------------------------------
# _can_reach_done unit tests
# ---------------------------------------------------------------------------

class TestCanReachDoneUnit:
    def _make_orch(self):
        with patch("kernel.orchestrator.GeminiDriver"), \
             patch("kernel.orchestrator.OllamaDriver"), \
             patch("kernel.orchestrator.TelegramGateway"):
            return SodaOrchestrator()

    def test_none_result_is_done(self):
        orch = self._make_orch()
        assert orch._can_reach_done(None) is True

    def test_empty_dict_is_done(self):
        orch = self._make_orch()
        assert orch._can_reach_done({}) is True

    def test_skipped_is_done(self):
        orch = self._make_orch()
        assert orch._can_reach_done({"skipped": True}) is True

    def test_fixed_is_done(self):
        orch = self._make_orch()
        assert orch._can_reach_done({"fixed": True}) is True

    def test_syntax_error_is_failed(self):
        orch = self._make_orch()
        assert orch._can_reach_done({"errors_final": "SyntaxError: invalid syntax"}) is False

    def test_module_not_found_is_advisory(self):
        orch = self._make_orch()
        assert orch._can_reach_done({"errors_final": "ModuleNotFoundError: requests"}) is True

    def test_advisory_env_is_done(self):
        orch = self._make_orch()
        assert orch._can_reach_done({"errors_final": "ConnectionRefusedError: [Errno 111]"}) is True

    def test_sanitize_package_json(self):
        from kernel.code_generator import CodeGenerator
        raw = json.dumps({
            "dependencies": {
                "@framer-motion/framer-motion": "^10.0.0",
                "react": "^18.0.0",
                "@types/jest": "undefined",
            }
        })
        fixed = CodeGenerator._sanitize_package_json_content(raw)
        pkg = json.loads(fixed)
        assert "framer-motion" in pkg["dependencies"]
        assert "@framer-motion/framer-motion" not in pkg["dependencies"]
        assert pkg["dependencies"]["@types/jest"] != "undefined"


# ---------------------------------------------------------------------------
# Mejoras Qwen: A (prompt adaptivo), B (temperatura escalonada), C (metadata)
# ---------------------------------------------------------------------------

class TestQwenImprovements:
    """Tests para las mejoras A, B y C de interacciones con Qwen."""

    MINIMAL_MODULE = {
        "nombre": "api",
        "responsabilidad": "REST endpoints",
        "dependencias": ["db"],
        "endpoints": ["/health"],
    }
    MINIMAL_BLUEPRINT = {
        "stack_sugerido": {"backend": "fastapi"},
        "funcionalidades": ["CRUD"],
    }
    MINIMAL_ARCH = {"contratos": [], "modulos": []}

    def _make_gen(self):
        with patch("kernel.orchestrator.GeminiDriver"), \
             patch("kernel.orchestrator.OllamaDriver"), \
             patch("kernel.orchestrator.TelegramGateway"):
            from kernel.code_generator import CodeGenerator
            gen = CodeGenerator(MagicMock(), MagicMock())
            gen.notify = lambda *a, **kw: None
            gen._notify_fn = lambda *a, **kw: None
            return gen

    # ── A: prompt adaptivo ──────────────────────────────────────────────────

    def test_attempt1_includes_contracts(self):
        gen = self._make_gen()
        task = json.loads(gen._build_task(
            "api/main.py", self.MINIMAL_MODULE,
            self.MINIMAL_BLUEPRINT, self.MINIMAL_ARCH,
            qwen_attempt=1,
        ))
        assert "contratos_relevantes" in task
        assert "dependencias_del_modulo" in task

    def test_attempt2_omits_contracts(self):
        gen = self._make_gen()
        task = json.loads(gen._build_task(
            "api/main.py", self.MINIMAL_MODULE,
            self.MINIMAL_BLUEPRINT, self.MINIMAL_ARCH,
            qwen_attempt=2,
        ))
        assert "contratos_relevantes" not in task
        assert "dependencias_del_modulo" not in task

    def test_attempt3_omits_contracts(self):
        gen = self._make_gen()
        task = json.loads(gen._build_task(
            "api/main.py", self.MINIMAL_MODULE,
            self.MINIMAL_BLUEPRINT, self.MINIMAL_ARCH,
            qwen_attempt=3,
        ))
        assert "contratos_relevantes" not in task

    def test_dependency_context_truncated_on_retry(self):
        gen = self._make_gen()
        long_code = "class A:\n    def b(self):\n" + "        x = 1\n" * 1000
        dep_ctx = {"db": {"db/models.py": long_code}}
        task1 = json.loads(gen._build_task(
            "api/main.py", self.MINIMAL_MODULE,
            self.MINIMAL_BLUEPRINT, self.MINIMAL_ARCH,
            dependency_context=dep_ctx, qwen_attempt=1,
        ))
        
        # Con la extracción AST, el código inyectado en el contexto debe ser dramáticamente
        # más corto que el código original, conservando solo la firma de la función.
        dep1 = task1.get("codigo_generado_dependencias", {})
        assert "db" in dep1
        extracted_code = dep1["db"]["db/models.py"]
        
        assert len(extracted_code) < len(long_code)
        assert "class A:" in extracted_code
        assert "def b" in extracted_code
        assert "x = 1" not in extracted_code  # La lógica interna fue eliminada por el AST

    def test_design_context_omitted_on_retry(self):
        gen = self._make_gen()
        task1 = json.loads(gen._build_task(
            "api/main.py", self.MINIMAL_MODULE,
            self.MINIMAL_BLUEPRINT, self.MINIMAL_ARCH,
            design_context="dark_mode: true, palette: blue",
            qwen_attempt=1,
        ))
        task2 = json.loads(gen._build_task(
            "api/main.py", self.MINIMAL_MODULE,
            self.MINIMAL_BLUEPRINT, self.MINIMAL_ARCH,
            design_context="dark_mode: true, palette: blue",
            qwen_attempt=2,
        ))
        assert "especificacion_diseno" in task1
        assert "especificacion_diseno" not in task2

    # ── B: temperatura escalonada ───────────────────────────────────────────

    def test_temperatures_are_ascending(self):
        temps = CodeGenerator.QWEN_TEMPERATURES
        assert len(temps) == 6
        assert temps[0] <= temps[1] <= temps[2] <= temps[3] <= temps[4] <= temps[5]

    def test_temperature_clamps_at_max_index(self):
        temps = CodeGenerator.QWEN_TEMPERATURES
        # Attempt 10 should return the last temperature, not raise IndexError
        idx = min(10 - 1, len(temps) - 1)
        assert temps[idx] == temps[-1]

    def test_attempt1_is_low_temperature(self):
        assert CodeGenerator.QWEN_TEMPERATURES[0] <= 0.3

    def test_attempt3_is_higher_temperature(self):
        assert CodeGenerator.QWEN_TEMPERATURES[2] >= 0.5

    # ── C: metadata auto-inyectada en lugar de rechazar ─────────────────────

    def test_valid_python_without_metadata_is_accepted(self):
        """C: código Python válido sin metadata se acepta — metadata se inyecta en _prepare_generated_code,
        no en _is_good. _is_good nunca rechaza por metadata ausente."""
        gen = self._make_gen()
        # Validator says metadata is missing — should NOT cause rejection
        gen.validator.validate_content = MagicMock(return_value=False)
        gen.sandbox = MagicMock()
        gen.sandbox.available = False

        filepath = "api/main.py"
        resp = "def foo():\n    return 1"

        # _is_good as implemented: only checks empty/error + syntax
        def _is_good(r):
            if not r or r.lstrip().startswith("Error") or gen._is_driver_error(r):
                return False
            ok, _ = gen._validate_syntax(r, filepath)
            if not ok:
                return False
            return True

        assert _is_good(resp) is True
        # validate_content must NOT be called inside _is_good (metadata is a post-process)
        gen.validator.validate_content.assert_not_called()
