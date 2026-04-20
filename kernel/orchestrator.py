import asyncio
import json
import sys
import requests
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kernel.code_generator import CodeGenerator
from kernel.dependency_graph import DependencyGraph, ExecutionPlan
from kernel.drivers.claude_driver import ClaudeDriver
from kernel.drivers.gemini_driver import GeminiDriver
from kernel.drivers.ollama_driver import OllamaDriver
from kernel.context.context_builder import ContextBuilder
from kernel.capabilities.skill_matcher import SkillMatcher
from kernel.capabilities.profile_matcher import ProfileMatcher
from kernel.intelligence.wisdom_agent import WisdomAgent
from kernel.intelligence.goal_interpreter import GoalInterpreter
from kernel.intelligence.impact_analyzer import ImpactAnalyzer
from kernel.intelligence.context_health_monitor import ContextHealthMonitor
from kernel.intelligence.refoundation import RefoundationEngine
from kernel.capabilities.profile_evolution import ProfileEvolutionEngine
from kernel.lineage.project_lineage import ProjectLineage
from kernel.lineage.branching import BranchManager


class ProjectState(Enum):
    IDLE = "idle"
    CAPABILITIES = "capabilities"
    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    PLANNING = "planning"
    DEVELOPMENT = "development"
    INTEGRATION = "integration"
    DONE = "done"
    FAILED = "failed"
    AWAITING_CHECKPOINT = "awaiting_checkpoint"


