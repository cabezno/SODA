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
        sc = self.skill_matcher.load_skill_context(project.skills) if project else None
        pc = self.profile_matcher.load_profile_context(project.profile) if project else None
        payload = self.builder.build_payload("claude", role, task, skills_context=sc, profile_context=pc)
        return await self.claude.prompt(payload["system"], payload["user"])

    async def _call_gemini(self, role: str, task: str, project: Optional["Project"] = None) -> str:
        sc = self.skill_matcher.load_skill_context(project.skills) if project else None
        pc = self.profile_matcher.load_profile_context(project.profile) if project else None
        payload = self.builder.build_payload("gemini", role, task, skills_context=sc, profile_context=pc)
        return await asyncio.to_thread(self.gemini.prompt, payload["system"], payload["user"])

    async def _call_ollama(self, role: str, task: str, project: Optional["Project"] = None) -> str:
        sc = self.skill_matcher.load_skill_context(project.skills) if project else None
        pc = self.profile_matcher.load_profile_context(project.profile) if project else None
        payload = self.builder.build_payload("ollama", role, task, skills_context=sc, profile_context=pc)
        return await self.ollama.prompt(payload["system"], payload["user"])

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
        self._notify(f"Project {project.id} started.", "START", {"project_id": project.id})

        await self._phase_capabilities(project)
        await self._phase_requirements(project)
        print(f"\n[CHECKPOINT 1] Blueprint ready.")
        await self._phase_architecture(project)
        print(f"\n[CHECKPOINT 2] Architecture ready.")
        plan = await self._phase_planning(project)
        print("\n[CHECKPOINT 3] Plan ready. Starting development...")
        await self._phase_development(project, plan)

        project.state = ProjectState.DONE
        self._save_state(project)
        self._notify("Pipeline complete.", "DONE", {"project_id": project.id})
        print(f"\n[OK] Pipeline complete. Workspace: {project.workspace}")
        return project


if __name__ == "__main__":
    orchestrator = SodaOrchestrator()
    asyncio.run(orchestrator.run(
        "Quiero una app web CRUD simple para gestionar una lista de tareas: "
        "crear, leer, actualizar y eliminar tareas con titulo, descripcion y estado."
    ))
