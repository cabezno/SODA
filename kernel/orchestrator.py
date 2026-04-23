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
from kernel.drivers.provider_hub import AIProviderHub
from kernel.context.context_builder import ContextBuilder
from kernel.capabilities.capability_packs import CapabilityPackRegistry
from kernel.capabilities.skill_matcher import SkillMatcher
from kernel.capabilities.profile_matcher import ProfileMatcher
from kernel.capabilities.skill_manager import SkillManager
from kernel.capabilities.profile_manager import ProfileManager
from kernel.intelligence.wisdom_agent import WisdomAgent
from kernel.intelligence.goal_interpreter import GoalInterpreter
from kernel.intelligence.impact_analyzer import ImpactAnalyzer
from kernel.intelligence.reference_analyzer import ReferenceAnalyzer
from kernel.intelligence.context_health_monitor import ContextHealthMonitor
from kernel.intelligence.refoundation import RefoundationEngine
from kernel.capabilities.profile_evolution import ProfileEvolutionEngine
from kernel.lineage.project_lineage import ProjectLineage
from kernel.lineage.branching import BranchManager
from kernel.intelligence.copilot_consultant import CopilotConsultant
from kernel.integrity.goal_integrity_validator import GoalIntegrityValidator
from kernel.knowledge.chromadb_manager import ChromaDBManager, KnowledgeOrchestrator
from kernel.execution.docker_sandbox import DockerSandbox
from kernel.communication.telegram_gateway import TelegramGateway
from kernel.communication.user_interaction import get_gateway
from kernel.execution.project_runner import ProjectRunner
from kernel.execution.smoke_tester import SmokeTester
from kernel.execution.service_orchestrator import ServiceOrchestrator
from kernel.outputs.output_generator import OutputGenerator
from kernel.git_manager import GitManager
from kernel.goals.goal_tree import GoalTree
from kernel.orchestration.intensity_orchestrator import IntensityOrchestrator
from kernel.drivers.driver_factory import build_driver
from kernel.projects.project_types import ProjectTypeRegistry
from kernel.projects.project_manager import ProjectManager
from kernel.vision.vision_capturer import VisionCapturer
from kernel.vision.visual_inspector import VisualInspector
from kernel.validation.architecture_validator import ArchitectureValidator
from kernel.validation.blueprint_validator import BlueprintValidator
from kernel.validation.import_dependency_validator import ImportDependencyValidator
from kernel.validation.api_contract_enforcer import APIContractEnforcer
from kernel.security.security_reviewer import SecurityReviewer
from kernel.testing.test_generator import TestGenerator
from kernel.execution.boot_agent import BootAgent
from kernel.learning.behavior_observer import BehaviorObserver
from kernel.learning.knowledge_base import KnowledgeBase
from kernel.learning.local_ai_coach import LocalAICoach
from kernel.design.ui_design_agent import UIDesignAgent
from kernel.design.design_context_injector import DesignContextInjector
from kernel.audit.language_auditor import LanguageAuditor
from kernel.external.web_researcher import WebResearcher
from kernel.watchdog_mgr import ProjectWatchdog
from kernel.persistence.requirements_store import RequirementsStore
from kernel.monitoring.performance_tracker import PerformanceTracker
from kernel.intelligence.conformance_verifier import ConformanceVerifier


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
    project_type: str = ""
    capability_packs: list = field(default_factory=list)
    goal_tree: dict = field(default_factory=dict)
    intensity_level: str = ""
    reference_report: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


COPILOT_TEMPERATURE = {
    #            code_passes  phase_regen
    "baja":  {"code_passes": 1, "phase_regen": 0},
    "media": {"code_passes": 3, "phase_regen": 1},
    "alta":  {"code_passes": 5, "phase_regen": 2},
}