@dataclass
class Project:
    id: str
    description: str
    state: ProjectState = ProjectState.IDLE
    workspace: Optional[Path] = None
    blueprint: dict = field(default_factory=dict)
    architecture: dict = field(default_factory=dict)
    skills: list = field(default_factory=list)
    profile: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class SodaOrchestrator:
    MAX_LOCAL_RETRIES = 3

    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.projects_dir = self.base_dir / "projects"
        self.builder = ContextBuilder()
        self.claude = ClaudeDriver()
        self.gemini = GeminiDriver()
        self.ollama = OllamaDriver(model_name="qwen2.5-coder:7b")
        self.code_gen = CodeGenerator(self.ollama, self.claude)
        self.skill_matcher = SkillMatcher(self.gemini, self.builder)
        self.profile_matcher = ProfileMatcher(self.gemini, self.builder)
        self.wisdom_agent = WisdomAgent(self.gemini, self.builder)
        self.goal_interpreter = GoalInterpreter(self.claude, self.builder)
        self.impact_analyzer = ImpactAnalyzer(self.claude, self.builder)
        self.refoundation = RefoundationEngine(self.claude, self.builder)
        self.profile_evolution = ProfileEvolutionEngine(self.gemini, self.builder)
        self.lineage = ProjectLineage(self.base_dir)
        self.branch_manager = BranchManager(self.projects_dir)
        self.health = ContextHealthMonitor(notify_fn=self._notify)
        self._ui_url = "http://127.0.0.1:8000/api/event"

    # --- UI notifications ---

    def _notify(self, message: str, event_type: str = "LOG", data: Optional[dict] = None) -> None:
        try:
            requests.post(
                self._ui_url,
                json={"event_type": event_type, "message": message, "data": data or {}},
                timeout=0.05,
            )
        except Exception:
            pass

    # --- Utilities ---

    @staticmethod
    def _extract_json(text: str) -> dict:
        import re
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {"raw": text}

    # --- Project management ---

    def _new_project(self, description: str) -> Project:
        project_id = f"proj_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        workspace = self.projects_dir / project_id
        workspace.mkdir(parents=True, exist_ok=True)
        return Project(id=project_id, description=description, workspace=workspace)

    def _save_state(self, project: Project):
        (project.workspace / "metadata.json").write_text(
            json.dumps({
                "id": project.id,
                "state": project.state.value,
                "description": project.description,
                "blueprint": project.blueprint,
                "architecture": project.architecture,
                "skills": project.skills,
                "profile": project.profile,
                "created_at": project.created_at,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # --- Model calls ---

    async def _call_claude(self, role: str, task: str, project: Optional["Project"] = None) -> str:
        import time
        sc = self.skill_matcher.load_skill_context(project.skills) if project else None
        pc = self.profile_matcher.load_profile_context(project.profile) if project else None
        payload = self.builder.build_payload("claude", role, task, skills_context=sc, profile_context=pc)
        t0 = time.monotonic()
        result = await self.claude.prompt(payload["system"], payload["user"])
        self.health.record(role, "claude", time.monotonic() - t0, result, "Error" not in result)
        return result

    async def _call_gemini(self, role: str, task: str, project: Optional["Project"] = None) -> str:
        import time
        sc = self.skill_matcher.load_skill_context(project.skills) if project else None
        pc = self.profile_matcher.load_profile_context(project.profile) if project else None
        payload = self.builder.build_payload("gemini", role, task, skills_context=sc, profile_context=pc)
        t0 = time.monotonic()
        result = await asyncio.to_thread(self.gemini.prompt, payload["system"], payload["user"])
        self.health.record(role, "gemini", time.monotonic() - t0, result, "Error" not in result)
        return result

    async def _call_ollama(self, role: str, task: str, project: Optional["Project"] = None) -> str:
        import time
        sc = self.skill_matcher.load_skill_context(project.skills) if project else None
        pc = self.profile_matcher.load_profile_context(project.profile) if project else None
        payload = self.builder.build_payload("ollama", role, task, skills_context=sc, profile_context=pc)
        t0 = time.monotonic()
        result = await self.ollama.prompt(payload["system"], payload["user"])
        self.health.record(role, "ollama", time.monotonic() - t0, result, "Error" not in result)
        return result

    async def _call_with_escalation(self, role: str, task: str, project: Project) -> str:
        for attempt in range(1, self.MAX_LOCAL_RETRIES + 1):
            print(f"  [Qwen] Attempt {attempt}/{self.MAX_LOCAL_RETRIES}...")
            result = await self._call_ollama(role, task, project)
            if "Error" not in result:
                return result
            print(f"  [!] Failed attempt {attempt}: {result[:80]}")
        print("  [^^] Escalating to Claude Sonnet...")
        result = await self._call_claude(role, task, project)
        if "Error" not in result:
            return result
        project.state = ProjectState.FAILED
        raise RuntimeError(f"All models failed for role '{role}'. Human checkpoint required.")

    # --- Phases ---

    async def _phase_wisdom(self, project: Project) -> None:
        print("\n[FASE 0.5] Wisdom — analyzing description...")
        self._notify("Wisdom Agent analyzing...", "PHASE_START", {"phase": "wisdom"})
        observations = await self.wisdom_agent.analyze(
            project.description, project.skills, project.profile
        )
        if observations:
            for obs in observations:
                print(f"  [{obs.type.upper()}] {obs.message}")
                self._notify(
                    obs.message,
                    "WISDOM",
                    {"type": obs.type, "suggestion": obs.suggestion},
                )
        else:
            self._notify("No observations — description is clear.", "WISDOM", {"type": "ok", "suggestion": ""})
        print(f"  [OK] {len(observations)} observation(s)")

    async def _phase_capabilities(self, project: Project) -> None:
        print("\n[FASE 0] Capabilities — matching skills and profile...")
        self._notify("Matching skills and profile...", "PHASE_START", {"phase": "capabilities"})
        project.state = ProjectState.CAPABILITIES

        skills = await self.skill_matcher.match(project.description)
        profile = await self.profile_matcher.match(project.description, skills)

        project.skills = skills
        project.profile = profile

        print(f"  [OK] Skills: {skills}")
        print(f"  [OK] Profile: {profile}")
        self._notify(
            f"Profile: {profile} | Skills: {', '.join(skills) or 'none'}",
            "CAPABILITIES",
            {"skills": skills, "profile": profile},
        )
        self._save_state(project)

    async def _phase_requirements(self, project: Project) -> None:
        print("\n[FASE 1] Requirements — interviewing with Claude Sonnet...")
        self._notify("Analyzing requirements...", "PHASE_START", {"phase": "requirements"})
        project.state = ProjectState.REQUIREMENTS
        response = await self._call_claude("requirements_interviewer", project.description, project)
        project.blueprint = self._extract_json(response)
        out = project.workspace / "blueprint.json"
        out.write_text(json.dumps(project.blueprint, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [OK] Blueprint -> {out}")
        self._notify("Blueprint generated.", "CHECKPOINT", {"number": 1})
        self._save_state(project)

    async def _phase_architecture(self, project: Project) -> None:
        print("\n[FASE 2] Architecture — designing with Gemini Pro...")
        self._notify("Designing architecture...", "PHASE_START", {"phase": "architecture"})
        project.state = ProjectState.ARCHITECTURE
        blueprint_str = json.dumps(project.blueprint, ensure_ascii=False)
        response = await self._call_gemini("global_architect", blueprint_str, project)
        project.architecture = self._extract_json(response)
        out = project.workspace / "architecture.json"
        out.write_text(json.dumps(project.architecture, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [OK] Architecture -> {out}")
        self._notify("Architecture generated.", "CHECKPOINT", {"number": 2})
        self._save_state(project)

    async def _phase_planning(self, project: Project) -> ExecutionPlan:
        print("\n[FASE 3] Planning — building module DAG...")
        self._notify("Building execution plan...", "PHASE_START", {"phase": "planning"})
        project.state = ProjectState.PLANNING
        modulos = project.architecture.get("modulos", [])
        if not modulos:
            raise ValueError("Architecture has no modules defined.")
        graph = DependencyGraph(modulos)
        plan = graph.build_execution_plan()
        plan_data = {"levels": plan.levels, "order": plan.order, "parallelizable": plan.parallelizable}
        out = project.workspace / "execution_plan.json"
        out.write_text(json.dumps(plan_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(graph.summary())
        print(f"  [OK] Plan -> {out}")
        self._notify("Plan ready.", "CHECKPOINT", {"number": 3, "levels": plan.levels})
        self._save_state(project)
        return plan

    async def _phase_development(self, project: Project, plan: ExecutionPlan) -> None:
        print("\n[FASE 4] Development — generating code...")
        self._notify("Generating code...", "PHASE_START", {"phase": "development"})
        project.state = ProjectState.DEVELOPMENT
        modulos_by_name = {m["nombre"]: m for m in project.architecture.get("modulos", [])}
        source_dir = project.workspace / "source"
        source_dir.mkdir(exist_ok=True)
        nombres_en_nivel = [
            [n for n in level if n in modulos_by_name]
            for level in plan.levels
        ]
        for i, level in enumerate(plan.levels):
            nombres = nombres_en_nivel[i]
            tag = f"[parallel x{len(nombres)}]" if len(nombres) > 1 else "[sequential]"
            print(f"\n  Level {i} {tag}: {' | '.join(nombres)}")
            for nombre in nombres:
                self._notify(f"Generating module: {nombre}", "MODULE_START", {"module": nombre, "level": i})
            tasks = [
                self.code_gen.generate_module(
                    modulos_by_name[nombre], project.blueprint, project.architecture,
                )
                for nombre in nombres
            ]
            results_per_module = await asyncio.gather(*tasks)
            for nombre, generated_files in zip(nombres, results_per_module):
                for gf in generated_files:
                    out = source_dir / gf.filepath
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(gf.content, encoding="utf-8")
                    self._notify(
                        f"File ready: {gf.filepath}",
                        "FILE_GENERATED",
                        {"filename": gf.filepath, "code": gf.content, "validated": gf.validated},
                    )
                self._notify(f"Module done: {nombre}", "MODULE_DONE", {"module": nombre, "level": i})
        print(f"\n  [OK] Code generated -> {source_dir}")
        self._save_state(project)

    # --- Entry point ---

    async def run(self, description: str) -> Project:
        project = self._new_project(description)
        print(f"\n{'='*55}")
        print(f"SODA — Project: {project.id}")
        print(f"Description: {description[:80]}")
        print(f"{'='*55}")
        self.lineage.record_start(project.id, project.description)
        self._notify(f"Project {project.id} started.", "START", {"project_id": project.id})

        await self._phase_capabilities(project)
        self.lineage.record_capabilities(project.id, project.skills, project.profile)
        await self._phase_wisdom(project)
        await self._phase_requirements(project)
        print(f"\n[CHECKPOINT 1] Blueprint ready.")
        await self._phase_architecture(project)
        print(f"\n[CHECKPOINT 2] Architecture ready.")
        plan = await self._phase_planning(project)
        print("\n[CHECKPOINT 3] Plan ready. Starting development...")
        await self._phase_development(project, plan)

        project.state = ProjectState.DONE
        self._save_state(project)
        self.lineage.record_complete(project.id, "done")

        await self._phase_evolution(project)

        self._notify("Pipeline complete.", "DONE", {"project_id": project.id})
        print(f"\n[OK] Pipeline complete. Workspace: {project.workspace}")
        return project


    async def _phase_evolution(self, project: Project) -> None:
        if not project.profile:
            return
        print("\n[POST] Profile Evolution — capturing learnings...")
        self._notify("Capturing project learnings...", "PHASE_START", {"phase": "evolution"})
        try:
            learnings = await self.profile_evolution.evolve(
                project.id, project.description,
                project.blueprint, project.architecture,
                project.profile, project.skills,
            )
            count = (
                len(learnings.get("patterns", []))
                + len(learnings.get("anti_patterns", []))
                + len(learnings.get("preferences", []))
            )
            print(f"  [OK] {count} learning(s) written to profile '{project.profile}'")
            self._notify(
                f"{count} learnings captured for profile '{project.profile}'",
                "EVOLUTION",
                {"profile": project.profile, "count": count, "learnings": learnings},
            )
        except Exception as e:
            print(f"  [!] Evolution failed (non-critical): {e}")

    async def refound(self, project: Project) -> Project:
        """Summarize current project and start a new one from the condensed description."""
        print("\n[REFOUND] Summarizing project for refoundation...")
        self._notify("Preparing refoundation...", "PHASE_START", {"phase": "refoundation"})
        summary = await self.refoundation.summarize(
            project.description, project.blueprint, project.architecture
        )
        new_description = summary.get("refounded_description", project.description)
        key_decisions = summary.get("key_decisions", [])
        if key_decisions:
            new_description += " Key decisions: " + "; ".join(key_decisions) + "."

        self._notify(
            f"Refoundation ready. New description: {new_description[:100]}...",
            "REFOUNDATION",
            {"parent_id": project.id, "description": new_description},
        )
        new_project = await self.run(new_description)
        self.lineage.record_start(new_project.id, new_description, parent_id=project.id)
        return new_project

    async def modify(self, project: Project, user_request: str) -> dict:
        """Interpret a post-generation change request, branch if structural, return plan+impact."""
        self._notify(f"Interpreting: {user_request[:80]}", "PHASE_START", {"phase": "modification"})

        plan = await self.goal_interpreter.interpret(
            user_request, project.architecture, project.blueprint
        )
        self._notify(
            f"Change classified as [{plan.change_type}]: {plan.impact_summary}",
            "MODIFICATION_PLAN",
            plan.to_dict(),
        )
        print(f"  [GoalInterpreter] {plan.change_type}: {plan.description}")

        report = await self.impact_analyzer.analyze(plan, project.architecture)
        self._notify(
            f"Impact [{report.risk_level}]: {report.risk_reason}",
            "IMPACT_REPORT",
            report.to_dict(),
        )
        print(f"  [ImpactAnalyzer] Risk={report.risk_level}, affects: {report.directly_affected + report.transitively_affected}")

        branch_id = None
        if self.branch_manager.should_branch(plan.change_type, plan.requires_regeneration):
            branch_name = plan.change_type
            branch_id, branch_dir = self.branch_manager.create_branch(project.id, branch_name)
            self.lineage.record_branch(project.id, branch_id, branch_name, user_request)
            self._notify(
                f"Branch created: {branch_id}",
                "BRANCH_CREATED",
                {"branch_id": branch_id, "branch_name": branch_name, "parent_id": project.id},
            )
            print(f"  [Branch] Created {branch_id} at {branch_dir}")

        return {"plan": plan.to_dict(), "impact": report.to_dict(), "branch_id": branch_id}


if __name__ == "__main__":
    orchestrator = SodaOrchestrator()
    asyncio.run(orchestrator.run(
        "Quiero una app web CRUD simple para gestionar una lista de tareas: "
        "crear, leer, actualizar y eliminar tareas con titulo, descripcion y estado."
    ))
