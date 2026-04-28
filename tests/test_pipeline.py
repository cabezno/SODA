"""
Pipeline integration tests — all AI drivers mocked, no real API calls.
Run with: python -m pytest tests/test_pipeline.py -v
"""
import asyncio
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Stub heavy optional deps before any kernel imports
for _mod in ("docker", "anthropic", "google.generativeai", "ollama",
             "telegram", "telegram.ext", "pywebview", "chromadb",
             "watchdog", "watchdog.observers", "watchdog.events",
             "github", "git"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from kernel.orchestrator import SodaOrchestrator, Project, ProjectState
from kernel.code_generator import GeneratedFile
from kernel.intelligence.wisdom_agent import WisdomObservation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_BLUEPRINT = {
    "nombre_proyecto": "Todo App",
    "descripcion": "A simple todo API",
    "funcionalidades": ["create task", "list tasks"],
    "stack_sugerido": {"backend": "fastapi", "frontend": "", "base_de_datos": "sqlite"},
    "comando_instalacion": "pip install -r requirements.txt",
    "comando_ejecucion": "uvicorn api.main:app --port 8000",
}

MINIMAL_ARCHITECTURE = {
    "modulos": [
        {
            "nombre": "api",
            "responsabilidad": "REST endpoints",
            "dependencias": [],
            "archivos_principales": ["api/main.py"],
            "endpoints": [],
        },
        {
            "nombre": "db",
            "responsabilidad": "SQLite models",
            "dependencias": [],
            "archivos_principales": ["db/models.py"],
            "endpoints": [],
        },
    ],
    "contratos": [],
}

FAKE_FILE = GeneratedFile(
    filepath="api/main.py",
    content="# generated\nprint('hello')",
    goal_id="api__api_main_py",
    validated=True,
    attempts=1,
)


@pytest.fixture
def orchestrator(tmp_path):
    """Build a SodaOrchestrator with all AI components mocked."""
    with patch("kernel.orchestrator.ClaudeDriver"), \
         patch("kernel.orchestrator.GeminiDriver"), \
         patch("kernel.orchestrator.OllamaDriver"), \
         patch("kernel.orchestrator.TelegramGateway") as MockTelegram, \
         patch("kernel.sandbox.dynamic_env.DynamicEnvironment") as MockDynEnv:

        MockTelegram.return_value.is_configured.return_value = False
        MockTelegram.return_value.should_forward.return_value = False
        mock_dyn_instance = MagicMock()
        mock_dyn_instance.ensure_venv = AsyncMock(return_value=True)
        mock_dyn_instance.install_requirements = AsyncMock(return_value=MagicMock(success=True))
        mock_dyn_instance.run_syntax_check = AsyncMock(return_value=MagicMock(success=True, errors=[]))
        mock_dyn_instance.run_tests = AsyncMock(return_value=MagicMock(success=True, stdout="", stderr=""))
        MockDynEnv.return_value = mock_dyn_instance

        orch = SodaOrchestrator()
        orch.projects_dir = tmp_path / "projects"
        orch.projects_dir.mkdir()

        # Mock AI capability components
        orch.skill_matcher.match = AsyncMock(return_value=["skill_fastapi", "skill_sqlite"])
        orch.skill_matcher.load_skill_context = MagicMock(return_value="")
        orch.profile_matcher.match = AsyncMock(return_value="profile_web_fullstack")
        orch.profile_matcher.load_profile_context = MagicMock(return_value="")
        orch.wisdom_agent.analyze = AsyncMock(return_value=[])
        orch.profile_evolution.evolve = AsyncMock(return_value={
            "patterns": ["used fastapi"], "anti_patterns": [], "preferences": []
        })
        orch.copilot_consultant.review_blueprint = AsyncMock(return_value=None)
        orch.copilot_consultant.review_architecture = AsyncMock(return_value=None)
        orch.copilot_consultant.review_capabilities = AsyncMock(return_value=None)
        orch.copilot_consultant.review_plan = AsyncMock(return_value=None)
        orch.copilot_consultant.review_module = AsyncMock(return_value=None)
        orch.copilot_consultant.review_module_code = AsyncMock(return_value=None)
        orch.copilot_consultant.verify_module_code = AsyncMock(return_value=None)
        orch.copilot_consultant.review_validation = AsyncMock(return_value=None)
        orch.copilot_consultant.review_evolution = AsyncMock(return_value=None)
        orch.user_interaction.ask = AsyncMock(return_value="listo")

        # Mock model calls at orchestrator level
        orch._call_claude = AsyncMock(return_value=json.dumps(MINIMAL_BLUEPRINT))
        orch._call_gemini = AsyncMock(return_value=json.dumps(MINIMAL_ARCHITECTURE))

        # Mock code generator
        orch.code_gen.generate_module = AsyncMock(return_value=[FAKE_FILE])

        # Mock lineage (file I/O on projects dir)
        orch.lineage.record_start = MagicMock()
        orch.lineage.record_capabilities = MagicMock()
        orch.lineage.record_complete = MagicMock()
        orch.lineage.record_branch = MagicMock()

        # Mock sandbox and validation — both create real subprocesses/venvs
        async def _noop_sandbox(*a, **kw): pass
        orch._phase_sandbox = _noop_sandbox
        orch._validate_and_maybe_regen = AsyncMock(return_value={"skipped": True, "fixed": False, "rounds": 0})

        yield orch

        # Cleanup: remove generated project workspaces to avoid filling C:\Temp
        import shutil
        projects_dir = tmp_path / "projects"
        if projects_dir.exists():
            shutil.rmtree(projects_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Phase unit tests (mocked orchestrator)
# ---------------------------------------------------------------------------

class TestPhaseCapabilities:
    def test_skills_and_profile_set(self, orchestrator, tmp_path):
        project = _new_project(orchestrator, tmp_path)
        asyncio.run(orchestrator._phase_capabilities(project))
        assert project.skills == ["skill_fastapi", "skill_sqlite"]
        assert project.profile == "profile_web_fullstack"
        assert project.state == ProjectState.CAPABILITIES

    def test_metadata_written(self, orchestrator, tmp_path):
        project = _new_project(orchestrator, tmp_path)
        asyncio.run(orchestrator._phase_capabilities(project))
        meta = json.loads((project.workspace / "metadata.json").read_text())
        assert meta["skills"] == ["skill_fastapi", "skill_sqlite"]
        assert meta["profile"] == "profile_web_fullstack"


class TestPhaseRequirements:
    def test_blueprint_saved(self, orchestrator, tmp_path):
        project = _new_project(orchestrator, tmp_path)
        project.skills = ["skill_fastapi"]
        project.profile = "profile_web_fullstack"
        asyncio.run(orchestrator._phase_requirements(project))
        assert project.blueprint == MINIMAL_BLUEPRINT
        bp = json.loads((project.workspace / "blueprint.json").read_text())
        assert bp["nombre_proyecto"] == "Todo App"

    def test_state_is_requirements(self, orchestrator, tmp_path):
        project = _new_project(orchestrator, tmp_path)
        asyncio.run(orchestrator._phase_requirements(project))
        assert project.state == ProjectState.REQUIREMENTS


class TestPhaseArchitecture:
    def test_architecture_saved(self, orchestrator, tmp_path):
        project = _new_project(orchestrator, tmp_path)
        project.blueprint = MINIMAL_BLUEPRINT
        orchestrator._call_gemini = AsyncMock(return_value=json.dumps(MINIMAL_ARCHITECTURE))
        asyncio.run(orchestrator._phase_architecture(project))
        assert len(project.architecture["modulos"]) == 2
        arch = json.loads((project.workspace / "architecture.json").read_text())
        assert arch["modulos"][0]["nombre"] == "api"

    def test_goal_tree_saved(self, orchestrator, tmp_path):
        project = _new_project(orchestrator, tmp_path)
        project.blueprint = MINIMAL_BLUEPRINT
        asyncio.run(orchestrator._phase_architecture(project))

        goal_tree = json.loads((project.workspace / "goal_tree.json").read_text())

        assert any(node["id"] == "api__api_main_py" for node in goal_tree["nodes"])
        assert project.goal_tree["root_id"].endswith("__root")

    def test_state_is_architecture(self, orchestrator, tmp_path):
        project = _new_project(orchestrator, tmp_path)
        project.blueprint = MINIMAL_BLUEPRINT
        asyncio.run(orchestrator._phase_architecture(project))
        assert project.state == ProjectState.ARCHITECTURE


class TestPhasePlanning:
    def test_plan_built_correctly(self, orchestrator, tmp_path):
        project = _new_project(orchestrator, tmp_path)
        project.architecture = MINIMAL_ARCHITECTURE
        plan = asyncio.run(orchestrator._phase_planning(project))
        assert set(plan.order) == {"api", "db"}
        assert (project.workspace / "execution_plan.json").exists()

    def test_raises_on_empty_modules(self, orchestrator, tmp_path):
        project = _new_project(orchestrator, tmp_path)
        project.architecture = {"modulos": []}
        with pytest.raises(ValueError, match="no modules"):
            asyncio.run(orchestrator._phase_planning(project))


class TestPhaseDevelopment:
    def test_source_files_written(self, orchestrator, tmp_path):
        project = _new_project(orchestrator, tmp_path)
        project.architecture = MINIMAL_ARCHITECTURE
        from kernel.dependency_graph import DependencyGraph
        plan = DependencyGraph(MINIMAL_ARCHITECTURE["modulos"]).build_execution_plan()
        asyncio.run(orchestrator._phase_development(project, plan))
        source_dir = project.workspace / "source"
        assert source_dir.exists()

    def test_generate_module_called_per_module(self, orchestrator, tmp_path):
        project = _new_project(orchestrator, tmp_path)
        project.architecture = MINIMAL_ARCHITECTURE
        from kernel.dependency_graph import DependencyGraph
        plan = DependencyGraph(MINIMAL_ARCHITECTURE["modulos"]).build_execution_plan()
        asyncio.run(orchestrator._phase_development(project, plan))
        assert orchestrator.code_gen.generate_module.call_count == 2

    def test_development_marks_generated_goals_as_implemented(self, orchestrator, tmp_path):
        project = _new_project(orchestrator, tmp_path)
        project.blueprint = MINIMAL_BLUEPRINT
        asyncio.run(orchestrator._phase_architecture(project))
        from kernel.dependency_graph import DependencyGraph
        plan = DependencyGraph(MINIMAL_ARCHITECTURE["modulos"]).build_execution_plan()

        asyncio.run(orchestrator._phase_development(project, plan))

        goal_tree = json.loads((project.workspace / "goal_tree.json").read_text())
        api_goal = next(node for node in goal_tree["nodes"] if node["id"] == "api__api_main_py")
        assert api_goal["status"] == "implemented"


class TestPhaseWisdom:
    def test_no_observations_runs_clean(self, orchestrator, tmp_path):
        project = _new_project(orchestrator, tmp_path)
        project.skills = []
        project.profile = ""
        asyncio.run(orchestrator._phase_wisdom(project))
        orchestrator.wisdom_agent.analyze.assert_called_once()

    def test_observations_forwarded(self, orchestrator, tmp_path):
        obs = WisdomObservation(obs_type="warning", message="scope is broad", suggestion="narrow it")
        orchestrator.wisdom_agent.analyze = AsyncMock(return_value=[obs])
        project = _new_project(orchestrator, tmp_path)
        asyncio.run(orchestrator._phase_wisdom(project))  # should not raise


# ---------------------------------------------------------------------------
# Full pipeline run()
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def test_run_reaches_done(self, orchestrator, tmp_path):
        orchestrator.projects_dir = tmp_path / "projects"
        orchestrator.projects_dir.mkdir(exist_ok=True)
        project = asyncio.run(orchestrator.run("Build a simple todo API"))
        assert project.state == ProjectState.DONE
        assert project.project_type == "software"

    def test_run_creates_workspace(self, orchestrator, tmp_path):
        orchestrator.projects_dir = tmp_path / "projects"
        orchestrator.projects_dir.mkdir(exist_ok=True)
        project = asyncio.run(orchestrator.run("Build a simple todo API"))
        assert project.workspace.exists()
        assert (project.workspace / "metadata.json").exists()
        assert (project.workspace / "goal_tree.json").exists()
        meta = json.loads((project.workspace / "metadata.json").read_text())
        assert meta["project_type"] == "software"
        assert meta["capability_packs"] == []
        assert meta["intensity_level"] in {"low", "medium", "high"}
        assert "reference_report" in meta

    def test_run_detects_capability_packs_from_description(self, orchestrator, tmp_path):
        orchestrator.projects_dir = tmp_path / "projects"
        orchestrator.projects_dir.mkdir(exist_ok=True)
        project = asyncio.run(orchestrator.run("Build a simple todo API with login and JWT authentication"))

        meta = json.loads((project.workspace / "metadata.json").read_text())
        assert project.capability_packs == ["auth_complete"]
        assert meta["capability_packs"] == ["auth_complete"]

    def test_run_calls_lineage(self, orchestrator, tmp_path):
        orchestrator.projects_dir = tmp_path / "projects"
        orchestrator.projects_dir.mkdir(exist_ok=True)
        project = asyncio.run(orchestrator.run("Build a simple todo API"))
        orchestrator.lineage.record_start.assert_called_once()
        orchestrator.lineage.record_complete.assert_called_once()

    def test_run_invokes_evolution(self, orchestrator, tmp_path):
        orchestrator.projects_dir = tmp_path / "projects"
        orchestrator.projects_dir.mkdir(exist_ok=True)
        asyncio.run(orchestrator.run("Build a simple todo API"))
        orchestrator.profile_evolution.evolve.assert_called_once()


# ---------------------------------------------------------------------------
# modify() flow
# ---------------------------------------------------------------------------

class TestModifyFlow:
    def setup_method(self):
        from unittest.mock import MagicMock
        from kernel.intelligence.goal_interpreter import ModificationPlan
        from kernel.intelligence.impact_analyzer import ImpactReport

        self.mock_plan = MagicMock(spec=ModificationPlan)
        self.mock_plan.change_type = "cosmetic"
        self.mock_plan.requires_regeneration = False
        self.mock_plan.description = "rename variable"
        self.mock_plan.impact_summary = "minimal"
        self.mock_plan.to_dict.return_value = {"change_type": "cosmetic"}

        self.mock_report = MagicMock(spec=ImpactReport)
        self.mock_report.risk_level = "low"
        self.mock_report.risk_reason = "no structural impact"
        self.mock_report.directly_affected = []
        self.mock_report.transitively_affected = []
        self.mock_report.to_dict.return_value = {"risk_level": "low"}

    def test_cosmetic_change_no_branch(self, orchestrator, tmp_path):
        orchestrator.goal_interpreter.interpret = AsyncMock(return_value=self.mock_plan)
        orchestrator.impact_analyzer.analyze = AsyncMock(return_value=self.mock_report)
        project = _new_project(orchestrator, tmp_path)
        result = asyncio.run(orchestrator.modify(project, "rename var x to count"))
        assert result["branch_id"] is None
        assert result["plan"]["change_type"] == "cosmetic"

    def test_structural_change_creates_branch(self, orchestrator, tmp_path):
        self.mock_plan.change_type = "structural"
        self.mock_plan.requires_regeneration = True
        orchestrator.goal_interpreter.interpret = AsyncMock(return_value=self.mock_plan)
        orchestrator.impact_analyzer.analyze = AsyncMock(return_value=self.mock_report)

        project = _new_project(orchestrator, tmp_path)
        (project.workspace / "source").mkdir()
        (project.workspace / "metadata.json").write_text(
            json.dumps({"id": project.id, "state": "done"}), encoding="utf-8"
        )
        result = asyncio.run(orchestrator.modify(project, "add auth module"))
        assert result["branch_id"] is not None

    def test_modify_returns_plan_and_impact(self, orchestrator, tmp_path):
        orchestrator.goal_interpreter.interpret = AsyncMock(return_value=self.mock_plan)
        orchestrator.impact_analyzer.analyze = AsyncMock(return_value=self.mock_report)
        project = _new_project(orchestrator, tmp_path)
        result = asyncio.run(orchestrator.modify(project, "any change"))
        assert "plan" in result
        assert "impact" in result

    def test_modify_returns_reference_report_and_persists_it(self, orchestrator, tmp_path):
        orchestrator.goal_interpreter.interpret = AsyncMock(return_value=self.mock_plan)
        orchestrator.impact_analyzer.analyze = AsyncMock(return_value=self.mock_report)
        project = _new_project(orchestrator, tmp_path)

        result = asyncio.run(
            orchestrator.modify(project, "make it behave like https://example.com/dashboard")
        )

        saved = json.loads((project.workspace / "metadata.json").read_text(encoding="utf-8"))
        assert result["reference_report"]["total_urls"] == 1
        assert result["reference_report"]["broken_candidates"] == 1
        assert saved["reference_report"]["broken_candidates"] == 1


# ---------------------------------------------------------------------------
# DONE guard — validation blocking vs tolerable
# ---------------------------------------------------------------------------

class TestDoneGuardPipeline:
    """run() must end in FAILED when validation has blocking errors, DONE otherwise."""

    def test_run_sets_failed_on_blocking_validation(self, orchestrator, tmp_path):
        """SyntaxError in errors_final must prevent DONE and set FAILED."""
        orchestrator.projects_dir = tmp_path / "projects"
        orchestrator.projects_dir.mkdir(exist_ok=True)
        orchestrator._validate_and_maybe_regen = AsyncMock(return_value={
            "fixed": False,
            "errors_final": "SyntaxError: invalid syntax (api/main.py, line 5)",
            "failed_modules": ["api"],
            "rounds": 2,
        })
        project = asyncio.run(orchestrator.run("Build a simple todo API"))
        assert project.state == ProjectState.FAILED

    def test_run_reaches_done_on_skipped_validation(self, orchestrator, tmp_path):
        """Skipped validation (Docker unavailable) must still allow DONE."""
        orchestrator.projects_dir = tmp_path / "projects"
        orchestrator.projects_dir.mkdir(exist_ok=True)
        orchestrator._validate_and_maybe_regen = AsyncMock(return_value={
            "fixed": False, "skipped": True
        })
        project = asyncio.run(orchestrator.run("Build a simple todo API"))
        assert project.state == ProjectState.DONE

    def test_run_reaches_done_on_fixed_validation(self, orchestrator, tmp_path):
        """fixed=True must reach DONE."""
        orchestrator.projects_dir = tmp_path / "projects"
        orchestrator.projects_dir.mkdir(exist_ok=True)
        orchestrator._validate_and_maybe_regen = AsyncMock(return_value={
            "fixed": True, "rounds": 1
        })
        project = asyncio.run(orchestrator.run("Build a simple todo API"))
        assert project.state == ProjectState.DONE

    def test_lineage_not_recorded_done_when_build_broken(self, orchestrator, tmp_path):
        """lineage.record_complete must NOT be called when the pipeline ends in FAILED."""
        orchestrator.projects_dir = tmp_path / "projects"
        orchestrator.projects_dir.mkdir(exist_ok=True)
        orchestrator._validate_and_maybe_regen = AsyncMock(return_value={
            "fixed": False,
            "errors_final": "NameError: name 'db' is not defined",
            "failed_modules": ["api"],
        })
        asyncio.run(orchestrator.run("Build a simple todo API"))
        orchestrator.lineage.record_complete.assert_not_called()

    def test_evolution_still_runs_when_build_broken(self, orchestrator, tmp_path):
        """_phase_evolution must run even when the pipeline ends in FAILED."""
        orchestrator.projects_dir = tmp_path / "projects"
        orchestrator.projects_dir.mkdir(exist_ok=True)
        orchestrator._validate_and_maybe_regen = AsyncMock(return_value={
            "fixed": False,
            "errors_final": "IndentationError: unexpected indent",
            "failed_modules": ["api"],
        })
        asyncio.run(orchestrator.run("Build a simple todo API"))
        orchestrator.profile_evolution.evolve.assert_called_once()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_project(orch: SodaOrchestrator, tmp_path: Path) -> Project:
    ws = tmp_path / "proj_test"
    ws.mkdir(exist_ok=True)
    return Project(id="proj_test", description="test project", workspace=ws)