class SodaOrchestrator:
    MAX_LOCAL_RETRIES = 3

    def __init__(self, copilot_temperature: str = "media"):
        temp = copilot_temperature.lower().strip() if copilot_temperature else "media"
        cfg = COPILOT_TEMPERATURE.get(temp, COPILOT_TEMPERATURE["media"])
        self._copilot_max_passes = cfg["code_passes"]
        self._copilot_phase_regen = cfg["phase_regen"]
        self._copilot_temperature = temp
        self.base_dir = Path(__file__).resolve().parent.parent
        self.projects_dir = self.base_dir / "projects"
        self.builder = ContextBuilder()
        self.claude = ClaudeDriver()
        self.gemini = GeminiDriver()
        self.ollama = OllamaDriver()  # auto-selects 14b > 7b based on what's pulled
        self.ai_hub = AIProviderHub(
            providers={
                "claude": self.claude,
                "gemini": self.gemini,
                "ollama": self.ollama,
            },
            routes=self._load_ai_routing(),
        )
        self._phase_provider_map = self._load_phase_provider_map()
        self.code_gen = CodeGenerator(self.ollama, self.claude, self.gemini)
        self.capability_pack_registry = CapabilityPackRegistry()
        self.skill_matcher = SkillMatcher(self.gemini, self.builder, claude_driver=self.claude)
        self.profile_matcher = ProfileMatcher(self.gemini, self.builder, claude_driver=self.claude)
        self.skill_manager = SkillManager(self.skill_matcher)
        self.profile_manager = ProfileManager(self.profile_matcher)
        self.wisdom_agent = WisdomAgent(self.gemini, self.builder, claude_driver=self.claude)
        self.goal_interpreter = GoalInterpreter(self.claude, self.builder)
        self.goal_interpreter.ask_fn = self._ask_user_clarification
        self.impact_analyzer = ImpactAnalyzer(self.claude, self.builder)
        self.reference_analyzer = ReferenceAnalyzer()
        self.refoundation = RefoundationEngine(self.claude, self.builder)
        self.profile_evolution = ProfileEvolutionEngine(self.gemini, self.builder, claude_driver=self.claude)
        self.profile_evolution.notify_fn = self._notify
        self.copilot_consultant = CopilotConsultant(self.claude, self.builder)
        self.chroma_manager = ChromaDBManager()
        self.knowledge_orchestrator = KnowledgeOrchestrator(self.chroma_manager)
        self.goal_validator = GoalIntegrityValidator()
        self.docker_sandbox = DockerSandbox()
        self.lineage = ProjectLineage(self.base_dir)
        self.branch_manager = BranchManager(self.projects_dir)
        self.project_runner = ProjectRunner()
        self.smoke_tester = SmokeTester()
        self.service_orchestrator = ServiceOrchestrator()
        self.output_generator = OutputGenerator()
        self.intensity = IntensityOrchestrator()
        self.project_types = ProjectTypeRegistry()
        self.project_manager = ProjectManager(self.base_dir)
        self.git_manager = GitManager()
        self.health = ContextHealthMonitor(notify_fn=self._notify)
        self.telegram = TelegramGateway()
        self.user_interaction = get_gateway()
        self.vision_capturer = VisionCapturer()
        self.visual_inspector = VisualInspector(gemini_driver=self.gemini)
        self.web_researcher = WebResearcher()
        self.import_validator = ImportDependencyValidator(notify_fn=self._notify)
        self.api_enforcer = APIContractEnforcer(notify_fn=self._notify)
        self.security_reviewer = SecurityReviewer(
            claude_driver=self.claude,
            context_builder=self.builder,
            notify_fn=self._notify,
        )
        self.test_generator = TestGenerator(
            claude_driver=self.claude,
            ollama_driver=self.ollama,
            context_builder=self.builder,
            notify_fn=self._notify,
        )
        self.boot_agent = BootAgent(
            claude_driver=self.claude,
            gemini_driver=self.gemini,
            context_builder=self.builder,
            notify_fn=self._notify,
        )
        self.ui_design_agent = UIDesignAgent()
        # Learning system — observer + knowledge base + coach for local AI
        self.observer = BehaviorObserver()
        self.knowledge_base = KnowledgeBase()
        self.coach = LocalAICoach(self.knowledge_base)
        self.code_gen.observer = self.observer
        self.code_gen.coach = self.coach
        self._ui_url = "http://127.0.0.1:8000/api/event"
        self.code_gen.notify = self._notify
        self.perf_tracker = PerformanceTracker()
        self.code_gen.tracker = self.perf_tracker
        self.conformance_verifier = ConformanceVerifier(self.claude, self.perf_tracker)
        self._load_custom_providers()

    def _load_custom_providers(self) -> None:
        """Register any custom AI providers saved in soda_config.json into ai_hub."""
        config_path = self.base_dir / "soda_config.json"
        try:
            if not config_path.exists():
                return
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            for prov in cfg.get("custom_providers", []):
                name = (prov.get("name") or "").strip().lower()
                api_key = prov.get("api_key", "")
                model = prov.get("model", "")
                base_url = prov.get("base_url", "")
                driver_type = prov.get("driver_type", "")
                if not name or not api_key:
                    continue
                driver = build_driver(name, api_key, model, base_url or None, driver_type or None)
                self.ai_hub.register(name, driver)
        except Exception as e:
            print(f"[WARN] Could not load custom providers: {e}")

    # --- UI notifications ---

    def _notify(self, message: str, event_type: str = "LOG", data: Optional[dict] = None) -> None:
        payload = {"event_type": event_type, "message": message, "data": data or {}}
        # Broadcast to WebSocket clients — must not block the event loop
        try:
            import asyncio as _asyncio
            loop = _asyncio.get_running_loop()
            # We're inside the async event loop: schedule broadcast as a task (zero blocking)
            from ui.websocket_handler import manager as _ws_manager
            loop.create_task(_ws_manager.broadcast(payload))
        except RuntimeError:
            # Not inside an async context — send via HTTP in a background thread
            import threading
            def _post():
                try:
                    requests.post(self._ui_url, json=payload, timeout=2.0)
                except Exception:
                    pass
            threading.Thread(target=_post, daemon=True).start()
        except Exception:
            pass
        # Forward key events to Telegram (fire-and-forget via httpx — no Bot event-loop conflict)
        if self.telegram.should_forward(event_type) and self.telegram.is_configured():
            import asyncio as _asyncio
            formatted = self.telegram.format_event(event_type, message, data)
            try:
                loop = _asyncio.get_running_loop()
                loop.create_task(self.telegram.send_event(event_type, formatted, data))
            except RuntimeError:
                # Not inside a running loop — fire in background thread
                import threading
                def _tg_send():
                    try:
                        _asyncio.run(self.telegram.send_event(event_type, formatted, data))
                    except Exception:
                        pass
                threading.Thread(target=_tg_send, daemon=True).start()
            except Exception:
                pass

    # --- Utilities ---

    async def _ask_user_clarification(self, question: str, options: list) -> str:
        """Ask the user a clarification question via the UI interaction gateway and return their answer."""
        options_text = ""
        if options:
            opts = "\n".join(f"  {i+1}. {o}" for i, o in enumerate(options))
            options_text = f"\n\nOpciones:\n{opts}"
        self._notify(
            f"{question}{options_text}",
            "USER_QUESTION",
            {"question": question, "options": options},
        )
        try:
            answer = await self.user_interaction.ask(question, self._notify)
            return answer or ""
        except Exception:
            return ""

    def _git_commit(self, project: Project, message: str) -> None:
        """Auto-commit changes per phase."""
        try:
            workspace = self._workspace(project)
            self.git_manager.commit_all(workspace, message)
            self._notify(f"Commit: {message}", "LOG", {})
        except Exception as e:
            self._notify(f"Git commit failed (non-critical): {e}", "LOG", {})

    @staticmethod
    def _extract_json(text: str) -> dict:
        import re

        def _try(s: str) -> dict | None:
            try:
                result = json.loads(s.strip())
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, ValueError):
                pass
            return None

        # 1. Direct parse
        r = _try(text)
        if r is not None:
            return r

        # 2. Strip code fences — greedy content match to capture the full object
        stripped = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped.strip())
        r = _try(stripped)
        if r is not None:
            return r

        # 3. Find the outermost {...} using balanced-brace walk
        start = text.find("{")
        if start != -1:
            depth = 0
            in_str = False
            escape = False
            for i, ch in enumerate(text[start:], start):
                if escape:
                    escape = False
                    continue
                if ch == "\\" and in_str:
                    escape = True
                    continue
                if ch == '"' and not escape:
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        r = _try(text[start: i + 1])
                        if r is not None:
                            return r
                        break

        # 4. Greedy regex fallback
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            r = _try(match.group(0))
            if r is not None:
                return r

        return {"raw": text}

    # --- Project management ---

    def _new_project(self, description: str, project_name: Optional[str] = None) -> Project:
        project_id = project_name or f"proj_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        workspace = self.projects_dir / project_id
        if workspace.exists():
            project_id = f"{project_id}_{datetime.now().strftime('%H%M%S')}"
            workspace = self.projects_dir / project_id
        workspace.mkdir(parents=True, exist_ok=True)
        # Keep ProjectManager in sync (update its projects_dir in case it was patched)
        self.project_manager.projects_dir = self.projects_dir
        project = Project(id=project_id, description=description, workspace=workspace)
        RequirementsStore(workspace).save(description, project_name or project_id)
        try:
            self.project_manager.save(project_id, {
                "id": project_id,
                "description": description,
                "state": "idle",
                "created_at": project.created_at,
                "workspace": str(workspace),
            })
        except Exception:
            pass
        return project

    @staticmethod
    def _workspace(project: Project) -> Path:
        if project.workspace is None:
            raise ValueError("Project workspace is not initialized")
        return project.workspace

    def _save_state(self, project: Project):
        data = {
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
            "workspace": str(project.workspace) if project.workspace else "",
        }
        workspace = self._workspace(project)
        (workspace / "metadata.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        # Keep ProjectManager index in sync
        try:
            self.project_manager.save(project.id, data)
        except Exception:
            pass

    def _save_goal_tree(self, project: Project) -> None:
        if not project.goal_tree:
            return
        out = self._workspace(project) / "goal_tree.json"
        out.write_text(json.dumps(project.goal_tree, indent=2, ensure_ascii=False), encoding="utf-8")

    def _build_goal_tree(self, project: Project) -> None:
        if not project.architecture.get("modulos"):
            project.goal_tree = {}
            return
        tree = GoalTree.from_architecture(project.id, project.description, project.architecture)
        project.goal_tree = tree.to_dict()
        self._save_goal_tree(project)
        self._notify(
            "Goal Tree actualizado.",
            "LOG",
            {
                "phase": "goal_tree",
                "project_id": project.id,
                "total_goals": len(project.goal_tree.get("nodes", [])),
            },
        )

    def _mark_goal_implemented(self, project: Project, goal_id: str, filepath: str) -> None:
        if not project.goal_tree:
            return
        tree = GoalTree.from_dict(project.goal_tree)
        if goal_id not in tree.nodes:
            return
        tree.mark_implemented(goal_id, filepath)
        project.goal_tree = tree.to_dict()

    def _apply_intensity_level(self, project: Project) -> None:
        level = self.intensity.choose_level(project.description)
        if project.intensity_level == level:
            return
        project.intensity_level = level
        self._save_state(project)
        self._notify(
            f"Nivel de intensidad asignado: {level}",
            "LOG",
            {"phase": "intensity", "project_id": project.id, "intensity_level": level},
        )

    def _apply_project_type(self, project: Project) -> None:
        project_type = self.project_types.classify(project.description)
        if project.project_type == project_type:
            return
        project.project_type = project_type
        self._save_state(project)
        details = self.project_types.get_type(project_type)
        self._notify(
            f"Tipo de proyecto detectado: {details['name']}",
            "LOG",
            {
                "phase": "project_type",
                "project_id": project.id,
                "project_type": project_type,
                "default_checkpoints": details["default_checkpoints"],
                "typical_outputs": details["typical_outputs"],
            },
        )

    def _apply_capability_packs(self, project: Project) -> None:
        capability_packs = self.capability_pack_registry.recommend(project.description)
        if project.capability_packs == capability_packs:
            return
        project.capability_packs = capability_packs
        self._save_state(project)
        self._notify(
            f"Capability packs detectados: {', '.join(capability_packs) or 'ninguno'}",
            "LOG",
            {
                "phase": "capability_packs",
                "project_id": project.id,
                "capability_packs": capability_packs,
            },
        )

    def _augment_task_with_project_context(self, task: str, project: Optional[Project]) -> str:
        if not project or not hasattr(self, "project_types") or not hasattr(self, "capability_pack_registry"):
            return task

        project_type_key = project.project_type or self.project_types.classify(project.description)
        details = self.project_types.get_type(project_type_key)
        capability_packs = project.capability_packs or self.capability_pack_registry.recommend(project.description)

        capability_pack_block = ""
        if capability_packs:
            pack_lines = []
            for pack_key in capability_packs:
                pack = self.capability_pack_registry.get_pack(pack_key)
                pack_lines.append(
                    f"- {pack['key']}: {pack['description']} | includes: {', '.join(pack['includes'])}"
                )
            capability_pack_block = "[CAPABILITY_PACKS]\n" + "\n".join(pack_lines) + "\n"

        return (
            f"{task}\n\n"
            "[PROJECT_TYPE_CONTEXT]\n"
            f"- key: {details['key']}\n"
            f"- name: {details['name']}\n"
            f"- description: {details['description']}\n"
            f"- default_checkpoints: {', '.join(details['default_checkpoints'])}\n"
            f"- typical_outputs: {', '.join(details['typical_outputs'])}\n"
            f"{capability_pack_block}"
            "Use this context to adapt the deliverable format, checkpoints, and final outputs."
        )

    def _build_reference_report(self, text: str) -> dict:
        report = self.reference_analyzer.analyze(text)
        return {
            "total_urls": report.total_urls,
            "unique_urls": report.unique_urls,
            "broken_candidates": report.broken_candidates,
        }

    # --- Model calls ---

    def _check_driver_error(self, result: str, ai_name: str, role: str) -> None:
        """Broadcast AI_ERROR if the driver returned a structured error."""
        if result.startswith("ERROR:"):
            rest = result[6:]
            code, msg = rest.split(":", 1) if ":" in rest else ("UNKNOWN", rest)
            self._notify(msg.strip(), "AI_ERROR", {"ai": ai_name, "error_code": code.strip(), "role": role})

    # Transient errors that should trigger retry (quota auto-reloads, server overload, network blip)
    _TRANSIENT_PREFIXES = ("ERROR:RATE_LIMIT:", "ERROR:OVERLOADED:", "ERROR:CONNECTION:")
    _RETRY_WAITS = [5, 15, 30, 60, 90, 120, 120, 120]  # seconds between retries

    async def _retry_transient(self, provider: str, call_fn) -> str:
        """Call call_fn(); if it returns a transient error, wait and retry up to 8 times."""
        def _str(r) -> str:
            return r.content if hasattr(r, "content") else str(r)

        result = await call_fn()
        for attempt, wait in enumerate(self._RETRY_WAITS):
            if not any(_str(result).startswith(p) for p in self._TRANSIENT_PREFIXES):
                return _str(result)
            self._notify(
                f"[{provider}] Cuota/límite temporal — reintentando en {wait}s (intento {attempt + 1}/{len(self._RETRY_WAITS)})",
                "LOG", {},
            )
            await asyncio.sleep(wait)
            result = await call_fn()
        return _str(result)

    async def _call_claude(self, role: str, task: str, project: Optional["Project"] = None) -> str:
        import time
        sc = self.skill_manager.load_context(project.skills, role=role) if project else None
        pc = self.profile_manager.load_context(project.profile) if project else None
        rag = self.knowledge_orchestrator.query(project.description, role=role) if project else None
        task = self._augment_task_with_project_context(task, project)
        payload = self.builder.build_payload("claude", role, task, skills_context=sc, profile_context=pc, rag_context=rag)
        self._notify(f"Claude — {role}", "AI_WORKING", {"ai": "Claude", "model": "claude-sonnet-4-6", "role": role})
        t0 = time.monotonic()
        result = await self._retry_transient("Claude", lambda: self.claude.prompt(payload["system"], payload["user"]))
        self._check_driver_error(result, "Claude", role)
        self.health.record(role, "claude", time.monotonic() - t0, result, not result.startswith("ERROR:") and not result.lstrip().startswith("Error"))
        return result

    async def _call_gemini(
        self,
        role: str,
        task: str,
        project: Optional["Project"] = None,
        response_format: str = "text",
        max_tokens: int = 8192,
    ) -> str:
        import time
        sc = self.skill_manager.load_context(project.skills, role=role) if project else None
        pc = self.profile_manager.load_context(project.profile) if project else None
        rag = self.knowledge_orchestrator.query(project.description, role=role) if project else None
        task = self._augment_task_with_project_context(task, project)
        payload = self.builder.build_payload("gemini", role, task, skills_context=sc, profile_context=pc, rag_context=rag)
        model_name = self.gemini.active_model or "Gemini"
        self._notify(f"Gemini ({model_name}) — {role}", "AI_WORKING", {"ai": "Gemini", "model": model_name, "role": role})
        t0 = time.monotonic()
        result = await self._retry_transient(
            "Gemini",
            lambda: self.gemini.call(
                payload["system"], payload["user"],
                response_format=response_format,
                max_tokens=max_tokens,
            ),
        )
        if not isinstance(result, str):
            result = result.content  # DriverResponse → str
        self._check_driver_error(result, "Gemini", role)
        self.health.record(role, "gemini", time.monotonic() - t0, result, not result.startswith("ERROR:") and not result.lstrip().startswith("Error"))
        return result

    async def _call_ollama(self, role: str, task: str, project: Optional["Project"] = None) -> str:
        import time
        sc = self.skill_manager.load_context(project.skills, role=role) if project else None
        pc = self.profile_manager.load_context(project.profile) if project else None
        rag = self.knowledge_orchestrator.query(project.description, role=role) if project else None
        task = self._augment_task_with_project_context(task, project)
        payload = self.builder.build_payload("ollama", role, task, skills_context=sc, profile_context=pc, rag_context=rag)
        self._notify(f"Qwen ({self.ollama.model}) — {role}", "AI_WORKING", {"ai": "Qwen", "model": self.ollama.model, "role": role})
        t0 = time.monotonic()
        result = await self._retry_transient("Qwen", lambda: self.ollama.prompt(payload["system"], payload["user"]))
        self._check_driver_error(result, "Qwen", role)
        self.health.record(role, "ollama", time.monotonic() - t0, result, not result.startswith("ERROR:") and not result.lstrip().startswith("Error"))
        return result

    async def _call_with_fallback(self, primary: str, role: str, task: str, project=None) -> str:
        """Try primary AI; on capacity error cascade through the fallback chain."""
        from kernel.utils.ai_fallback import is_capacity_error, error_code
        callers = {
            "claude": ("Claude", self._call_claude),
            "gemini": ("Gemini", self._call_gemini),
            "ollama": ("Qwen", self._call_ollama),
        }
        chain_names = self.ai_hub.get_chain(primary)
        chain = [callers[name] for name in chain_names if name in callers]

        if not chain:
            chain = [("Claude", self._call_claude), ("Gemini", self._call_gemini)]

        last = ""
        for ai_name, caller in chain:
            result = await caller(role, task, project)
            if not is_capacity_error(result):
                return result
            last = result
            code = error_code(result)
            self._notify(
                f"{ai_name} sin capacidad ({code}) — cambiando a siguiente IA...",
                "HEALTH_WARN",
                {"ai": ai_name, "error_code": code, "role": role},
            )
            print(f"  [>>] {ai_name} capacity error ({code}), trying next in chain...")
        return last

    async def _call_with_escalation(self, role: str, task: str, project: Project) -> str:
        from kernel.utils.ai_fallback import is_capacity_error
        for attempt in range(1, self.MAX_LOCAL_RETRIES + 1):
            print(f"  [Qwen] Attempt {attempt}/{self.MAX_LOCAL_RETRIES}...")
            result = await self._call_ollama(role, task, project)
            if not result.lstrip().startswith("Error"):
                return result
            print(f"  [!] Failed attempt {attempt}: {result[:80]}")
        print("  [^^] Escalating to Claude Sonnet...")
        result = await self._call_claude(role, task, project)
        if not result.lstrip().startswith("Error"):
            return result
        if is_capacity_error(result):
            print("  [^^] Claude capacity error — trying Gemini as last resort...")
            result = await self._call_gemini(role, task, project)
            if not result.lstrip().startswith("Error"):
                return result
        project.state = ProjectState.AWAITING_CHECKPOINT
        self._save_state(project)
        raise RuntimeError(f"All models failed for role '{role}'. Rate Limit o Caída. El proyecto está en pausa.")

    # --- Copilot suggestion handler ---

    _COPILOT_EVAL_SYSTEM = (
        "Sos un arquitecto de software evaluando sugerencias de un consultor senior. "
        "Respondés SOLO con JSON válido, sin texto extra."
    )

    async def _copilot_suggest(self, phase: str, suggestion: Optional[dict]) -> Optional[str]:
        """Claude evaluates ALL Copilot suggestions (batched) and decides to apply or skip.
        Copilot always delivers every issue in one interaction — no partial rounds."""
        if not suggestion or not suggestion.get("has_suggestion"):
            return None

        msg = suggestion.get("message", "")
        changes: list = suggestion.get("changes", [])
        if not changes:
            return None

        # Build numbered list of all changes
        numbered = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(changes))

        # Broadcast all suggestions as a single informational event
        self._notify(
            f"[Copilot/{phase}] {msg} ({len(changes)} cambio(s))",
            "COPILOT_SUGGESTION",
            {"phase": phase, "message": msg, "changes": changes},
        )

        # Claude evaluates the full batch at once
        eval_prompt = (
            f"El Copilot revisó la fase '{phase}' y encontró {len(changes)} problema(s):\n\n"
            f"RESUMEN: {msg}\n\n"
            f"CAMBIOS PROPUESTOS:\n{numbered}\n\n"
            f"¿Estos cambios mejoran técnicamente el proyecto y valen la pena aplicarlos todos?\n"
            f'Respondé SOLO con: {{"apply": true, "reason": "razón concisa"}}'
        )
        try:
            dr = await self.claude.call(
                self._COPILOT_EVAL_SYSTEM, eval_prompt, max_tokens=256, temperature=0.2
            )
            import re as _re, json as _json
            m = _re.search(r'\{[^{}]*\}', dr.content, _re.DOTALL)
            decision = _json.loads(m.group(0)) if m else {}
            apply = bool(decision.get("apply", False))
            reason = str(decision.get("reason", ""))
        except Exception as exc:
            apply = False
            reason = f"error al evaluar: {exc}"

        if apply:
            consolidated = numbered  # all changes as one block
            self._notify(
                f"[Claude/eval] Copilot aceptado en {phase} ({len(changes)} cambio(s)) — {reason}",
                "COPILOT_APPLIED",
                {"phase": phase, "reason": reason, "changes": changes},
            )
            return consolidated
        else:
            self._notify(
                f"[Claude/eval] Copilot descartado en {phase} — {reason}",
                "COPILOT_REJECTED",
                {"phase": phase, "reason": reason},
            )
            return None

    # --- Phases ---

    async def _phase_wisdom(self, project: Project) -> None:
        print("\n[FASE 0.5] Wisdom — analyzing description...")
        self._notify("Analizando descripción...", "PHASE_START", {"phase": "wisdom"})

        # Web research: enrich context with real-time information when Perplexity is configured
        if self.web_researcher.is_configured():
            research_query = f"Best practices and common patterns for: {project.description[:200]}"
            self._notify("Investigando referencias web...", "LOG", {"phase": "wisdom"})
            research_result = await self.web_researcher.search(research_query)
            if research_result.excerpt and research_result.status_code in (200, 0):
                project.description += f"\n\n[WEB_RESEARCH]\n{research_result.excerpt[:1500]}"
                self._notify(
                    f"Investigación web incorporada ({research_result.source}).",
                    "LOG",
                    {"source": research_result.source, "citations": research_result.citations[:3]},
                )

        observations = await self.wisdom_agent.analyze(
            project.description, project.skills, project.profile
        )
        if observations:
            for obs in observations:
                print(f"  [{obs.type.upper()}] {obs.message}")
                self._notify(obs.message, "WISDOM", {"type": obs.type, "suggestion": obs.suggestion})
        else:
            self._notify("Sin observaciones — descripción clara.", "WISDOM", {"type": "ok", "suggestion": ""})
        print(f"  [OK] {len(observations)} observation(s)")

        # Pause once for all ambiguities — batched into a single question to avoid stalling N×15min
        needs_answer = [o for o in observations if o.type in ("ambiguity", "missing_requirement")]
        if needs_answer:
            items = "\n".join(
                f"  {i+1}. {(o.suggestion.strip() or o.message)[:160]}"
                for i, o in enumerate(needs_answer)
            )
            combined = f"SODA tiene {len(needs_answer)} duda(s) sobre tu proyecto:\n{items}\n\nResponde con aclaraciones o escribí 'continuar' para saltar."
            print(f"  [?] Asking user (batched {len(needs_answer)} items)")
            answer = await self.user_interaction.ask(combined, self._notify)
            if answer.strip() and answer.strip().lower() not in ("continuar", "continue", "skip", "saltar"):
                project.description += f"\n\nAclaraciones del usuario: {answer.strip()}"
                self._notify(f"Aclaraciones incorporadas: {answer[:120]}", "LOG", {})

    async def _phase_capabilities(self, project: Project) -> None:
        print("\n[FASE 0] Capabilities — matching skills and profile...")
        self._notify("Buscando skills y perfil...", "PHASE_START", {"phase": "capabilities"})
        project.state = ProjectState.CAPABILITIES

        skills = await self.skill_manager.select(project.description)
        profile = await self.profile_manager.select(project.description, skills)

        project.skills = skills
        project.profile = profile

        print(f"  [OK] Skills: {skills}")
        print(f"  [OK] Profile: {profile}")
        self._notify(
            f"Perfil: {profile} | Skills: {', '.join(skills) or 'ninguno'}",
            "CAPABILITIES",
            {"skills": skills, "profile": profile},
        )

        # Copilot review: are the chosen capabilities right?
        cap_sug = await self.copilot_consultant.review_capabilities(skills, profile, project.description)
        change = await self._copilot_suggest("capabilities", cap_sug)
        if change:
            project.description += f"\n\nSUGERENCIA COPILOT (capabilities): {change}"

        self._save_state(project)

    async def _phase_requirements(self, project: Project) -> None:
        print("\n[FASE 1] Requirements — interviewing with Claude Sonnet...")
        self._notify("Analizando requerimientos...", "PHASE_START", {"phase": "requirements"})
        project.state = ProjectState.REQUIREMENTS

        # Enrich description with similar past projects from vector memory
        history_hint = self.knowledge_orchestrator.enrich_context_with_history(project.description)
        task_input = project.description
        if history_hint:
            task_input = f"{project.description}\n\n{history_hint}"
            self._notify("Memoria vectorial: proyectos similares encontrados.", "LOG", {})

        MAX_COPILOT_REGEN = self._copilot_phase_regen
        for regen in range(MAX_COPILOT_REGEN + 1):
            max_attempts = 3
            for attempt in range(max_attempts):
                response = await self._call_for_role("claude", "requirements_interviewer", task_input, project)
                project.blueprint = self._extract_json(response)
                if "raw" not in project.blueprint and "nombre_proyecto" in project.blueprint:
                    break
                self._notify(
                    f"Advertencia: blueprint malformado (intento {attempt+1}/{max_attempts}). Reintentando...",
                    "HEALTH_WARN", {"phase": "requirements", "raw_preview": str(response)[:200]},
                )

            if "raw" in project.blueprint and "nombre_proyecto" not in project.blueprint:
                raise ValueError("No se pudo generar un blueprint JSON válido tras 3 intentos.")

            # Copilot review — only on non-final iterations to avoid unbounded recursion
            if regen < MAX_COPILOT_REGEN:
                suggestion = await self.copilot_consultant.review_blueprint(project.blueprint, project.description)
                change = await self._copilot_suggest("requirements", suggestion)
                if change:
                    project.description += f"\n\nSUGERENCIA COPILOT APLICADA: {change}"
                    self._apply_project_type(project)
                    self._apply_capability_packs(project)
                    task_input = project.description
                    self._notify("Regenerando blueprint con la sugerencia de Copilot...", "LOG", {})
                    continue
            break

        # Validate and auto-repair blueprint structure
        bp_val = BlueprintValidator().validate(project.blueprint)
        if bp_val.auto_fixes:
            project.blueprint = bp_val.fixed_architecture
            self._notify(
                f"Blueprint auto-corregido: {len(bp_val.auto_fixes)} ajuste(s).",
                "LOG", {"fixes": bp_val.auto_fixes},
            )
        for w in bp_val.warnings:
            self._notify(w, "HEALTH_WARN", {"phase": "requirements_validation"})
        if not bp_val.is_valid:
            raise ValueError(f"Blueprint inválido: {'; '.join(bp_val.errors)}")

        nombre = project.blueprint.get("nombre_proyecto", project.id)
        out = self._workspace(project) / "blueprint.json"
        out.write_text(json.dumps(project.blueprint, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [OK] Blueprint -> {out}")
        self._notify("Blueprint listo.", "CHECKPOINT", {"number": 1, "project_name": nombre})
        self._save_state(project)

    async def _phase_architecture(self, project: Project) -> None:
        print("\n[FASE 2] Architecture — designing with Gemini Pro...")
        self._notify("Diseñando arquitectura...", "PHASE_START", {"phase": "architecture"})

        project.state = ProjectState.ARCHITECTURE
        blueprint_str = json.dumps(project.blueprint, ensure_ascii=False)
        req_block = RequirementsStore(project.workspace).as_constraint_block()
        if req_block:
            blueprint_str = req_block + "\n" + blueprint_str

        max_attempts = 3
        last_response = ""
        for attempt in range(max_attempts):
            last_response = await self._call_gemini(
                "global_architect", blueprint_str, project,
                response_format="json",
                max_tokens=16384,
            )
            project.architecture = self._extract_json(last_response)
            if "raw" not in project.architecture and "modulos" in project.architecture:
                break
            preview = last_response[:300].replace("\n", " ")
            print(f"  [ARCH] Intento {attempt+1} fallido. Respuesta: {preview}")
            self._notify(
                f"Advertencia: arquitectura malformada (intento {attempt+1}/{max_attempts}). Reintentando...",
                "HEALTH_WARN",
                {"phase": "architecture", "attempt": attempt + 1, "raw_preview": last_response[:300]},
            )

        if "modulos" not in project.architecture:
            self._notify(
                "Gemini falló 3 veces generando arquitectura — escalando a Claude...",
                "HEALTH_WARN",
                {"phase": "architecture"},
            )
            claude_response = await self._call_claude("global_architect", blueprint_str, project)
            project.architecture = self._extract_json(claude_response)
            if "modulos" not in project.architecture:
                raise ValueError("No se pudo generar una arquitectura JSON válida (Gemini×3 + Claude fallback).")

        # Structural validation + auto-repair (paths, deps, contracts, config)
        arch_val = ArchitectureValidator().validate(project.architecture, project.blueprint)
        if arch_val.auto_fixes:
            project.architecture = arch_val.fixed_architecture
            print(f"  [VALID] {len(arch_val.auto_fixes)} corrección(es) automática(s):")
            for fix in arch_val.auto_fixes:
                print(f"    • {fix}")
            self._notify(
                f"Arquitectura auto-corregida: {len(arch_val.auto_fixes)} ajuste(s).",
                "LOG", {"fixes": arch_val.auto_fixes},
            )
        for w in arch_val.warnings:
            self._notify(w, "HEALTH_WARN", {"phase": "architecture_validation"})
            print(f"  [WARN] {w}")
        if not arch_val.is_valid:
            raise ValueError(f"Arquitectura inválida tras correcciones: {'; '.join(arch_val.errors)}")

        # Copilot Consultant Hook — single advisory pass, no regeneration loop
        suggestion = await self.copilot_consultant.review_architecture(project.architecture, project.blueprint)
        change = await self._copilot_suggest("architecture", suggestion)
        if change:
            # Incorporate feedback inline — no recursive call
            project.architecture["_copilot_note"] = change
            self._notify("Sugerencia Copilot incorporada en arquitectura (sin regenerar).", "LOG", {})

        out = self._workspace(project) / "architecture.json"
        out.write_text(json.dumps(project.architecture, indent=2, ensure_ascii=False), encoding="utf-8")
        self._build_goal_tree(project)
        print(f"  [OK] Architecture -> {out}")
        self._notify("Arquitectura lista.", "CHECKPOINT", {"number": 2})

        # Record architecture pattern for learning
        try:
            modulos = project.architecture.get("modulos", [])
            self.observer.record_architecture(
                provider="gemini",
                project_type=str(project.blueprint.get("tipo_proyecto", "")),
                description_summary=project.description[:300],
                module_count=len(modulos),
                stack=project.blueprint.get("stack_sugerido", {}),
                architecture_snippet=json.dumps({"modulos": [m.get("nombre") for m in modulos]})[:800],
                project_id=project.project_id,
            )
        except Exception:
            pass

        self._save_state(project)

        # ── Arquitecto v2 (convivencia temporal) ─────────────────────────────
        # architecture.json (legacy "modulos" format) is generated above and
        # consumed by Planning/Development. master_contract.json is generated
        # here in PARALLEL as the new contract format for future migration.
        #
        # TODO: Once Planning/Development migrate to consume master_contract.json,
        # remove the Gemini global_architect call above and make this the primary
        # architecture phase. The GoalTree should also be built from the blueprint
        # *before* this call so the Architect receives validated goal IDs.
        await self._phase_master_contract(project)

    async def _phase_master_contract(self, project: Project) -> None:
        """Generate master_contract.json using Arquitecto v2 (parallel to legacy arch).

        This is a PARALLEL output that does not affect the existing pipeline.
        architecture.json (legacy) continues to drive Planning and Development.
        master_contract.json is the new contract format — future phases will migrate
        to consume it instead of architecture['modulos'].

        Failures here are non-fatal: logged and skipped to not block the pipeline.
        """
        try:
            from kernel.intelligence.complexity_classifier import ProjectComplexityClassifier
            from kernel.intelligence.architect import Architect
            from kernel.integrity.contract_auditor import ContractAuditor
            from kernel.orchestration.contract_refinement_loop import ContractRefinementLoop

            self._notify(
                "Arquitecto v2: clasificando complejidad del proyecto...",
                "LOG",
                {"phase": "master_contract"},
            )

            classifier = ProjectComplexityClassifier()
            assessment = classifier.classify(project.blueprint)

            self._notify(
                f"Arquitecto v2: proyecto clasificado como '{assessment.level.value}' "
                f"(score {assessment.score}). {assessment.reasoning.splitlines()[0]}",
                "LOG",
                {"complexity": assessment.level.value, "score": assessment.score},
            )
            print(
                f"  [ARCH-V2] Complejidad: {assessment.level.value} | "
                f"Modelo: {assessment.level.value}"
            )

            loop = ContractRefinementLoop(
                architect=Architect(self.claude),
                auditor=ContractAuditor(goal_tree={}),
                max_attempts=3,
            )

            active_skills = [
                {"name": s} if isinstance(s, str) else s
                for s in (project.skills or [])
            ]

            result = await loop.execute(
                blueprint=project.blueprint,
                complexity=assessment.level,
                active_skills=active_skills,
                active_profile={},
                goal_tree={},
            )

            if result.status in ("approved", "approved_with_warnings"):
                contract_path = self._workspace(project) / "master_contract.json"
                contract_path.write_text(
                    result.contract.model_dump_json(indent=2),
                    encoding="utf-8",
                )
                attempt_count = len(result.attempts)
                self.perf_tracker.record_contract_result(
                    status=result.status,
                    attempts=attempt_count,
                    model=result.contract.model_used,
                )
                self._notify(
                    f"Arquitecto v2: contrato maestro aprobado "
                    f"(status={result.status}, intentos={attempt_count}).",
                    "LOG",
                    {
                        "phase": "master_contract",
                        "status": result.status,
                        "attempts": attempt_count,
                        "complexity": assessment.level.value,
                        "path": str(contract_path),
                    },
                )
                print(f"  [ARCH-V2] master_contract.json -> {contract_path}")
                self._git_commit(
                    project,
                    f"feat: master contract approved "
                    f"(complexity: {assessment.level.value}, attempts: {attempt_count})",
                )
                if result.status == "approved_with_warnings":
                    warning_count = len(result.attempts[-1].audit_report.all_warnings)
                    self._notify(
                        f"Arquitecto v2: {warning_count} warning(s) en el contrato maestro.",
                        "HEALTH_WARN",
                        {"warnings": [w.description for w in result.attempts[-1].audit_report.all_warnings]},
                    )

            else:
                # requires_user_intervention
                error_count = len(result.final_issues.all_errors) if result.final_issues else 0
                self.perf_tracker.record_contract_result(
                    status="requires_user_intervention",
                    attempts=len(result.attempts),
                )
                self._notify(
                    f"Arquitecto v2: contrato maestro no aprobado tras {len(result.attempts)} intento(s). "
                    f"{error_count} error(s) sin resolver. Pipeline continúa con architecture.json (legacy).",
                    "HEALTH_WARN",
                    {
                        "phase": "master_contract",
                        "status": "requires_user_intervention",
                        "attempts": len(result.attempts),
                    },
                )
                print(f"  [ARCH-V2] ⚠ Contrato maestro no aprobado — pipeline continúa con legacy arch.")

        except Exception as exc:
            # Non-fatal: log and continue. Legacy architecture.json is still valid.
            self._notify(
                f"Arquitecto v2 (non-fatal): {exc}",
                "LOG",
                {"phase": "master_contract", "error": str(exc)},
            )
            print(f"  [ARCH-V2] Non-fatal error, skipping master contract: {exc}")

    async def _phase_planning(self, project: Project) -> ExecutionPlan:
        print("\n[FASE 3] Planning — building module DAG...")
        self._notify("Construyendo plan de ejecución...", "PHASE_START", {"phase": "planning"})
        project.state = ProjectState.PLANNING
        modulos = project.architecture.get("modulos", [])
        if not modulos:
            raise ValueError("Architecture has no modules defined.")
        graph = DependencyGraph(modulos)
        plan = graph.build_execution_plan()
        if plan.broken_edges:
            self._notify(
                f"Dependencias circulares detectadas y resueltas: {plan.broken_edges}",
                "HEALTH_WARN",
                {"broken_edges": [list(e) for e in plan.broken_edges]},
            )
        plan_data = {"levels": plan.levels, "order": plan.order, "parallelizable": plan.parallelizable}
        out = self._workspace(project) / "execution_plan.json"
        out.write_text(json.dumps(plan_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(graph.summary())
        print(f"  [OK] Plan -> {out}")
        total_files = sum(
            len(m.get("archivos_principales", []))
            for m in modulos
            if m["nombre"] in {n for level in plan.levels for n in level}
        )
        # Copilot review: execution order
        plan_sug = await self.copilot_consultant.review_plan(plan.levels, project.architecture)
        await self._copilot_suggest("planning", plan_sug)  # advisory only — no regeneration needed

        self._notify("Plan listo.", "CHECKPOINT", {
            "number": 3,
            "levels": plan.levels,
            "total_modules": sum(len(l) for l in plan.levels),
            "total_files": total_files,
        })
        self._save_state(project)
        return plan

    async def _phase_design(self, project: Project) -> None:
        """FASE 3.5 — Generate design_spec.json for frontend projects (between PLAN and DEV)."""
        self._notify("Generando especificación de diseño UI...", "PHASE_START", {"phase": "design"})
        workspace = self._workspace(project)
        try:
            spec = self.ui_design_agent.generate_spec(project.blueprint, project.architecture)
            self.ui_design_agent.save_spec(spec, workspace)
            self._notify(
                f"Diseño generado: {spec.design_system}, {spec.layout_pattern}, dark={spec.dark_mode}",
                "PHASE_DONE",
                {"phase": "design", "design_system": spec.design_system, "layout": spec.layout_pattern},
            )
            print(f"  [OK] Design spec → {workspace / 'design_spec.json'}")
        except Exception as exc:
            self._notify(f"UIDesignAgent falló (no crítico): {exc}", "LOG", {})
            print(f"  [WARN] UIDesignAgent failed: {exc}")

    async def _phase_development(self, project: Project, plan: ExecutionPlan, interactive_mode: bool = False) -> None:
        print("\n[FASE 4] Development — generating code...")
        self._notify("Generando código...", "PHASE_START", {"phase": "development"})

        project.state = ProjectState.DEVELOPMENT
        intensity_profile = self.intensity.choose_profile(project.description)
        modulos_by_name = {m["nombre"]: m for m in project.architecture.get("modulos", [])}
        source_dir = self._workspace(project) / "source"
        source_dir.mkdir(exist_ok=True)
        from kernel.execution.html_template_injector import inject_for_project as _inject_html
        _inject_html(source_dir, project.blueprint, project.architecture)
        design_injector = DesignContextInjector(self._workspace(project))

        # Build skills and profile context once for the whole DEV phase
        skills_context: Optional[str] = None
        profile_context: Optional[str] = None
        try:
            if project.skills:
                skills_context = self.skill_manager.load_context(project.skills, role="code_generator") or None
            if project.profile:
                profile_context = self.profile_manager.load_context(project.profile) or None
        except Exception as _e:
            self._notify(f"Skills/profile context no disponible: {_e}", "LOG", {})

        # Tracks generated code per module so downstream modules get real context
        module_generated_code: dict[str, dict[str, str]] = {}

        nombres_en_nivel = [
            [n for n in level if n in modulos_by_name]
            for level in plan.levels
        ]
        for i, level in enumerate(plan.levels):
            nombres = nombres_en_nivel[i]
            tag = f"[parallel x{len(nombres)}]" if len(nombres) > 1 else "[sequential]"
            print(f"\n  Level {i} {tag}: {' | '.join(nombres)}")

            if interactive_mode:
                answer = await self.user_interaction.ask(
                    f"Listo para generar Nivel {i} ({', '.join(nombres)}). ¿Continuar? (sí/no/saltar)",
                    self._notify
                )
                if answer.strip().lower() in ("no", "n"):
                    raise RuntimeError("Ejecución pausada por el usuario en modo interactivo.")
                elif answer.strip().lower() in ("saltar", "skip"):
                    self._notify(f"Saltando Nivel {i} a petición del usuario.", "LOG", {})
                    continue

            for nombre in nombres:
                self._notify(f"Generando módulo: {nombre}", "MODULE_START", {"module": nombre, "level": i})
            tasks = [
                self._dev_qwen_copilot_loop(
                    modulos_by_name[nombre], project, source_dir,
                    dependency_context=module_generated_code,
                    skills_context=skills_context,
                    profile_context=profile_context,
                    design_injector=design_injector,
                )
                for nombre in nombres
            ]
            results_per_module = await asyncio.gather(*tasks)
            for nombre, generated_files in zip(nombres, results_per_module):
                # Accumulate generated code so the next level can use it as context
                module_generated_code[nombre] = {gf.filepath: gf.content for gf in generated_files}
                if intensity_profile.review_required or intensity_profile.arbiter_required:
                    await self._intensity_copilot_loop(
                        nombre, modulos_by_name[nombre], generated_files,
                        source_dir, project, intensity_profile,
                    )
                self._notify(f"Módulo listo: {nombre}", "MODULE_DONE", {"module": nombre, "level": i})

            # Lightweight syntax verification after each level (non-blocking)
            await self._verify_level_syntax(source_dir, nombres, project)

        print(f"\n  [OK] Code generated -> {source_dir}")
        self._save_goal_tree(project)
        self._save_state(project)

    async def _phase_verify(self, project: Project) -> None:
        """Architectural conformance check: Haiku verifies every generated module
        against its contract and fixes non-conformances in place. Non-fatal."""
        try:
            source_dir = self._workspace(project) / "source"
            self._notify(
                "Verificando conformidad arquitectónica con Haiku...",
                "PHASE_START",
                {"phase": "conformance_verify"},
            )
            await self.conformance_verifier.verify_project(project.architecture, source_dir)
            self._notify(
                "Verificación de conformidad completa.",
                "PHASE_DONE",
                {"phase": "conformance_verify"},
            )
        except Exception as exc:
            print(f"  [VERIFY] Error (no crítico): {exc}")
            self._notify(f"ConformanceVerifier falló (no crítico): {exc}", "LOG", {})

    async def _dev_qwen_copilot_loop(
        self, module: dict, project: "Project", source_dir: Path,
        dependency_context: Optional[dict] = None,
        skills_context: Optional[str] = None,
        profile_context: Optional[str] = None,
        design_injector: Optional["DesignContextInjector"] = None,
    ) -> list:
        """Qwen↔Copilot loop for DEV phase: Qwen generates, Copilot reviews code,
        Qwen regenerates with feedback. Max rounds set by copilot_temperature. Then Claude supervisor verifies."""
        MAX_ROUNDS = self._copilot_max_passes
        copilot_feedback: Optional[str] = None
        generated_files: list = []

        design_context: Optional[str] = None
        if design_injector and design_injector.is_available():
            design_context = design_injector.get_injection_for_module(module, project.blueprint) or None

        user_requirements = RequirementsStore(project.workspace).as_task_field()
        for round_idx in range(MAX_ROUNDS):
            generated_files = await self.code_gen.generate_module(
                module, project.blueprint, project.architecture,
                copilot_feedback=copilot_feedback,
                user_requirements=user_requirements,
                dependency_context=dependency_context,
                skills_context=skills_context,
                profile_context=profile_context,
                design_context=design_context,
            )
            # Write files after each round
            for gf in generated_files:
                out = source_dir / gf.filepath
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(gf.content, encoding="utf-8", errors="replace")
                self._mark_goal_implemented(project, gf.goal_id, gf.filepath)
                self._notify(
                    f"Archivo listo: {gf.filepath}",
                    "FILE_GENERATED",
                    {"filename": gf.filepath, "code": gf.content, "validated": gf.validated},
                )

            # Copilot code review — fires every round
            files_content = {gf.filepath: gf.content for gf in generated_files}
            code_sug = await self.copilot_consultant.review_module_code(
                module["nombre"], files_content, project.blueprint
            )
            if not code_sug or not code_sug.get("has_suggestion"):
                # No issues — loop is done
                self._notify(
                    f"[Copilot/dev] Módulo {module['nombre']} OK en ronda {round_idx + 1}",
                    "COPILOT_APPLIED",
                    {"module": module["nombre"], "round": round_idx + 1},
                )
                break

            # Todos los issues de Copilot → un bloque único para Qwen
            changes = code_sug.get("changes") or []
            if changes:
                copilot_feedback = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(changes))
            else:
                copilot_feedback = code_sug.get("message", "")
            self._notify(
                f"[Copilot/dev] Ronda {round_idx + 1}: {code_sug.get('message', '')} ({len(changes)} cambio(s))",
                "COPILOT_SUGGESTION",
                {"module": module["nombre"], "round": round_idx + 1, "changes": changes},
            )

            if round_idx == MAX_ROUNDS - 1:
                # Last round reached — Claude supervisor verifies final state
                verify_sug = await self.copilot_consultant.verify_module_code(
                    module["nombre"], files_content, copilot_feedback, project.blueprint
                )
                if verify_sug and verify_sug.get("has_suggestion"):
                    self._notify(
                        f"[Copilot/supervisor] Pendiente en {module['nombre']}: {verify_sug.get('message', '')}",
                        "COPILOT_SUGGESTION",
                        {"module": module["nombre"], "phase": "supervisor", "proposed_change": verify_sug.get("proposed_change", "")},
                    )

        return generated_files

    async def _intensity_copilot_loop(
        self,
        nombre: str,
        module_spec: dict,
        generated_files: list,
        source_dir: Path,
        project: "Project",
        intensity_profile,
    ) -> None:
        """Claude/Gemini corrige → Copilot revisa → si hay issues, IA vuelve a corregir. Rondas según temperatura."""
        MAX_ROUNDS = self._copilot_max_passes
        copilot_feedback: Optional[str] = None

        for round_idx in range(MAX_ROUNDS):
            if intensity_profile.review_required:
                await self._intensity_review_module(
                    nombre, generated_files, source_dir, project,
                    arbiter=False, copilot_feedback=copilot_feedback,
                )
            if intensity_profile.arbiter_required:
                await self._intensity_ensemble_module(nombre, module_spec, project, source_dir)

            # Re-leer los archivos que Claude/Gemini escribió en disco
            updated_content: dict = {}
            for gf in generated_files:
                fpath = source_dir / gf.filepath
                if fpath.exists():
                    try:
                        updated_content[gf.filepath] = fpath.read_text(encoding="utf-8")
                    except Exception:
                        pass
            if not updated_content:
                return

            # Copilot revisa el código corregido por la IA
            code_sug = await self.copilot_consultant.review_module_code(
                nombre, updated_content, project.blueprint
            )

            if not code_sug or not code_sug.get("has_suggestion"):
                self._notify(
                    f"[Copilot] {nombre} aprobado tras revisión IA (ronda {round_idx + 1})",
                    "COPILOT_APPLIED",
                    {"module": nombre, "round": round_idx + 1},
                )
                return

            # Copilot encontró issues — alimentar TODOS a la próxima ronda IA como bloque único
            changes = code_sug.get("changes") or []
            if changes:
                copilot_feedback = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(changes))
            else:
                copilot_feedback = code_sug.get("message", "")
            self._notify(
                f"[Copilot→IA] Ronda {round_idx + 1} — {nombre}: {code_sug.get('message', '')} ({len(changes)} cambio(s))",
                "COPILOT_SUGGESTION",
                {"module": nombre, "round": round_idx + 1, "changes": changes},
            )

        self._notify(
            f"[Copilot] {nombre}: máximo de rondas ({MAX_ROUNDS}) alcanzado, continuando.",
            "LOG",
            {"module": nombre},
        )

    async def _intensity_review_module(
        self,
        nombre: str,
        generated_files: list,
        source_dir,
        project: "Project",
        arbiter: bool = False,
        copilot_feedback: Optional[str] = None,
    ) -> None:
        """Run a Claude review/arbiter pass on generated module files for high/critical intensity."""
        if not generated_files:
            return
        role = "arbiter" if arbiter else "reviewer"
        label = "Árbitro" if arbiter else "Revisor"
        self._notify(f"{label} de intensidad revisando módulo: {nombre}", "LOG", {"module": nombre, "role": role})
        files_summary = "\n\n".join(
            f"### {gf.filepath}\n```\n{gf.content[:1500]}\n```" for gf in generated_files
        )
        feedback_section = (
            f"FEEDBACK DE COPILOT (aplicar obligatoriamente):\n{copilot_feedback}\n\n"
            if copilot_feedback else ""
        )
        prompt = (
            f"{'ÁRBITRO DE CALIDAD' if arbiter else 'REVISOR DE CÓDIGO'} — Módulo: {nombre}\n\n"
            f"Revisa los siguientes archivos generados y devuelve SOLO un JSON con esta estructura:\n"
            f'{{"issues": ["issue1", ...], "fixed_files": {{"path/to/file.py": "full corrected content or empty string if ok"}}, "verdict": "ok|needs_fix"}}\n\n'
            f"Si no hay problemas críticos, retorna verdict=ok y fixed_files vacío.\n\n"
            f"{feedback_section}"
            f"{files_summary}"
        )
        try:
            raw = await self._call_for_role("claude", role, prompt)
            import re as _re
            m = _re.search(r"\{.*\}", raw, _re.DOTALL)
            if not m:
                return
            import json as _json
            parsed = _json.loads(m.group(0))
            fixed = parsed.get("fixed_files", {})
            verdict = parsed.get("verdict", "ok")
            issues = parsed.get("issues", [])
            if issues:
                self._notify(
                    f"{label} detectó {len(issues)} problema(s) en {nombre}",
                    "HEALTH_WARN",
                    {"module": nombre, "issues": issues[:5], "verdict": verdict},
                )
            for fpath, content in fixed.items():
                if content and content.strip():
                    out = source_dir / fpath
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(content, encoding="utf-8", errors="replace")
                    self._notify(
                        f"{label} corrigió: {fpath}",
                        "FILE_GENERATED",
                        {"filename": fpath, "code": content, "validated": True},
                    )
        except Exception as e:
            self._notify(f"{label} falló para {nombre}: {e}", "LOG", {})

    async def _intensity_ensemble_module(
        self,
        nombre: str,
        module_spec: dict,
        project: "Project",
        source_dir: Path,
    ) -> None:
        """Level-4 critical: generate with Claude AND Gemini, then Claude arbiter picks the best."""
        self._notify(f"Ensemble crítico para módulo: {nombre}", "LOG", {"module": nombre})
        task = (
            f"MODULE: {nombre}\n"
            f"SPEC: {json.dumps(module_spec, ensure_ascii=False)[:1200]}\n"
            f"BLUEPRINT: {json.dumps(project.blueprint, ensure_ascii=False)[:800]}\n"
            "Generate production-quality code for all files in this module. "
            "Return ONLY a JSON: {\"files\": {\"path/file.ext\": \"content\"}}"
        )
        try:
            gen_a, gen_b = await asyncio.gather(
                self._call_claude("code_generator", task, project),
                self._call_gemini("code_generator", task, project),
            )
        except Exception as exc:
            self._notify(f"Ensemble falló para {nombre}: {exc}", "LOG", {})
            return

        arbiter_prompt = (
            f"You are a senior code arbiter. Two implementations were generated for module '{nombre}'.\n\n"
            f"=== IMPLEMENTATION A (Claude) ===\n{gen_a[:2000]}\n\n"
            f"=== IMPLEMENTATION B (Gemini) ===\n{gen_b[:2000]}\n\n"
            f"Pick the better one or merge the best parts. "
            f"Return ONLY valid JSON: {{\"files\": {{\"path/file.ext\": \"content\"}}}}"
        )
        try:
            best = await self._call_claude("arbiter", arbiter_prompt)
            import re as _re, json as _json
            m = _re.search(r'\{.*\}', best, _re.DOTALL)
            if not m:
                return
            parsed = _json.loads(m.group(0))
            for fpath, content in parsed.get("files", {}).items():
                if content and content.strip():
                    out = source_dir / fpath
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(content, encoding="utf-8", errors="replace")
                    self._notify(f"Ensemble árbitro escribió: {fpath}", "FILE_GENERATED", {"filename": fpath, "code": content, "validated": True})
        except Exception as exc:
            self._notify(f"Árbitro ensemble falló para {nombre}: {exc}", "LOG", {})

    async def _verify_level_syntax(self, source_dir: Path, module_names: list, project: "Project") -> None:
        """Syntax-check Python files generated in this level. Non-blocking — logs warnings only."""
        import py_compile, glob as _glob, os as _os
        errors = []
        for name in module_names:
            for py_file in source_dir.rglob("*.py"):
                try:
                    py_compile.compile(str(py_file), doraise=True)
                except py_compile.PyCompileError as exc:
                    errors.append(f"{py_file.relative_to(source_dir)}: {str(exc)[:120]}")
        if errors:
            self._notify(
                f"Verificación continua: {len(errors)} error(es) de sintaxis tras nivel con {', '.join(module_names)}",
                "HEALTH_WARN",
                {"phase": "dev_verify", "modules": module_names, "errors": errors[:5]},
            )

    # --- Entry point ---

    async def resume(self, project_id: str, interactive_mode: bool = False) -> Project:
        """Resumes a project from its last saved state."""
        workspace = self.projects_dir / project_id
        if not workspace.exists():
            raise FileNotFoundError(f"Proyecto no encontrado: {project_id}")
        
        meta_file = workspace / "metadata.json"
        if not meta_file.exists():
            raise FileNotFoundError(f"Falta metadata.json para el proyecto: {project_id}")
            
        import json as _json
        data = _json.loads(meta_file.read_text(encoding="utf-8"))
        
        project = Project(
            id=data["id"],
            description=data.get("description", ""),
            state=ProjectState(data.get("state", "idle")),
            workspace=workspace,
            blueprint=data.get("blueprint", {}),
            architecture=data.get("architecture", {}),
            skills=data.get("skills", []),
            profile=data.get("profile", ""),
            project_type=data.get("project_type", ""),
            capability_packs=data.get("capability_packs", []),
            goal_tree=data.get("goal_tree", {}),
            intensity_level=data.get("intensity_level", ""),
            reference_report=data.get("reference_report", {}),
            created_at=data.get("created_at", datetime.now().isoformat())
        )
        
        print(f"\n{'='*55}")
        print(f"SODA — Resuming Project: {project.id}")
        print(f"Current State: {project.state.value}")
        print(f"{'='*55}")
        
        self._notify(f"Reanudando proyecto {project.id} desde estado: {project.state.value}", "START", {"project_id": project.id})
        self._apply_intensity_level(project)
        self._apply_project_type(project)
        self._apply_capability_packs(project)
        
        try:
            # Reanudar fases según el estado
            if project.state in (ProjectState.IDLE, ProjectState.CAPABILITIES):
                await self._phase_capabilities(project)
                self.lineage.record_capabilities(project.id, project.skills, project.profile)
                await self._phase_wisdom(project)
                self._apply_project_type(project)
                self._apply_capability_packs(project)
                await self._phase_requirements(project)
                self._git_commit(project, "Fase 1: Blueprint generado")
            
            if project.state.value in ("idle", "capabilities", "requirements"):
                await self._phase_architecture(project)
                self._git_commit(project, "Fase 2: Arquitectura generada")
                
            if project.state.value in ("idle", "capabilities", "requirements", "architecture"):
                plan = await self._phase_planning(project)
                await self._phase_design(project)
                await self._phase_development(project, plan, interactive_mode)

                # FASE 4: Validación de integridad de objetivos (Anti-Huérfanos)
                integrity_report = self.goal_validator.validate_project_integrity(project.architecture)
                if not integrity_report.get("is_clean", True):
                    self._notify("Se detectó código huérfano que no pertenece al diseño original.", "HEALTH_WARN", integrity_report)
                
                self._git_commit(project, "Fase 4: Desarrollo completado y validado")
                
            if project.state.value not in ("done", "failed"):
                validation_result = await self._phase_validation(project)

                # Copilot review: suggest fix if build has errors
                val_sug = await self.copilot_consultant.review_validation(validation_result, project.blueprint)
                await self._copilot_suggest("validation", val_sug)

                should_regen, modules_to_regen = self._should_regenerate_after_validation(validation_result, project)
                if should_regen:
                    self._notify(
                        f"Se detectaron errores concentrados en {len(modules_to_regen)} módulo(s). Regenerando y revalidando.",
                        "HEALTH_WARN",
                        {"phase": "validation", "modules": modules_to_regen},
                    )
                    await self._phase_targeted_regeneration(
                        project,
                        modules_to_regen,
                        validation_result.get("errors_final", ""),
                    )
                    validation_result = await self._phase_validation(project, skip_permission=True)
                    self._git_commit(project, "Fase 4.5: Regeneración post-validación")

                # Docker Sandbox y Visual Inspector Hooks
                self._notify("Ejecutando pruebas en Docker Sandbox...", "LOG", {})
                docker_test_results = self.docker_sandbox.run_tests(
                    str(project.workspace), 
                    self._get_install_command(project), 
                    self._get_run_command(project)
                )
                if not docker_test_results["success"]:
                    self._notify("Pruebas TDD en Docker fallaron.", "HEALTH_WARN", docker_test_results)
                
                # Visual Inspector hook
                await self._phase_visual_inspection(project)

                await self._phase_docs(project)
                self._git_commit(project, "Fase 5: Documentación generada")

                project.state = ProjectState.DONE
                self._save_state(project)
                self.lineage.record_complete(project.id, "done")
                await self._phase_evolution(project)

            run_command = self._get_run_command(project)
            install_command = self._get_install_command(project)
            runtime_health = self._get_runtime_health(project, run_command, install_command)
            runtime_smoke = self._get_runtime_smoke(project, run_command, install_command)
            if runtime_smoke.get("attempted") and not runtime_smoke.get("passed"):
                self._notify(
                    f"Smoke check runtime no pasó ({runtime_smoke.get('reason')}).",
                    "HEALTH_WARN",
                    {"phase": "runtime", "runtime_smoke": runtime_smoke},
                )
            self._notify("Pipeline reanudado y completado.", "DONE", {
                "project_id": project.id,
                "run_command": run_command,
                "install_command": install_command,
                "workspace": str(project.workspace),
                "project_type": project.project_type,
                "capability_packs": project.capability_packs,
                "intensity_level": project.intensity_level,
                "reference_report": project.reference_report,
                "runtime_health": runtime_health,
                "runtime_smoke": runtime_smoke,
            })
            
            try:
                await self._phase_feedback_loop(project)
            except Exception as e:
                print(f"  [!] Feedback loop error (non-critical): {e}")

        except Exception as e:
            project.state = ProjectState.FAILED
            self._save_state(project)
            self._notify(f"Error crítico en el pipeline: {str(e)}", "PIPELINE_ERROR", {"project_id": project.id})
            print(f"\n[ERROR FATAL] {str(e)}")

        return project

    async def _run_non_software_pipeline(self, project: Project) -> None:
        """Alternate pipeline for analysis / marketing / finance projects.
        Phases: CAP → WISDOM → REQ (brief) → REPORT OUTPUT → DONE.
        Skips ARCH, PLAN, DEV entirely.
        """
        type_labels = {
            "analysis": ("análisis", "research"),
            "marketing": ("marketing", "campaign_plan"),
            "finance": ("finanzas", "financial_model"),
        }
        label, output_type = type_labels.get(project.project_type, ("proyecto", "report"))

        self._notify(
            f"Pipeline no-software activo: {label.upper()} — saltando ARCH/DEV.",
            "LOG",
            {"phase": "project_type_routing", "project_type": project.project_type},
        )

        # Phase 1: lightweight blueprint / brief
        await self._phase_requirements(project)
        self._git_commit(project, f"Fase 1: Brief de {label} generado")
        print(f"\n[CHECKPOINT 1] Brief ready.")

        # Phase 2: generate main output document via Claude
        self._notify(f"Generando {output_type} con Claude…", "PHASE_START", {"phase": "output_generation"})
        workspace = self._workspace(project)
        output_dir = workspace / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        skills_ctx = None
        if project.skills:
            from kernel.capabilities.skill_matcher import SkillMatcher
            skills_ctx = SkillMatcher.load_skill_context(project.skills, role="code_generator")

        payload = self.builder.build_payload(
            provider="claude",
            role=project.project_type,
            task_content=(
                f"Genera el {output_type} completo en Markdown para el siguiente proyecto de {label}.\n\n"
                f"Blueprint:\n{project.blueprint}"
            ),
            skills_context=skills_ctx,
        )
        result = await self._call_claude(
            payload["system"], payload["user"], project=project, role=project.project_type
        )
        report_path = output_dir / f"{output_type}.md"
        report_path.write_text(result, encoding="utf-8")
        self._notify(
            f"Documento principal generado: {output_type}.md",
            "FILE_GENERATED",
            {"filename": str(report_path.relative_to(workspace)), "code": result[:500]},
        )

        # Phase 3: generate output bundle (PDF / Excel if available)
        if project.blueprint and project.architecture is None:
            project.architecture = {}
        try:
            self.output_generator.generate_all(workspace, project.blueprint or {}, project.architecture or {})
        except Exception as e:
            self._notify(f"Output generator (non-fatal): {e}", "LOG", {})

        project.state = ProjectState.DONE
        self._save_state(project)
        self.lineage.record_complete(project.id, "done")

        if project.blueprint:
            self.knowledge_orchestrator.store_completed_project(project.id, project.blueprint, {})

        self._notify(
            "Pipeline no-software completo.",
            "DONE",
            {
                "project_id": project.id,
                "project_type": project.project_type,
                "workspace": str(project.workspace),
                "output_type": output_type,
            },
        )
        print(f"\n[OK] Non-software pipeline complete. Workspace: {project.workspace}")

    async def run(self, description: str, project_name: Optional[str] = None, interactive_mode: bool = False) -> Project:
        project = self._new_project(description, project_name)
        print(f"\n{'='*55}")
        print(f"SODA — Project: {project.id}")
        print(f"Description: {description[:80]}")
        print(f"{'='*55}")
        self.lineage.record_start(project.id, project.description)
        self._notify(
            f"Proyecto {project.id} iniciado. Temperatura Copilot: {self._copilot_temperature} "
            f"({self._copilot_max_passes} pasada(s) máx en código).",
            "START",
            {"project_id": project.id, "copilot_temperature": self._copilot_temperature},
        )
        self._apply_intensity_level(project)
        self._apply_project_type(project)
        self._apply_capability_packs(project)

        try:
            await self._phase_capabilities(project)
            self.perf_tracker.record_gemini_phase("capabilities")
            self.lineage.record_capabilities(project.id, project.skills, project.profile)
            await self._phase_wisdom(project)
            self.perf_tracker.record_gemini_phase("wisdom")
            self._apply_project_type(project)
            self._apply_capability_packs(project)

            # Non-software types: skip ARCH/DEV phases and go straight to document output
            if project.project_type in ("analysis", "marketing", "finance"):
                await self._run_non_software_pipeline(project)
                return project

            await self._phase_requirements(project)
            self._git_commit(project, "Fase 1: Blueprint generado")
            print(f"\n[CHECKPOINT 1] Blueprint ready.")

            await self._phase_architecture(project)
            self.perf_tracker.record_gemini_phase("architecture")
            self._git_commit(project, "Fase 2: Arquitectura generada")
            print(f"\n[CHECKPOINT 2] Architecture ready.")

            plan = await self._phase_planning(project)
            print("\n[CHECKPOINT 3] Plan ready. Starting development...")

            await self._phase_design(project)
            await self._phase_development(project, plan, interactive_mode)

            # FASE 4.V: Verificación de conformidad arquitectónica (Haiku)
            await self._phase_verify(project)
            self._git_commit(project, "feat: conformance verify — Haiku corrigió no-conformidades")

            # FASE 4: Validación de integridad de objetivos (Anti-Huérfanos)
            integrity_report = self.goal_validator.validate_project_integrity(project.architecture)
            if not integrity_report.get("is_clean", True):
                self._notify("Se detectó código huérfano que no pertenece al diseño original.", "HEALTH_WARN", integrity_report)

            self._git_commit(project, "Fase 4: Desarrollo completado y validado")

            # FASE 4.1: Validación de dependencias / imports
            await self._phase_import_validation(project)

            # FASE 4.2: Revisión de seguridad
            await self._phase_security_review(project)

            # FASE 4.3: Generación de tests automáticos
            await self._phase_test_generation(project)

            # FASE 4.4: Validación de contrato API frontend↔backend
            await self._phase_api_contract(project)

            await self._phase_audit(project)

            validation_result = await self._phase_validation(project)

            should_regen, modules_to_regen = self._should_regenerate_after_validation(validation_result, project)
            if should_regen:
                self._notify(
                    f"Se detectaron errores concentrados en {len(modules_to_regen)} módulo(s). Regenerando y revalidando.",
                    "HEALTH_WARN",
                    {"phase": "validation", "modules": modules_to_regen},
                )
                await self._phase_targeted_regeneration(
                    project,
                    modules_to_regen,
                    validation_result.get("errors_final", ""),
                )
                validation_result = await self._phase_validation(project, skip_permission=True)
                self._git_commit(project, "Fase 4.5: Regeneración post-validación")

            # Docker Sandbox y Visual Inspector Hooks
            self._notify("Ejecutando pruebas en Docker Sandbox...", "LOG", {})
            docker_test_results = self.docker_sandbox.run_tests(
                str(project.workspace),
                self._get_install_command(project),
                self._get_run_command(project)
            )
            if not docker_test_results["success"]:
                self._notify("Pruebas TDD en Docker fallaron.", "HEALTH_WARN", docker_test_results)

            # FASE 5.1: Boot Agent — instala, arranca y auto-repara
            await self._phase_boot_agent(project)

            # Visual Inspector hook
            await self._phase_visual_inspection(project)

            await self._phase_docs(project)
            self._git_commit(project, "Fase 5: Documentación generada")

            project.state = ProjectState.DONE
            self._save_state(project)
            self.lineage.record_complete(project.id, "done")
            
            # Guardar en memoria vectorial para enriquecer proyectos futuros
            if project.blueprint and project.architecture:
                self.knowledge_orchestrator.store_completed_project(
                    project.id, project.blueprint, project.architecture
                )

            await self._phase_evolution(project)
            self.perf_tracker.record_gemini_phase("evolution")

            run_command = self._get_run_command(project)
            install_command = self._get_install_command(project)
            runtime_health = self._get_runtime_health(project, run_command, install_command)

            setup_result = await self._phase_setup_and_verify(project)
            runtime_smoke = setup_result.get("smoke", self._get_runtime_smoke(project, run_command, install_command))

            # Reporte final de efectividad del equipo IA
            self.perf_tracker.print_report()

            self._notify(
                "Pipeline completo.",
                "DONE",
                {
                    "project_id": project.id,
                    "run_command": run_command,
                    "install_command": install_command,
                    "workspace": str(project.workspace),
                    "project_type": project.project_type,
                    "capability_packs": project.capability_packs,
                    "intensity_level": project.intensity_level,
                    "reference_report": project.reference_report,
                    "runtime_health": runtime_health,
                    "runtime_smoke": runtime_smoke,
                    "setup_result": setup_result,
                },
            )
            print(f"\n[OK] Pipeline complete. Workspace: {project.workspace}")

            try:
                await self._phase_feedback_loop(project)
            except Exception as e:
                print(f"  [!] Feedback loop error (non-critical): {e}")

        except Exception as e:
            import traceback as _tb
            project.state = ProjectState.FAILED
            self._save_state(project)
            self._notify(f"Error crítico en el pipeline: {str(e)}", "PIPELINE_ERROR", {"project_id": project.id})
            print(f"\n[ERROR FATAL] {str(e)}")
            try:
                from kernel.execution.execution_error_log import ExecutionErrorLog
                ExecutionErrorLog.record_exception(project.id, project.state.value, e, {"description": project.description[:200]})
            except Exception:
                pass

        return project

    # ──────────────────────────────────────────────────────────────────────────
    # IMPORT FROM EXISTING CODE
    # ──────────────────────────────────────────────────────────────────────────

    async def import_from_code(
        self,
        code: str,
        filename: str,
        analysis: dict,
        intent: str,
        project_name: str,
    ) -> "Project":
        """
        Pipeline que arranca desde código existente provisto por el usuario.
        Omite las fases WISDOM y REQ; construye el blueprint desde el análisis
        de IA ya realizado + la intención del usuario, luego corre ARCH→DEV→DONE.
        """
        from pathlib import Path

        project = self._new_project(
            description=f"{analysis.get('summary', '')}. El usuario quiere: {intent}",
            project_name=project_name,
        )

        print(f"\n{'='*55}")
        print(f"SODA — Import from code: {project.id}")
        print(f"Archivo base: {filename}  |  Intención: {intent[:60]}")
        print(f"{'='*55}")

        self.lineage.record_start(project.id, project.description)
        self._notify(
            f"Proyecto '{project.id}' iniciado desde código existente.",
            "START",
            {"project_id": project.id, "project_name": project.id},
        )

        # ── Guardar código existente en workspace/source/ ──────────────────
        src_dir = Path(project.workspace) / "source"
        src_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = Path(filename).name or "main.py"
        (src_dir / safe_filename).write_text(code, encoding="utf-8")
        self._notify(
            f"Código base guardado: {safe_filename}",
            "FILE_GENERATED",
            {"file": safe_filename, "module": "codigo_base"},
        )

        # ── Construir blueprint a partir del análisis + intención ──────────
        project.blueprint = {
            "nombre_proyecto":    project.id,
            "descripcion":        f"{analysis.get('summary', '')}. El usuario quiere: {intent}",
            "funcionalidades":    analysis.get("capabilities") or [intent],
            "stack_sugerido":     analysis.get("stack", ""),
            "lenguaje_principal": analysis.get("language", ""),
            "frameworks":         analysis.get("frameworks", []),
            "codigo_existente":   {safe_filename: code[:2000]},  # preview — evitar blueprint gigante
            "intencion_usuario":  intent,
            "comando_instalacion": analysis.get("install_command", ""),
            "comando_ejecucion":   analysis.get("run_command", ""),
        }

        try:
            # ── Fase CAPABILITIES ─────────────────────────────────────────
            await self._phase_capabilities(project)
            self.lineage.record_capabilities(project.id, project.skills, project.profile)
            self._apply_project_type(project)
            self._apply_capability_packs(project)

            # ── Fase ARCHITECTURE (usa blueprint con código base) ─────────
            await self._phase_architecture(project)
            self._git_commit(project, "Fase 2: Arquitectura generada desde código existente")

            # ── Fase PLANNING ─────────────────────────────────────────────
            plan = await self._phase_planning(project)

            # ── Fase DESIGN ───────────────────────────────────────────────
            await self._phase_design(project)

            # ── Fase DEVELOPMENT ─────────────────────────────────────────
            await self._phase_development(project, plan)

            integrity_report = self.goal_validator.validate_project_integrity(project.architecture)
            if not integrity_report.get("is_clean", True):
                self._notify("Se detectó código huérfano.", "HEALTH_WARN", integrity_report)

            self._git_commit(project, "Fase 4: Desarrollo completado")

            # ── Fase AUDIT ───────────────────────────────────────────────
            await self._phase_audit(project)

            # ── Fase VALIDATION ──────────────────────────────────────────
            validation_result = await self._phase_validation(project)
            should_regen, modules_to_regen = self._should_regenerate_after_validation(validation_result, project)
            if should_regen:
                await self._phase_targeted_regeneration(project, modules_to_regen, validation_result.get("errors_final", ""))
                validation_result = await self._phase_validation(project, skip_permission=True)
                self._git_commit(project, "Fase 4.5: Regeneración post-validación")

            await self._phase_docs(project)
            self._git_commit(project, "Fase 5: Documentación generada")

            project.state = ProjectState.DONE
            self._save_state(project)
            self.lineage.record_complete(project.id, "done")

            if project.blueprint and project.architecture:
                self.knowledge_orchestrator.store_completed_project(
                    project.id, project.blueprint, project.architecture
                )

            await self._phase_evolution(project)

            run_command     = self._get_run_command(project)
            install_command = self._get_install_command(project)
            runtime_health  = self._get_runtime_health(project, run_command, install_command)
            setup_result    = await self._phase_setup_and_verify(project)
            runtime_smoke   = setup_result.get("smoke", self._get_runtime_smoke(project, run_command, install_command))

            self._notify(
                "Pipeline desde código existente completo.",
                "DONE",
                {
                    "project_id":     project.id,
                    "run_command":    run_command,
                    "install_command": install_command,
                    "workspace":      str(project.workspace),
                    "runtime_health": runtime_health,
                    "runtime_smoke":  runtime_smoke,
                    "setup_result":   setup_result,
                },
            )
            print(f"\n[OK] Import-from-code complete. Workspace: {project.workspace}")

        except Exception as e:
            project.state = ProjectState.FAILED
            self._save_state(project)
            self._notify(f"Error en pipeline desde código: {str(e)}", "PIPELINE_ERROR", {"project_id": project.id})
            print(f"\n[ERROR FATAL] {str(e)}")

        return project

    def _get_run_command(self, project: Project) -> str:
        """Extract run command from blueprint, handling both parsed and raw formats."""
        bp = project.blueprint or {}
        cmd = bp.get("comando_ejecucion", "")
        if cmd:
            return cmd
        raw = bp.get("raw", "")
        if raw:
            try:
                import re
                m = re.search(r'"comando_ejecucion"\s*:\s*"([^"]+)"', raw)
                if m:
                    return m.group(1)
            except Exception:
                pass
        return ""

    def _get_install_command(self, project: Project) -> str:
        """Extract install command from blueprint."""
        bp = project.blueprint or {}
        cmd = bp.get("comando_instalacion", "")
        if cmd:
            return cmd
        raw = bp.get("raw", "")
        if raw:
            try:
                import re
                m = re.search(r'"comando_instalacion"\s*:\s*"([^"]+)"', raw)
                if m:
                    return m.group(1)
            except Exception:
                pass
        return ""

    def _get_auto_confirm(self) -> bool:
        try:
            cfg_path = self.base_dir / "soda_config.json"
            if cfg_path.exists():
                import json as _json
                return bool(_json.loads(cfg_path.read_text(encoding="utf-8")).get("auto_confirm", False))
        except Exception:
            pass
        return False

    def _get_runtime_health(self, project: Project, run_command: str, install_command: str) -> dict:
        if not project.workspace:
            return {
                "stack": "unknown",
                "working_dir": "",
                "has_run_command": bool((run_command or "").strip()),
                "has_install_command": bool((install_command or "").strip()),
                "source_exists": False,
                "manifest_found": False,
                "detected_manifest": "",
            }
        return self.project_runner.preflight(
            project_workspace=project.workspace,
            run_command=run_command,
            install_command=install_command,
        ).to_dict()

    def _get_runtime_smoke(self, project: Project, run_command: str, install_command: str) -> dict:
        if not self._runtime_smoke_enabled():
            return {
                "attempted": False,
                "passed": False,
                "target_url": "",
                "reason": "disabled",
                "status_code": 0,
            }
        if not project.workspace:
            return {
                "attempted": False,
                "passed": False,
                "target_url": "",
                "reason": "no_workspace",
                "status_code": 0,
            }

        return self.project_runner.smoke_check(
            project_workspace=project.workspace,
            run_command=run_command,
            install_command=install_command,
        ).to_dict()

    def _runtime_smoke_enabled(self) -> bool:
        try:
            cfg_path = self.base_dir / "soda_config.json"
            if cfg_path.exists():
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                return bool(data.get("runtime_smoke_check", True))
        except Exception:
            pass
        return True

    def _load_ai_routing(self) -> dict:
        """Load provider fallback routing from soda_config.json.

        Expected shape:
        {
          "ai_routing": {
            "claude": ["claude", "gemini", "openai", "ollama"],
            ...
          }
        }
        """
        try:
            cfg_path = self.base_dir / "soda_config.json"
            if cfg_path.exists():
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                routing = data.get("ai_routing", {})
                if isinstance(routing, dict):
                    valid = {}
                    for k, v in routing.items():
                        if isinstance(k, str) and isinstance(v, list):
                            valid[k] = [x for x in v if isinstance(x, str)]
                    return valid
        except Exception:
            pass
        return {}

    def _load_phase_provider_map(self) -> dict:
        """Load per-role primary provider override from soda_config.json."""
        try:
            cfg_path = self.base_dir / "soda_config.json"
            if cfg_path.exists():
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                mapping = data.get("ai_phase_provider", {})
                if isinstance(mapping, dict):
                    valid = {}
                    for role, provider in mapping.items():
                        if isinstance(role, str) and isinstance(provider, str):
                            valid[role] = provider
                    return valid
        except Exception:
            pass
        return {}

    def _resolve_primary_provider(self, default_primary: str, role: str) -> str:
        selected = self._phase_provider_map.get(role, default_primary)
        if selected in set(self.ai_hub.available()):
            return selected
        return default_primary

    async def _call_for_role(self, default_primary: str, role: str, task: str, project=None) -> str:
        primary = self._resolve_primary_provider(default_primary, role)
        if primary != default_primary:
            self._notify(
                f"Override IA para {role}: {default_primary} -> {primary}",
                "LOG",
                {"role": role, "default": default_primary, "selected": primary},
            )
        return await self._call_with_fallback(primary, role, task, project)

    async def _phase_audit(self, project: Project) -> None:
        """Language-aware audit: check generated code against stack rules, fix with AI if needed."""
        print("\n[FASE 4.2] Audit — language rules check...")
        self._notify("Auditando código generado...", "PHASE_START", {"phase": "audit"})

        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            self._notify("Sin directorio source — auditoría omitida.", "LOG", {})
            return

        auditor = LanguageAuditor(
            claude_driver=self.claude,
            gemini_driver=self.gemini,
            context_builder=self.builder,
            notify_fn=self._notify,
        )

        audit_result = auditor.audit_project(source_dir, project.architecture, project.blueprint)

        if not audit_result.violations:
            self._notify("Auditoría: sin problemas.", "CHECKPOINT", {"phase": "audit", "score": 100})
            return

        # Apply AI fixes for errors and warnings
        if audit_result.errors:
            fixes = await auditor.request_ai_fix(
                audit_result, source_dir, project.description, project.architecture
            )
            applied = 0
            for fix in fixes:
                filepath = (fix.get("file") or "").strip().lstrip("/\\")
                code = fix.get("code", "")
                reason = fix.get("reason", "")
                if not filepath or not code:
                    continue
                target = source_dir / filepath
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(code, encoding="utf-8")
                self._notify(
                    f"[Audit] Corregido: {filepath}" + (f" — {reason}" if reason else ""),
                    "FILE_GENERATED",
                    {"filename": filepath, "code": code, "validated": False, "audit_fix": True},
                )
                applied += 1

            if applied:
                self._notify(
                    f"Auditoría: {applied} archivo(s) corregido(s) por IA.",
                    "CHECKPOINT",
                    {"phase": "audit", "applied": applied, "score": audit_result.score},
                )
            else:
                self._notify(
                    f"Auditoría: {len(audit_result.errors)} error(es) sin corrección automática — "
                    "se intentará en la fase de validación.",
                    "HEALTH_WARN",
                    {"phase": "audit", "violations": [v.to_dict() for v in audit_result.errors]},
                )

        # Save audit report
        try:
            report_path = self._workspace(project) / "audit_report.json"
            report_path.write_text(
                __import__("json").dumps(audit_result.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    async def _phase_validation(self, project: Project, skip_permission: bool = False) -> dict:
        from kernel.project_validator import ProjectValidator
        from kernel.utils.env_checker import check_stack_tools
        print("\n[FASE 4.5] Validation — env check + build + auto-fix...")
        self._notify("Verificando entorno y corrigiendo código...", "PHASE_START", {"phase": "validation"})

        workspace = self._workspace(project)
        source_dir = workspace / "source"
        if not source_dir.exists():
            self._notify("Sin directorio source — omitiendo validación.", "LOG", {})
            return {"skipped": True, "fixed": False, "rounds": 0}

        install_cmd = self._get_install_command(project)
        run_cmd = self._get_run_command(project)

        # 1. Detect required runtime tools
        tools = await check_stack_tools(run_cmd, install_cmd)
        missing = [t for t in tools if not t.available]
        for t in tools:
            icon = "✓" if t.available else "✗"
            self._notify(
                f"{icon} {t.required_for}{': ' + t.version if t.available else ' — no encontrado'}",
                "ENV_CHECK",
                {"tool": t.name, "available": t.available, "version": t.version, "required_for": t.required_for},
            )
        if missing:
            names = ", ".join(t.required_for for t in missing)
            self._notify(
                f"Herramientas faltantes: {names}. Instalálas manualmente para ejecutar el proyecto.",
                "HEALTH_WARN",
                {"missing_tools": [t.name for t in missing]},
            )

        # 2. Ask permission to install dependencies (unless auto_confirm)
        needs_install = bool(install_cmd) or any(
            x in (run_cmd or "").lower()
            for x in ("pip", "npm", "dotnet", "go ", "cargo")
        )
        auto_confirm = self._get_auto_confirm()

        if needs_install and not auto_confirm and not skip_permission:
            answer = await self.user_interaction.ask(
                "¿Instalar dependencias del proyecto y verificar el código? "
                "(Activá 'Auto-sí' en la barra superior para no preguntar en el futuro.)",
                self._notify,
            )
            if answer.strip().lower() in ("no", "n", "omitir", "skip", "cancelar"):
                self._notify("Instalación omitida por el usuario.", "LOG", {})
                return {"skipped": True, "fixed": False, "rounds": 0}
        elif needs_install and auto_confirm:
            self._notify("Auto-sí activado — instalando dependencias sin preguntar.", "LOG", {})

        # 3. Run validation loop
        validator = ProjectValidator(
            claude_driver=self.claude,
            gemini_driver=self.gemini,
            context_builder=self.builder,
            notify_fn=self._notify,
        )

        result = await validator.validate_and_fix(
            source_dir=source_dir,
            install_cmd=install_cmd,
            run_cmd=run_cmd,
            project_description=project.description,
            workspace=workspace,
            architecture=project.architecture,
        )

        if result.get("skipped"):
            self._notify("Validación omitida (stack sin comando de build).", "LOG", {})
        elif result.get("fixed"):
            self._notify(
                f"Código validado y funcional tras {result['rounds']} ronda(s).",
                "CHECKPOINT",
                {"phase": "validation", "rounds": result["rounds"], "success": True},
            )
        else:
            self._notify(
                f"Advertencia: errores de build pendientes tras {result['rounds']} ronda(s).",
                "HEALTH_WARN",
                {
                    "phase": "validation",
                    "rounds": result["rounds"],
                    "failed_modules": result.get("failed_modules", []),
                },
            )

        return result

    # ── Nuevas fases post-DEV ─────────────────────────────────────────────────

    async def _phase_import_validation(self, project: Project) -> None:
        self._notify("Validando dependencias del manifiesto…", "PHASE_START", {"phase": "import_validation"})
        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            return
        try:
            report = self.import_validator.validate(source_dir, project.architecture)
            self._save_phase_report(project, "import_validation_report.json", report.to_dict())
        except Exception as e:
            self._notify(f"ImportValidator falló (no crítico): {e}", "LOG", {})

    async def _phase_security_review(self, project: Project) -> None:
        self._notify("Revisando seguridad del código generado…", "PHASE_START", {"phase": "security_review"})
        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            return
        try:
            report = self.security_reviewer.review(source_dir, project.blueprint)
            self._save_phase_report(project, "security_report.json", report.to_dict())
            if not report.passed and (report.critical or report.high):
                await self.security_reviewer.request_ai_suggestions(report, source_dir)
        except Exception as e:
            self._notify(f"SecurityReviewer falló (no crítico): {e}", "LOG", {})

    async def _phase_test_generation(self, project: Project) -> None:
        self._notify("Generando tests automáticos…", "PHASE_START", {"phase": "test_generation"})
        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            return
        try:
            # Build module_generated_code from disk
            module_generated_code: dict[str, dict[str, str]] = {}
            for mod in project.architecture.get("modulos", []):
                nombre = mod.get("nombre", "")
                files: dict[str, str] = {}
                for fp in mod.get("archivos_principales", []):
                    fpath = source_dir / fp
                    if fpath.exists():
                        try:
                            files[fp] = fpath.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            pass
                if files:
                    module_generated_code[nombre] = files

            report = await self.test_generator.generate_for_project(
                source_dir, project.architecture, project.blueprint, module_generated_code
            )
            self._save_phase_report(project, "test_generation_report.json", report.to_dict())
            self._git_commit(project, "Fase 4.3: Tests automáticos generados")
        except Exception as e:
            self._notify(f"TestGenerator falló (no crítico): {e}", "LOG", {})

    async def _phase_api_contract(self, project: Project) -> None:
        self._notify("Verificando contrato API frontend↔backend…", "PHASE_START", {"phase": "api_contract"})
        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            return
        try:
            report = self.api_enforcer.enforce(source_dir, project.architecture, project.blueprint)
            self._save_phase_report(project, "api_contract_report.json", report.to_dict())
        except Exception as e:
            self._notify(f"APIContractEnforcer falló (no crítico): {e}", "LOG", {})

    async def _phase_boot_agent(self, project: Project) -> None:
        self._notify("BootAgent: instalando y arrancando proyecto…", "PHASE_START", {"phase": "boot_agent"})
        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            return
        try:
            report = await self.boot_agent.run(source_dir, project.architecture, project.blueprint)
            self._save_phase_report(project, "boot_report.json", report.to_dict())
            if report.final_ok:
                self._git_commit(project, "Fase 5.1: Proyecto arranca correctamente")
        except Exception as e:
            self._notify(f"BootAgent falló (no crítico): {e}", "LOG", {})

    def _save_phase_report(self, project: Project, filename: str, data: dict) -> None:
        try:
            out = self._workspace(project) / filename
            out.write_text(
                __import__("json").dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _should_regenerate_after_validation(self, result: dict, project: Project) -> tuple[bool, list[str]]:
        if not result or result.get("skipped") or result.get("fixed"):
            return False, []

        failed_modules = [m for m in result.get("failed_modules", []) if m]
        if not failed_modules:
            return False, []

        total_modules = len((project.architecture or {}).get("modulos", []))
        if total_modules and len(failed_modules) > max(1, total_modules // 2):
            # Too broad: likely architectural/systemic issue, avoid blind regeneration.
            return False, []

        return True, failed_modules

    async def _phase_targeted_regeneration(self, project: Project, module_names: list[str], errors_final: str = "") -> None:
        modulos_by_name = {m["nombre"]: m for m in project.architecture.get("modulos", [])}
        source_dir = self._workspace(project) / "source"
        note = "\n\nREGENERACIÓN AUTOMÁTICA POR FALLO DE VALIDACIÓN"
        if errors_final:
            note += f"\nResumen de errores:\n{errors_final[:1000]}"

        self._notify(
            f"Regeneración dirigida iniciada para {len(module_names)} módulo(s).",
            "PHASE_START",
            {"phase": "targeted_regeneration", "modules": module_names},
        )

        # Build skills/profile context and read all already-generated files for cross-module context
        skills_context: Optional[str] = None
        profile_context: Optional[str] = None
        try:
            if project.skills:
                skills_context = self.skill_manager.load_context(project.skills, role="code_generator") or None
            if project.profile:
                profile_context = self.profile_manager.load_context(project.profile) or None
        except Exception:
            pass

        dependency_context: dict = {}
        if source_dir.exists():
            for mod in project.architecture.get("modulos", []):
                mod_nombre = mod.get("nombre", "")
                if mod_nombre in module_names:
                    continue  # skip modules being regenerated — use the new version
                files: dict[str, str] = {}
                for fp in mod.get("archivos_principales", []):
                    fpath = source_dir / fp
                    if fpath.exists():
                        try:
                            files[fp] = fpath.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            pass
                if files:
                    dependency_context[mod_nombre] = files

        user_requirements = RequirementsStore(project.workspace).as_task_field()
        for nombre in module_names:
            if nombre not in modulos_by_name:
                continue

            original = modulos_by_name[nombre]
            module = {
                **original,
                "responsabilidad": f"{original.get('responsabilidad', '').rstrip()}{note}",
            }
            self._notify(f"Regenerando: {nombre}", "MODULE_START", {"module": nombre})
            generated_files = await self.code_gen.generate_module(
                module, project.blueprint, project.architecture,
                user_requirements=user_requirements,
                dependency_context=dependency_context,
                skills_context=skills_context,
                profile_context=profile_context,
            )
            for gf in generated_files:
                out = source_dir / gf.filepath
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(gf.content, encoding="utf-8", errors="replace")
                self._notify(
                    f"Actualizado: {gf.filepath}",
                    "FILE_GENERATED",
                    {"filename": gf.filepath, "code": gf.content, "validated": gf.validated},
                )
            self._notify(f"Módulo regenerado: {nombre}", "MODULE_DONE", {"module": nombre})

        self._save_state(project)

    def _find_visual_modules(self, project: Project, issues: list[str]) -> list[str]:
        """Return module names likely responsible for detected visual issues."""
        ui_keywords = {"frontend", "ui", "view", "template", "page", "render", "html", "css", "react", "vue", "svelte", "static"}
        modulos = project.architecture.get("modulos", [])
        candidates = []
        for mod in modulos:
            nombre = mod.get("nombre", "").lower()
            resp = mod.get("responsabilidad", "").lower()
            if any(kw in nombre or kw in resp for kw in ui_keywords):
                candidates.append(mod["nombre"])
        # If no obvious UI modules, fall back to first module (entry-point)
        if not candidates and modulos:
            candidates = [modulos[0]["nombre"]]
        return candidates

    async def _phase_visual_inspection(self, project: Project, max_fix_iterations: int = 2) -> None:
        """Capture screenshot of running app, analyze with Gemini Flash vision, and regenerate UI modules if issues found."""
        run_command = self._get_run_command(project)
        install_command = self._get_install_command(project)
        if not run_command:
            return
        stack = self.project_runner.detect_stack(run_command, install_command)
        url = self.project_runner.infer_runtime_url(run_command, stack)
        if not url:
            return

        workspace = self._workspace(project)
        source_dir = workspace / "source"
        screenshot_dir = workspace / "_screenshots"
        context = f"Project: {project.id}. Stack: {stack}. URL: {url}"

        for iteration in range(1 + max_fix_iterations):
            screenshot_path = screenshot_dir / f"main_v{iteration}.png"
            self._notify(
                f"Visual Inspector: capturando screenshot (iteración {iteration + 1})…",
                "LOG", {"phase": "visual_inspection", "iteration": iteration + 1},
            )
            capture = await self.vision_capturer.capture_url(url, screenshot_path)
            if not capture.exists:
                self._notify(
                    f"Screenshot no disponible ({capture.error or 'app no corriendo'})",
                    "LOG", {},
                )
                return

            self._notify("Visual Inspector: analizando renderizado con Gemini Flash…", "LOG", {})
            inspection = await self.visual_inspector.analyze(screenshot_path, context=context)

            if not inspection.issues_detected:
                self._notify(
                    f"Visual Inspector: app renderiza correctamente. {inspection.ai_analysis}",
                    "LOG",
                    {"phase": "visual_inspection", "renders_correctly": True, "iteration": iteration + 1},
                )
                return

            self._notify(
                f"Visual Inspector detectó {len(inspection.issues_detected)} problema(s): "
                + "; ".join(inspection.issues_detected[:3]),
                "HEALTH_WARN",
                {
                    "phase": "visual_inspection",
                    "renders_correctly": inspection.renders_correctly,
                    "issues": inspection.issues_detected,
                    "suggestions": inspection.suggestions,
                    "summary": inspection.ai_analysis,
                    "iteration": iteration + 1,
                },
            )

            if iteration >= max_fix_iterations:
                break

            # Regenerate UI modules with visual feedback injected into task
            ui_modules = self._find_visual_modules(project, inspection.issues_detected)
            if not ui_modules:
                break

            issues_text = "\n".join(f"- {i}" for i in inspection.issues_detected[:6])
            suggestions_text = "\n".join(f"- {s}" for s in inspection.suggestions[:4])
            fix_note = (
                f"\n\nREGENERACIÓN POR PROBLEMAS VISUALES DETECTADOS (iteración {iteration + 1})\n"
                f"Problemas:\n{issues_text}\n"
                f"Sugerencias:\n{suggestions_text}"
            )

            modulos_by_name = {m["nombre"]: m for m in project.architecture.get("modulos", [])}
            self._notify(
                f"Regenerando {len(ui_modules)} módulo(s) de UI por problemas visuales…",
                "PHASE_START",
                {"phase": "visual_fix", "modules": ui_modules, "iteration": iteration + 1},
            )
            for nombre in ui_modules:
                if nombre not in modulos_by_name:
                    continue
                original = modulos_by_name[nombre]
                module = {**original, "responsabilidad": original.get("responsabilidad", "").rstrip() + fix_note}
                generated_files = await self.code_gen.generate_module(
                    module, project.blueprint, project.architecture,
                    user_requirements=RequirementsStore(project.workspace).as_task_field(),
                )
                for gf in generated_files:
                    out = source_dir / gf.filepath
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(gf.content, encoding="utf-8", errors="replace")
                    self._notify(
                        f"Actualizado (visual fix): {gf.filepath}",
                        "FILE_GENERATED",
                        {"filename": gf.filepath, "code": gf.content, "validated": gf.validated},
                    )
                self._notify(f"Módulo visual regenerado: {nombre}", "MODULE_DONE", {"module": nombre})

            self._save_state(project)

    async def _phase_setup_and_verify(self, project: Project) -> dict:
        """Install dependencies, launch project, basic smoke, then full endpoint smoke suite."""
        run_command = self._get_run_command(project)
        install_command = self._get_install_command(project)
        if not run_command:
            return {}
        workspace = self._workspace(project)
        self._notify("Configurando y verificando proyecto generado…", "LOG", {"phase": "setup"})
        result = await self.project_runner.setup_and_verify(
            project_workspace=workspace,
            run_command=run_command,
            install_command=install_command,
            notify_fn=self._notify,
        )
        # Run full endpoint smoke suite if app is reachable
        smoke_basic = result.get("smoke", {})
        base_url = smoke_basic.get("target_url", "")
        if base_url and smoke_basic.get("passed"):
            source_dir = workspace / "source"
            arch = project.architecture or {}
            self._notify(f"Ejecutando smoke suite de endpoints en {base_url}…", "LOG", {"phase": "smoke_suite"})
            suite = await self.smoke_tester.run_suite_async(base_url, arch, source_dir if source_dir.exists() else None)
            result["smoke_suite"] = suite.to_dict()
            if not suite.all_passed:
                self._notify(
                    f"Smoke suite: {suite.passed}/{suite.total} endpoints OK",
                    "HEALTH_WARN",
                    {"phase": "smoke_suite", **suite.to_dict()},
                )
            else:
                self._notify(f"Smoke suite: {suite.total} endpoints OK", "LOG", {"phase": "smoke_suite"})
        return result

    async def _phase_docs(self, project: Project) -> None:
        # Generate docker-compose.yml for multi-service projects before docs
        if project.blueprint and project.architecture:
            workspace = self._workspace(project)
            source_dir = workspace / "source"
            if source_dir.exists() and self.service_orchestrator.needs_compose(project.blueprint, project.architecture):
                compose_result = self.service_orchestrator.generate_compose(
                    project.blueprint, project.architecture, source_dir
                )
                if compose_result.generated:
                    self._notify(
                        f"docker-compose.yml generado con servicios: {', '.join(compose_result.services)}",
                        "FILE_GENERATED",
                        {"file": compose_result.path, "services": compose_result.services},
                    )

        self._notify("Generando documentación...", "PHASE_START", {"phase": "docs"})
        try:
            workspace = self._workspace(project)
            source_dir = workspace / "source"
            files = []
            if source_dir.exists():
                files = sorted(
                    str(p.relative_to(source_dir))
                    for p in source_dir.rglob("*") if p.is_file()
                )

            bp_text = json.dumps(project.blueprint, ensure_ascii=False, indent=2)
            arch_text = json.dumps(project.architecture, ensure_ascii=False, indent=2)
            file_list = "\n".join(files[:60]) or "(sin archivos)"

            task = (
                f"BLUEPRINT:\n{bp_text}\n\n"
                f"ARQUITECTURA:\n{arch_text}\n\n"
                f"ARCHIVOS GENERADOS:\n{file_list}"
            )
            content = await self._call_for_role("claude", "docs_generator", task)
            project.reference_report = self._build_reference_report(content)
            self._save_state(project)

            readme_path = (source_dir if source_dir.exists() else workspace) / "README.txt"
            readme_path.write_text(content, encoding="utf-8")
            self._notify(
                f"README.txt generado: {readme_path.name}",
                "FILE_GENERATED",
                {"file": str(readme_path), "reference_report": project.reference_report},
            )
            if project.reference_report.get("broken_candidates", 0) > 0:
                self._notify(
                    "La documentación generada contiene referencias potencialmente rotas.",
                    "HEALTH_WARN",
                    {"phase": "docs", "reference_report": project.reference_report},
                )

            # Generate output files (markdown report, PDF, Excel, presentation)
            outputs_dir = workspace / "_soda_outputs"
            try:
                output_results = self.output_generator.generate_all(
                    project_id=project.id,
                    blueprint=project.blueprint or {},
                    architecture=project.architecture or {},
                    reference_report=project.reference_report or {},
                    output_dir=outputs_dir,
                )
                for out in output_results:
                    if out.success:
                        self._notify(
                            f"Output generado: {out.format} → {out.path}",
                            "FILE_GENERATED",
                            {"file": out.path, "format": out.format, "size": out.size_bytes},
                        )
            except Exception as out_err:
                self._notify(f"Output generation omitida: {out_err}", "LOG", {})

        except Exception as e:
            self._notify(f"Documentación omitida: {e}", "LOG")

    async def _phase_iteration(self, project: Project, user_request: str) -> None:
        """Re-generate modules affected by user feedback, then re-validate."""
        self._notify("Analizando cambios solicitados...", "PHASE_START", {"phase": "modification"})
        modulos_by_name = {m["nombre"]: m for m in project.architecture.get("modulos", [])}

        # Identify affected modules via goal interpreter + impact analyzer
        affected: set = set()
        try:
            plan = await self.goal_interpreter.interpret(user_request, project.architecture, project.blueprint)
            report = await self.impact_analyzer.analyze(plan, project.architecture)
            affected = set(report.directly_affected + report.transitively_affected)
        except Exception as e:
            print(f"  [!] Impact analysis failed: {e}")

        if not affected:
            affected = set(modulos_by_name.keys())

        source_dir = self._workspace(project) / "source"
        self._notify(
            f"Regenerando {len(affected)} módulo(s) con los cambios solicitados...",
            "PHASE_START", {"phase": "development"},
        )

        for nombre in sorted(affected):
            if nombre not in modulos_by_name:
                continue
            module = {
                **modulos_by_name[nombre],
                "responsabilidad": (
                    modulos_by_name[nombre]["responsabilidad"]
                    + f"\n\nCAMBIO SOLICITADO POR EL USUARIO: {user_request}"
                ),
            }
            self._notify(f"Regenerando: {nombre}", "MODULE_START", {"module": nombre})
            generated_files = await self.code_gen.generate_module(
                module, project.blueprint, project.architecture,
                user_requirements=RequirementsStore(project.workspace).as_task_field(),
            )
            for gf in generated_files:
                out = source_dir / gf.filepath
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(gf.content, encoding="utf-8", errors="replace")
                self._notify(
                    f"Actualizado: {gf.filepath}",
                    "FILE_GENERATED",
                    {"filename": gf.filepath, "code": gf.content, "validated": gf.validated},
                )
            self._notify(f"Módulo actualizado: {nombre}", "MODULE_DONE", {"module": nombre})

        self._save_state(project)

    async def _phase_feedback_loop(self, project: Project) -> None:
        """Ask user for feedback after DONE, apply changes, re-validate, repeat."""
        MAX_ITERATIONS = 5
        DONE_WORDS = {"listo", "ok", "bien", "perfecto", "ninguno", "no", "no cambios",
                      "nada", "gracias", "todo bien", "funciona", "excelente", "genial"}

        for iteration in range(MAX_ITERATIONS):
            question = (
                "Ejecutá la app con el botón ▶. ¿Quedó como esperabas? "
                "Describí los cambios que querés (o escribí 'listo' para terminar)."
                if iteration == 0
                else "¿Cómo quedó? ¿Querés más cambios? (describílos o escribí 'listo')"
            )
            answer = await self.user_interaction.ask(question, self._notify)
            answer_clean = answer.strip().lower()

            if not answer_clean or any(answer_clean == w for w in DONE_WORDS) or answer_clean.startswith("listo"):
                if answer_clean:
                    self._notify("¡Proyecto terminado! Podés seguir usando el botón ▶ para ejecutarlo.", "LOG", {})
                break

            self._notify(f"Aplicando: {answer[:120]}", "LOG", {})
            await self._phase_iteration(project, answer)
            await self._phase_validation(project, skip_permission=True)

            run_command = self._get_run_command(project)
            install_command = self._get_install_command(project)
            self._notify(
                f"Cambios aplicados (iteración {iteration + 1}).",
                "ITERATION_DONE",
                {
                    "project_id": project.id,
                    "run_command": run_command,
                    "install_command": install_command,
                    "workspace": str(project.workspace),
                    "iteration": iteration + 1,
                },
            )

    async def _phase_evolution(self, project: Project) -> None:
        if not project.profile:
            return
        print("\n[POST] Profile Evolution — capturing learnings...")
        self._notify("Capturando aprendizajes...", "PHASE_START", {"phase": "evolution"})
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
                f"{count} aprendizajes guardados en perfil '{project.profile}'",
                "EVOLUTION",
                {"profile": project.profile, "count": count, "learnings": learnings},
            )
            # Copilot review: are the captured learnings complete?
            evo_sug = await self.copilot_consultant.review_evolution(learnings, project.description)
            await self._copilot_suggest("evolution", evo_sug)
        except Exception as e:
            print(f"  [!] Evolution failed (non-critical): {e}")

        # Synthesize new observations into the knowledge base (fire-and-forget)
        try:
            new_patterns = self.knowledge_base.synthesize_from_observations()
            if new_patterns > 0:
                print(f"  [KB] {new_patterns} nuevo(s) patrón(es) sintetizados en base de conocimiento")
                self._notify(
                    f"Knowledge Base: {new_patterns} patrón(es) nuevos aprendidos",
                    "EVOLUTION",
                    {"type": "knowledge_synthesis", "new_patterns": new_patterns},
                )
        except Exception as e:
            print(f"  [!] Knowledge synthesis failed (non-critical): {e}")

    async def refound(self, project: Project) -> Project:
        """Summarize current project and start a new one from the condensed description."""
        print("\n[REFOUND] Summarizing project for refoundation...")
        self._notify("Preparando refundación...", "PHASE_START", {"phase": "refoundation"})
        summary = await self.refoundation.summarize(
            project.description, project.blueprint, project.architecture
        )
        new_description = summary.get("refounded_description", project.description)
        key_decisions = summary.get("key_decisions", [])
        if key_decisions:
            new_description += " Key decisions: " + "; ".join(key_decisions) + "."

        self._notify(
            f"Refundación lista. Nueva descripción: {new_description[:100]}...",
            "REFOUNDATION",
            {"parent_id": project.id, "description": new_description},
        )
        new_project = await self.run(new_description)
        self.lineage.record_start(new_project.id, new_description, parent_id=project.id)
        return new_project

    async def modify(self, project: Project, user_request: str) -> dict:
        """Interpret a post-generation change request, branch if structural, return plan+impact."""
        self._notify(f"Interpreting: {user_request[:80]}", "PHASE_START", {"phase": "modification"})

        reference_report = self._build_reference_report(user_request)
        project.reference_report = reference_report
        self._save_state(project)
        self._notify(
            "Análisis de referencias del cambio completado.",
            "REFERENCE_ANALYSIS",
            {"project_id": project.id, "reference_report": reference_report},
        )
        if reference_report.get("broken_candidates", 0) > 0:
            self._notify(
                "El pedido menciona referencias potencialmente ambiguas o rotas.",
                "HEALTH_WARN",
                {"phase": "modification", "reference_report": reference_report},
            )

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
        comparison = None
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

            # Comparative run: execute both versions and compare results
            run_command = self._get_run_command(project)
            install_command = self._get_install_command(project)
            if run_command:
                self._notify(
                    "Ejecutando ambas versiones para comparación…",
                    "LOG",
                    {"parent_id": project.id, "branch_id": branch_id},
                )
                try:
                    comparison = await self.branch_manager.run_both_and_compare(
                        parent_id=project.id,
                        branch_id=branch_id,
                        run_command=run_command,
                        install_command=install_command,
                        notify_fn=self._notify,
                    )
                    self._notify(
                        f"Comparación: recomendado '{comparison['recommendation']}' "
                        f"(main={comparison['scores']['main']}, branch={comparison['scores']['branch']})",
                        "BRANCH_COMPARISON",
                        comparison,
                    )
                except Exception as e:
                    self._notify(f"Comparación fallida: {e}", "LOG", {})

        return {
            "plan": plan.to_dict(),
            "impact": report.to_dict(),
            "reference_report": reference_report,
            "branch_id": branch_id,
            "comparison": comparison,
        }


    # ── Open existing project pipeline ───────────────────────────────────────

    async def open_and_process(
        self,
        source_path: str,
        action: str,
        intent: str,
        project_name: str,
        analysis: dict,
        target_language: str = "",
    ) -> "Project":
        """
        Pipeline for opening an existing external project and processing it.
        Actions: fix_bugs | refactor | add_feature | add_tests | add_docs |
                 migrate_language | run_and_test | full_pipeline
        """
        from pathlib import Path as _Path

        source_dir = _Path(source_path)
        run_cmd   = analysis.get("run_command", "")
        inst_cmd  = analysis.get("install_command", "")
        purpose   = analysis.get("purpose", "")
        stack     = analysis.get("stack", {})
        lang      = stack.get("language", "")

        # For language migration: delegate to LanguageMigrator, then create project from result
        if action == "migrate_language" and target_language:
            return await self._pipeline_migrate_language(
                source_dir, target_language, project_name, purpose, analysis
            )

        # Build description from analysis + user intent
        quality   = analysis.get("quality", {})
        issues    = "; ".join(quality.get("issues", [])[:5])
        desc_parts = [
            f"PROYECTO EXISTENTE — {purpose}",
            f"Stack: {lang} / {stack.get('framework', '')}",
            f"Acción solicitada: {action}",
            f"Intención del usuario: {intent}",
        ]
        if issues:
            desc_parts.append(f"Problemas detectados: {issues}")
        description = "\n".join(desc_parts)

        project = self._new_project(description=description, project_name=project_name)

        print(f"\n{'='*55}")
        print(f"SODA — Open & Process: {project.id}")
        print(f"Fuente: {source_path} | Acción: {action}")
        print(f"{'='*55}")

        self.lineage.record_start(project.id, project.description)
        self._notify(
            f"Proyecto '{project.id}' iniciado desde proyecto externo.",
            "START",
            {"project_id": project.id, "project_name": project.id},
        )

        try:
            # Copy source files into workspace
            import shutil as _shutil
            workspace_source = _Path(project.workspace) / "source"
            workspace_source.mkdir(parents=True, exist_ok=True)
            if source_dir.is_dir():
                _shutil.copytree(str(source_dir), str(workspace_source), dirs_exist_ok=True)
            elif source_dir.is_file():
                _shutil.copy2(str(source_dir), str(workspace_source / source_dir.name))

            # Build blueprint from analysis
            project.blueprint = {
                "descripcion": description,
                "tipo_proyecto": analysis.get("domain", "web_app"),
                "lenguaje": lang,
                "stack": f"{lang}/{stack.get('framework', '')}",
                "comando_ejecucion": run_cmd,
                "comando_instalacion": inst_cmd,
                "modulos": [],
                "action": action,
                "original_analysis": analysis,
            }

            if action == "run_and_test":
                # Just install, run, smoke test
                await self._phase_validation(project)
                project.state = ProjectState.DONE
                self._save_state(project)
                self._notify(
                    "Ejecución y prueba completada.",
                    "DONE",
                    {"project_id": project.id, "run_command": run_cmd, "install_command": inst_cmd},
                )
                return project

            # Full processing pipeline (skips WISDOM/REQ, uses existing analysis)
            await self._phase_arch(project)
            await self._phase_plan(project)
            await self._phase_dev(project)
            await self._phase_validation(project)
            await self._phase_docs(project)

            project.state = ProjectState.DONE
            self._save_state(project)
            self.lineage.record_complete(project.id, "done")
            await self._phase_evolution(project)

            self._notify(
                "Procesamiento de proyecto externo completo.",
                "DONE",
                {"project_id": project.id, "run_command": run_cmd, "install_command": inst_cmd},
            )

        except Exception as e:
            import traceback
            project.state = ProjectState.FAILED
            self._save_state(project)
            from kernel.execution.execution_error_log import ExecutionErrorLog
            ExecutionErrorLog.record_exception(project.id, "open_and_process", e, {"source_path": source_path})
            self._notify(f"Error procesando proyecto externo: {e}", "PIPELINE_ERROR", {"project_id": project.id})
            print(f"\n[ERROR FATAL] {traceback.format_exc()}")

        return project

    async def _pipeline_migrate_language(
        self,
        source_dir: "Path",
        target_language: str,
        project_name: str,
        purpose: str,
        analysis: dict,
    ) -> "Project":
        """Create a project that is a language migration of an existing codebase."""
        from pathlib import Path as _Path

        source_lang = analysis.get("stack", {}).get("language", "")
        description = (
            f"Migración de {source_lang} a {target_language}. "
            f"Proyecto original: {purpose}"
        )

        project = self._new_project(description=description, project_name=project_name)

        self.lineage.record_start(project.id, description)
        self._notify(
            f"Migración {source_lang} → {target_language} iniciada.",
            "START",
            {"project_id": project.id, "project_name": project.id},
        )

        try:
            from kernel.execution.language_migrator import LanguageMigrator, SUPPORTED_TARGETS

            target_dir = _Path(project.workspace) / "source"
            migrator = LanguageMigrator(notify_fn=self._notify)
            result = await migrator.migrate(
                source_dir=source_dir,
                target_dir=target_dir,
                target_language=target_language,
                project_purpose=purpose,
                source_language=source_lang,
            )

            project.blueprint = {
                "descripcion": description,
                "lenguaje": target_language,
                "comando_ejecucion": result.get("run_command", ""),
                "comando_instalacion": result.get("install_command", ""),
                "migration_result": result,
            }
            self._save_state(project)

            project.state = ProjectState.DONE
            self._save_state(project)
            self.lineage.record_complete(project.id, "done")

            self._notify(
                f"Migración completa: {len(result.get('migrated_files', []))} archivos → {target_language}",
                "DONE",
                {
                    "project_id": project.id,
                    "run_command": result.get("run_command", ""),
                    "install_command": result.get("install_command", ""),
                },
            )

        except Exception as e:
            import traceback
            project.state = ProjectState.FAILED
            self._save_state(project)
            self._notify(f"Error en migración: {e}", "PIPELINE_ERROR", {"project_id": project.id})
            print(f"\n[MIGRATION ERROR] {traceback.format_exc()}")

        return project


if __name__ == "__main__":
    orchestrator = SodaOrchestrator()
    asyncio.run(orchestrator.run(
        "Quiero una app web CRUD simple para gestionar una lista de tareas: "
        "crear, leer, actualizar y eliminar tareas con titulo, descripcion y estado."
    ))
