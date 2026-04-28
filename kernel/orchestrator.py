import asyncio
import json
import re
import sys
import requests
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict
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
from kernel.docker_sandbox import DockerSandbox
from kernel.communication.telegram_gateway import TelegramGateway
from kernel.communication.user_interaction import get_gateway
from kernel.execution.project_runner import ProjectRunner
from kernel.execution.stack_detector import StackDetector
from kernel.execution.smoke_tester import SmokeTester
from kernel.execution.service_orchestrator import ServiceOrchestrator
from kernel.outputs.output_generator import OutputGenerator
from kernel.git_manager import GitManager
from kernel.goals.goal_tree import GoalTree
from kernel.orchestration.intensity_orchestrator import IntensityOrchestrator
from kernel.orchestration.phase_mixin import PhaseMixin
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
from kernel.testing.functional_test_generator import FunctionalTestGenerator
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
from kernel.logging.error_reporter import PhaseReporter, fmt_response


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
    topology: dict = field(default_factory=dict)  # topology.json — new v2 format
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


class SodaOrchestrator(PhaseMixin):
    MAX_LOCAL_RETRIES = 3

    def __init__(self, copilot_temperature: str = "media"):
        self._current_phase: str = "idle"
        self._active_project = None  # set to the Project object during run()
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
        self.functional_test_generator = FunctionalTestGenerator(
            claude_driver=self.claude,
            gemini_driver=self.gemini,
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
        self.code_gen._notify_fn = self._notify
        self.perf_tracker = PerformanceTracker()
        self.code_gen.tracker = self.perf_tracker
        self.conformance_verifier = ConformanceVerifier(self.claude, self.perf_tracker, notify_fn=self._notify)
        self._load_custom_providers()

    def cleanup_context(self):
        """Limpieza profunda de recursos y contexto (Capa 1, 2 y 3)."""
        print("  [CLEANUP] Iniciando purga integral de contexto...")
        
        # Capa 1: Limpiar Builder y Cache
        if hasattr(self, "builder") and hasattr(self.builder, "reset"):
            self.builder.reset()
            
        # Capa 3: Reset de Motores y Drivers
        if hasattr(self, "claude") and hasattr(self.claude, "clear_history"):
            self.claude.clear_history()
        if hasattr(self, "gemini") and hasattr(self.gemini, "clear_history"):
            self.gemini.clear_history()
        
        # Capa Hardware: IDLE Mode (Apagar Docker y Descargar VRAM)
        from kernel.resource_monitor import ResourceMonitor
        ResourceMonitor.set_mode("IDLE", ollama_model=self.ollama.active_model or "qwen2.5-coder:14b")
        
        print("  [CLEANUP] Sistema purificado y listo para el proximo proyecto.")

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
            "copilot_temperature": getattr(self, "_copilot_temperature", "media"),
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
        # Build enriched text: description + relevant blueprint fields when available
        text_parts = [project.description]
        if project.blueprint:
            bp = project.blueprint
            # Add stack tech names (auth, payment, websocket libs surface intensity keywords)
            stack = bp.get("stack_sugerido", {})
            if isinstance(stack, dict):
                text_parts.extend(str(v) for v in stack.values())
            elif isinstance(stack, list):
                text_parts.extend(str(v) for v in stack)
            # Add feature list
            for feat in bp.get("funcionalidades", []):
                text_parts.append(str(feat))
            # Add project type and integrations
            text_parts.append(str(bp.get("tipo_proyecto", "")))
            for integ in bp.get("integraciones", []):
                text_parts.append(str(integ))
            # Module count: many modules → raise baseline
            module_count = len(bp.get("modulos", []))
            if module_count >= 8:
                text_parts.append("microservice distributed api auth docker queue")
            elif module_count >= 4:
                text_parts.append("api crud dashboard integration")

        enriched_text = " ".join(text_parts)
        level = self.intensity.choose_level(enriched_text)
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

    async def _dispatch_call(
        self,
        driver,
        provider_name: str,
        display_name: str,
        role: str,
        task: str,
        project=None,
        **driver_kwargs,
    ) -> str:
        """Unified 5-step provider dispatch: context → payload → call → normalize → health.

        All _call_* methods delegate here so skill/profile/RAG loading, health
        recording, and error normalization live in exactly one place.
        """
        import time
        sc = self.skill_manager.load_context(project.skills, role=role) if project else None
        pc = self.profile_manager.load_context(project.profile) if project else None
        rag = self.knowledge_orchestrator.query(project.description, role=role) if project else None
        task = self._augment_task_with_project_context(task, project)
        payload = self.builder.build_payload(
            provider_name, role, task,
            skills_context=sc, profile_context=pc, rag_context=rag,
        )
        model_label = (
            getattr(driver, "active_model", None)
            or getattr(driver, "model", display_name)
        )
        self._notify(
            f"{display_name} ({model_label}) — {role}",
            "AI_WORKING",
            {"ai": display_name, "model": model_label, "role": role},
        )
        t0 = time.monotonic()
        result = await self._retry_transient(
            display_name,
            lambda: driver.call(payload["system"], payload["user"], **driver_kwargs),
        )
        # _retry_transient already normalises via _str(); guard kept for safety
        if not isinstance(result, str):
            result = result.content if hasattr(result, "content") else str(result)
        self._check_driver_error(result, display_name, role)
        self.health.record(role, provider_name, time.monotonic() - t0, result, not result.startswith("ERROR:"))
        return result

    async def _call_claude(self, role: str, task: str, project: Optional["Project"] = None) -> str:
        return await self._dispatch_call(self.claude, "claude", "Claude", role, task, project)

    async def _call_gemini(
        self,
        role: str,
        task: str,
        project: Optional["Project"] = None,
        response_format: str = "text",
        max_tokens: int = 8192,
    ) -> str:
        return await self._dispatch_call(
            self.gemini, "gemini", "Gemini", role, task, project,
            response_format=response_format, max_tokens=max_tokens,
        )

    async def _call_ollama(self, role: str, task: str, project: Optional["Project"] = None) -> str:
        return await self._dispatch_call(self.ollama, "ollama", "Qwen", role, task, project)

    async def _call_with_fallback(self, primary: str, role: str, task: str, project=None) -> str:
        """Try primary AI; on capacity error cascade through the fallback chain.

        Known providers (claude/gemini/ollama) use their dedicated methods with full
        skill/profile/RAG context. Any other provider registered in ai_hub is called
        generically via its driver's call() interface.
        """
        from kernel.utils.ai_fallback import is_capacity_error, error_code
        _known = {
            "claude": ("Claude", self._call_claude),
            "gemini": ("Gemini", self._call_gemini),
            "ollama": ("Qwen", self._call_ollama),
        }
        chain_names = self.ai_hub.get_chain(primary)
        chain: list = []
        for name in chain_names:
            if name in _known:
                chain.append(_known[name])
            else:
                driver = self.ai_hub.get(name)
                if driver is not None:
                    def _make_generic(drv, pname):
                        async def _generic(r, t, p):
                            return await self._dispatch_call(drv, pname, pname.capitalize(), r, t, p)
                        return (pname.capitalize(), _generic)
                    chain.append(_make_generic(driver, name))

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
            if not result.startswith("ERROR:"):
                return result
            print(f"  [!] Failed attempt {attempt}: {result[:80]}")
        print("  [^^] Escalating to Claude Sonnet...")
        result = await self._call_claude(role, task, project)
        if not result.startswith("ERROR:"):
            return result
        if is_capacity_error(result):
            print("  [^^] Claude capacity error — trying Gemini as last resort...")
            result = await self._call_gemini(role, task, project)
            if not result.startswith("ERROR:"):
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

    def _handle_copilot_review(
        self,
        review: Optional[Dict],
        phase: str,
        *,
        allow_rephase: bool = False,
    ) -> Dict:
        """Classify a normalized Copilot review and decide the minimum intervention strategy.

        Returns dict with keys:
          strategy  — "annotate" | "regenerate" | "rephase" | "ignore"
          applied   — True when strategy != "ignore"
          notes     — human-readable summary for logging
          changes   — list of concrete changes from the review
        """
        _ignore: Dict = {"strategy": "ignore", "applied": False, "notes": "", "changes": []}
        if not review or not review.get("has_suggestion"):
            return _ignore

        changes: list = review.get("changes") or []
        if not changes:
            return _ignore

        strategy: str = review.get("repair_mode", "annotate")
        severity: str = review.get("severity", "medium")
        confidence: float = float(review.get("confidence", 0.5))
        message: str = review.get("message", "")

        # Low confidence → downgrade to annotate regardless of repair_mode
        if confidence < 0.3:
            strategy = "annotate"

        # rephase only allowed when the caller explicitly opts in
        if strategy == "rephase" and not allow_rephase:
            strategy = "regenerate"

        notes = (
            f"[Copilot/{phase}] severity={severity} confidence={confidence:.2f} "
            f"→ {strategy}: {message}"
        )
        self._notify(
            notes,
            "COPILOT_SUGGESTION",
            {"phase": phase, "strategy": strategy, "severity": severity, "changes": changes},
        )
        return {
            "strategy": strategy,
            "applied": strategy != "ignore",
            "notes": notes,
            "changes": changes,
        }

    # --- Phases ---

    async def _dev_qwen_copilot_loop(
        self, module: dict, project: "Project", source_dir: Path,
        dependency_context: Optional[dict] = None,
        skills_context: Optional[str] = None,
        profile_context: Optional[str] = None,
        design_injector: Optional["DesignContextInjector"] = None,
        runtime_errors: str = "",
        master_contract: Optional[dict] = None,
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
                source_dir=source_dir,
                runtime_errors=runtime_errors if round_idx == 0 else "",
                master_contract=master_contract,
            )
            # PASO 2: Write files — path always comes from the task (module.archivos_principales),
            # never from LLM output. gf.filepath is set by generate_file() from the task JSON.
            _expected_paths = set(module.get("archivos_principales", []))
            for gf in generated_files:
                # Guard: if somehow filepath drifted from expected, force the expected path
                save_path = gf.filepath
                if _expected_paths and save_path not in _expected_paths:
                    _corrected = next(iter(_expected_paths), save_path)
                    self._notify(
                        f"[E4.7 guard] filepath corregido: '{save_path}' → '{_corrected}'",
                        "LOG",
                        {"expected": _corrected, "got": save_path},
                    )
                    save_path = _corrected
                out = source_dir / save_path
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(gf.content, encoding="utf-8", errors="replace")
                self._mark_goal_implemented(project, gf.goal_id, save_path)
                self._notify(
                    f"Archivo listo: {save_path}",
                    "FILE_GENERATED",
                    {"filename": save_path, "code": gf.content, "validated": gf.validated},
                )

            # Copilot code review — fires every round
            files_content = {gf.filepath: gf.content for gf in generated_files}
            code_sug = await self.copilot_consultant.review_module_code(
                module["nombre"], files_content, project.blueprint
            )
            phase_tag = f"dev/{module['nombre']}/rnd{round_idx + 1}"
            handled = self._handle_copilot_review(code_sug, phase_tag)
            if not handled["applied"]:
                # No issues — loop is done
                self._notify(
                    f"[Copilot/dev] Módulo {module['nombre']} OK en ronda {round_idx + 1}",
                    "COPILOT_APPLIED",
                    {"module": module["nombre"], "round": round_idx + 1},
                )
                break

            # ── Copilot direct-fix pass ─────────────────────────────────────
            # Copilot attempts to correct the files directly before asking Qwen to regenerate.
            fixed_files = await self.copilot_consultant.fix_module_code(
                module["nombre"], files_content, code_sug, project.blueprint
            )
            if fixed_files:
                # Merge fixes into current file map and write to disk
                files_content.update(fixed_files)
                for filepath, content in fixed_files.items():
                    out = source_dir / filepath
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(content, encoding="utf-8", errors="replace")
                self._notify(
                    f"[Copilot/fix] {module['nombre']}: {len(fixed_files)} archivo(s) corregidos directamente",
                    "COPILOT_APPLIED",
                    {"module": module["nombre"], "fixed_files": list(fixed_files.keys()),
                     "changes": handled["changes"]},
                )
                # Verify the direct fix resolved the issues
                verify_sug = await self.copilot_consultant.verify_module_code(
                    module["nombre"], files_content,
                    "\n".join(handled["changes"]), project.blueprint
                )
                verify_handled = self._handle_copilot_review(
                    verify_sug, f"dev/{module['nombre']}/verify-fix"
                )
                if not verify_handled["applied"]:
                    # Fix is clean — no need for Qwen to regenerate
                    self._notify(
                        f"[Copilot/fix] {module['nombre']}: verificado OK tras corrección directa",
                        "COPILOT_APPLIED",
                        {"module": module["nombre"], "phase": "verify-fix"},
                    )
                    break
                # Fix still has issues — feed remaining problems to Qwen
                copilot_feedback = "\n".join(
                    f"  {i+1}. {c}" for i, c in enumerate(verify_handled["changes"])
                )
            else:
                # Copilot could not produce a direct fix — use feedback for Qwen regeneration
                copilot_feedback = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(handled["changes"]))

            if round_idx == MAX_ROUNDS - 1:
                # Last round reached — Claude supervisor does final verification + fix
                verify_sug = await self.copilot_consultant.verify_module_code(
                    module["nombre"], files_content, copilot_feedback, project.blueprint
                )
                sup_handled = self._handle_copilot_review(
                    verify_sug, f"dev/{module['nombre']}/supervisor"
                )
                if sup_handled["applied"]:
                    # Supervisor found remaining issues — Copilot direct fix as last resort
                    sup_fixed = await self.copilot_consultant.fix_module_code(
                        module["nombre"], files_content, verify_sug, project.blueprint
                    )
                    if sup_fixed:
                        files_content.update(sup_fixed)
                        for filepath, content in sup_fixed.items():
                            out = source_dir / filepath
                            out.parent.mkdir(parents=True, exist_ok=True)
                            out.write_text(content, encoding="utf-8", errors="replace")
                        self._notify(
                            f"[Copilot/supervisor] {module['nombre']}: {len(sup_fixed)} archivo(s) corregidos",
                            "COPILOT_APPLIED",
                            {"module": module["nombre"], "phase": "supervisor", "fixed_files": list(sup_fixed.keys())},
                        )
                    else:
                        # Fall back to Qwen regeneration with supervisor feedback
                        supervisor_feedback = "\n".join(
                            f"  {i+1}. {c}" for i, c in enumerate(sup_handled["changes"])
                        )
                        self._notify(
                            f"[Copilot/supervisor] {module['nombre']}: regenerando con Qwen ({len(sup_handled['changes'])} cambio(s))",
                            "COPILOT_APPLIED",
                            {"module": module["nombre"], "phase": "supervisor", "changes": sup_handled["changes"]},
                        )
                        generated_files = await self.code_gen.generate_module(
                            module, project.blueprint, project.architecture,
                            copilot_feedback=supervisor_feedback,
                            user_requirements=user_requirements,
                            dependency_context=dependency_context,
                            skills_context=skills_context,
                            profile_context=profile_context,
                            design_context=design_context,
                            source_dir=source_dir,
                        )
                        for gf in generated_files:
                            out = source_dir / gf.filepath
                            out.parent.mkdir(parents=True, exist_ok=True)
                            out.write_text(gf.content, encoding="utf-8", errors="replace")
                            self._mark_goal_implemented(project, gf.goal_id, gf.filepath)
                            self._notify(
                                f"Archivo corregido (supervisor): {gf.filepath}",
                                "FILE_GENERATED",
                                {"filename": gf.filepath, "code": gf.content, "validated": gf.validated},
                            )
                else:
                    self._notify(
                        f"[Copilot/supervisor] {module['nombre']}: verificado sin issues pendientes.",
                        "COPILOT_APPLIED",
                        {"module": module["nombre"], "phase": "supervisor"},
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
        self.perf_tracker.reset()
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
                validation_result = await self._validate_and_maybe_regen(project)

                # Docker Sandbox y Visual Inspector Hooks
                self._notify("Ejecutando pruebas en Docker Sandbox...", "LOG", {"phase": "docker_sandbox"})
                docker_test_results = self.docker_sandbox.run_tests(
                    str(project.workspace),
                    self._get_install_command(project),
                    self._get_run_command(project)
                )
                if not docker_test_results["success"]:
                    self._notify(
                        "Pruebas TDD en Docker fallaron (advisory — no bloquea DONE).",
                        "HEALTH_WARN",
                        {"phase": "docker_sandbox", "advisory": True, **docker_test_results},
                    )
                
                # Visual Inspector hook
                await self._phase_visual_inspection(project)

                await self._phase_docs(project)
                self._git_commit(project, "Fase 5: Documentación generada")

                _boot_report_resume: Optional[Dict] = None
                _boot_report_path_resume = self._workspace(project) / "boot_report.json"
                if _boot_report_path_resume.exists():
                    try:
                        _boot_report_resume = json.loads(_boot_report_path_resume.read_text(encoding="utf-8"))
                    except Exception:
                        pass

                if self._can_reach_done(validation_result, _boot_report_resume):
                    project.state = ProjectState.DONE
                    self.lineage.record_complete(project.id, "done")
                else:
                    project.state = ProjectState.FAILED
                    self._notify(
                        "Pipeline detenido: errores críticos en el código generado.",
                        "PIPELINE_ERROR",
                        {"failed_modules": validation_result.get("failed_modules", [])},
                    )
                self._save_state(project)
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
            _resume_event = "DONE" if project.state == ProjectState.DONE else "FAILED"
            _resume_msg = (
                "Pipeline reanudado y completado."
                if project.state == ProjectState.DONE
                else "Pipeline reanudado con errores."
            )
            self._notify(_resume_msg, _resume_event, {
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

        # Phase 2: generate main output document
        self._notify(f"Generando {output_type}…", "PHASE_START", {"phase": "output_generation"})
        workspace = self._workspace(project)
        output_dir = workspace / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = await self._call_for_role(
            "claude",
            project.project_type,
            (
                f"Genera el {output_type} completo en Markdown para el siguiente proyecto de {label}.\n\n"
                f"Blueprint:\n{project.blueprint}"
            ),
            project,
        )
        report_path = output_dir / f"{output_type}.md"
        report_path.write_text(result, encoding="utf-8")
        self._notify(
            f"Documento principal generado: {output_type}.md",
            "FILE_GENERATED",
            {"filename": str(report_path.relative_to(workspace)), "code": result[:500]},
        )

        # Phase 3: generate output bundle (PDF / Excel if available)
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
        self.perf_tracker.reset()
        project = self._new_project(description, project_name)
        print(f"\n{'='*55}")
        print(f"SODA — Project: {project.id}")
        print(f"Description: {description[:80]}")
        print(f"{'='*55}")
        self._active_project = project
        self._current_phase = "capabilities"
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
            self._current_phase = "capabilities"
            await self._phase_capabilities(project)
            self.perf_tracker.record_gemini_phase("capabilities")
            self.lineage.record_capabilities(project.id, project.skills, project.profile)
            self._current_phase = "wisdom"
            await self._phase_wisdom(project)
            self.perf_tracker.record_gemini_phase("wisdom")
            self._apply_project_type(project)
            self._apply_capability_packs(project)

            # Non-software types: skip ARCH/DEV phases and go straight to document output
            if project.project_type in ("analysis", "marketing", "finance"):
                await self._run_non_software_pipeline(project)
                return project

            self._current_phase = "requirements"
            await self._phase_requirements(project)
            self._git_commit(project, "Fase 1: Blueprint generado")
            print(f"\n[CHECKPOINT 1] Blueprint ready.")

            self._current_phase = "architecture"
            await self._phase_architecture(project)
            self.perf_tracker.record_gemini_phase("architecture")
            self._git_commit(project, "Fase 2: Arquitectura generada")
            print(f"\n[CHECKPOINT 2] Architecture ready.")

            self._current_phase = "planning"
            plan = await self._phase_planning(project)
            print("\n[CHECKPOINT 3] Plan ready. Starting development...")

            self._current_phase = "design"
            await self._phase_design(project)
            self._current_phase = "development"
            await self._phase_development(project, plan, interactive_mode)

            # FASE 4.V: Verificación de conformidad arquitectónica (Haiku)
            self._current_phase = "verify"
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

            # FASE 4.3: Generación de tests automáticos (contract-based + E2E)
            await self._phase_test_generation(project)

            # FASE 4.4: Ejecución de tests + triage de fallos
            await self._phase_run_and_triage_tests(project)

            # FASE 4.5: Validación de contrato API frontend↔backend
            await self._phase_api_contract(project)

            await self._phase_audit(project)

            validation_result = await self._validate_and_maybe_regen(project)

            # Docker Sandbox y Visual Inspector Hooks
            self._notify("Ejecutando pruebas en Docker Sandbox...", "LOG", {"phase": "docker_sandbox"})
            docker_test_results = self.docker_sandbox.run_tests(
                str(project.workspace),
                self._get_install_command(project),
                self._get_run_command(project)
            )
            if not docker_test_results["success"]:
                self._notify(
                    "Pruebas TDD en Docker fallaron (advisory — no bloquea DONE).",
                    "HEALTH_WARN",
                    {"phase": "docker_sandbox", "advisory": True, **docker_test_results},
                )

            # FASE 5.1: Boot Agent — instala, arranca y auto-repara
            await self._phase_boot_agent(project)

            # Visual Inspector hook
            await self._phase_visual_inspection(project)

            await self._phase_docs(project)
            self._git_commit(project, "Fase 5: Documentación generada")

            # Read boot_report produced by _phase_boot_agent for the R6 DONE criterion
            _boot_report: Optional[Dict] = None
            _boot_report_path = self._workspace(project) / "boot_report.json"
            if _boot_report_path.exists():
                try:
                    _boot_report = json.loads(_boot_report_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            if self._can_reach_done(validation_result, _boot_report):
                project.state = ProjectState.DONE
                self.lineage.record_complete(project.id, "done")
            else:
                project.state = ProjectState.FAILED
                self._notify(
                    "Pipeline detenido: errores críticos en el código generado.",
                    "PIPELINE_ERROR",
                    {"failed_modules": validation_result.get("failed_modules", [])},
                )
            self._save_state(project)

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

            _run_event = "DONE" if project.state == ProjectState.DONE else "FAILED"
            _run_msg = (
                "Pipeline completo."
                if project.state == ProjectState.DONE
                else "Pipeline detenido con errores."
            )
            self._notify(
                _run_msg,
                _run_event,
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
                await self._phase_feedback_loop(project, setup_result=setup_result)
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
            validation_result = await self._validate_and_maybe_regen(project)

            await self._phase_docs(project)
            self._git_commit(project, "Fase 5: Documentación generada")

            if self._can_reach_done(validation_result):
                project.state = ProjectState.DONE
                self.lineage.record_complete(project.id, "done")
            else:
                project.state = ProjectState.FAILED
                self._notify(
                    "Pipeline detenido: errores críticos en el código generado.",
                    "PIPELINE_ERROR",
                    {"failed_modules": validation_result.get("failed_modules", [])},
                )
            self._save_state(project)

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

            _ifc_event = "DONE" if project.state == ProjectState.DONE else "FAILED"
            _ifc_msg = (
                "Pipeline desde código existente completo."
                if project.state == ProjectState.DONE
                else "Pipeline desde código existente detenido con errores."
            )
            self._notify(
                _ifc_msg,
                _ifc_event,
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
        """Derive run command: blueprint field (legacy) → filesystem detection."""
        bp = project.blueprint or {}
        cmd = bp.get("comando_ejecucion", "")
        if cmd:
            return cmd
        # Filesystem-first detection via BootAgent helper
        return self._detect_run_command_from_fs(project)

    def _get_install_command(self, project: Project) -> str:
        """Derive install command: blueprint field (legacy) → filesystem detection."""
        bp = project.blueprint or {}
        cmd = bp.get("comando_instalacion", "")
        if cmd:
            return cmd
        return self._detect_install_command_from_fs(project)

    def _detect_run_command_from_fs(self, project: Project) -> str:
        """Detect the run command by inspecting files in the project workspace."""
        from kernel.execution.boot_agent import _detect_commands
        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            source_dir = self._workspace(project)
        arch = project.architecture or {}
        try:
            _, run_parts, _ = _detect_commands(source_dir, arch)
            return " ".join(run_parts) if run_parts else ""
        except Exception:
            return ""

    def _detect_install_command_from_fs(self, project: Project) -> str:
        """Detect the install command by inspecting files in the project workspace."""
        from kernel.execution.boot_agent import _detect_commands
        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            source_dir = self._workspace(project)
        arch = project.architecture or {}
        try:
            install_parts, _, _ = _detect_commands(source_dir, arch)
            return " ".join(install_parts) if install_parts else ""
        except Exception:
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

    # Error taxonomy — three-category classification for validation and boot/smoke errors.
    # BLOCKING_CODE_ERROR  → generated code is structurally broken; blocks DONE
    # ADVISORY_RUNTIME     → missing 3rd-party dep or runtime env issue; does not block DONE
    # ADVISORY_ENV         → infrastructure/Docker/network; does not block DONE
    _ERROR_TAXONOMY: Dict[str, tuple] = {
        "BLOCKING_CODE_ERROR": (
            "SyntaxError",
            "IndentationError",
            "NameError",
            "ImportError: cannot import name",
        ),
        "ADVISORY_RUNTIME": (
            "ModuleNotFoundError",
            "ConnectionRefusedError",
            "OSError: [Errno 98]",
            "Address already in use",
            "ECONNREFUSED",
            "ENOENT",
            "Cannot find module",
            "npm warn",
        ),
        "ADVISORY_ENV": (
            "Docker",
            "Timeout after",
            "Permission denied",
            "No such file or directory",
            "connection_error",
            "no_probe_target",
        ),
    }

    # Derived from taxonomy — backward-compat alias used by _can_reach_done.
    _BLOCKING_ERROR_PATTERNS: tuple = _ERROR_TAXONOMY["BLOCKING_CODE_ERROR"]

    @staticmethod
    def _classify_error(error_text: str) -> str:
        """Return taxonomy category for error_text.

        Returns one of: 'BLOCKING_CODE_ERROR', 'ADVISORY_RUNTIME', 'ADVISORY_ENV', 'UNKNOWN'.
        First matching category wins.
        """
        for category, patterns in SodaOrchestrator._ERROR_TAXONOMY.items():
            if any(pat in error_text for pat in patterns):
                return category
        return "UNKNOWN"

    def _can_reach_done(self, validation_result: Optional[Dict], boot_report: Optional[Dict] = None) -> bool:
        """Return True if the validation result (and optional boot report) permit DONE.

        Blocking conditions:
          1. BLOCKING_CODE_ERROR in build output (SyntaxError, NameError, etc.)
          2. BootAgent ran on an HTTP stack and final_ok=False (structural boot crash)

        Tolerable: no result, skipped, fixed, ADVISORY_RUNTIME, ADVISORY_ENV, UNKNOWN,
                   or boot failure on non-HTTP stack (CLI tools exit immediately by design).
        """
        # ── Build check criterion ──────────────────────────────────────────
        if not validation_result:
            build_ok = True
        elif validation_result.get("skipped") or validation_result.get("fixed"):
            build_ok = True
        else:
            errors = str(validation_result.get("errors_final", ""))
            build_ok = not errors or self._classify_error(errors) != "BLOCKING_CODE_ERROR"

        if not build_ok:
            return False

        # ── Boot criterion (only when BootAgent ran on an HTTP stack) ──────
        if boot_report and not boot_report.get("skipped", True):
            stack = boot_report.get("stack", "unknown")
            if StackDetector.is_http_probe_applicable(stack) and not boot_report.get("final_ok", True):
                return False

        return True

    async def _validate_and_maybe_regen(self, project: Project, skip_permission: bool = False) -> dict:
        """Shared validation+regen path used by run(), resume() and import_from_code().

        Runs _phase_validation, consults Copilot for root-cause analysis, then decides
        whether to trigger targeted regeneration. Ensures all entry points behave identically.
        """
        validation_result = await self._phase_validation(project, skip_permission=skip_permission)

        val_sug = await self.copilot_consultant.review_validation(validation_result, project.blueprint)
        handled = self._handle_copilot_review(val_sug, "validation")

        should_regen, modules_to_regen = self._should_regenerate_after_validation(validation_result, project)
        if should_regen:
            self._notify(
                f"Se detectaron errores concentrados en {len(modules_to_regen)} módulo(s). Regenerando y revalidando.",
                "HEALTH_WARN",
                {"phase": "validation", "modules": modules_to_regen},
            )
            errors_ctx = validation_result.get("errors_final", "")
            if handled["applied"]:
                numbered = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(handled["changes"]))
                errors_ctx = f"ANÁLISIS COPILOT (causa raíz):\n{numbered}\n\nERRORES DE BUILD:\n{errors_ctx}"
            await self._phase_targeted_regeneration(project, modules_to_regen, errors_ctx)
            validation_result = await self._phase_validation(project, skip_permission=True)
            self._git_commit(project, "Fase 4.5: Regeneración post-validación")

        return validation_result

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
                _rnt_validation = await self._phase_validation(project)
                if self._can_reach_done(_rnt_validation):
                    project.state = ProjectState.DONE
                else:
                    project.state = ProjectState.FAILED
                self._save_state(project)
                _rnt_event = "DONE" if project.state == ProjectState.DONE else "FAILED"
                _rnt_msg = "Ejecución y prueba completada." if project.state == ProjectState.DONE else "Ejecución y prueba con errores."
                self._notify(
                    _rnt_msg,
                    _rnt_event,
                    {"project_id": project.id, "run_command": run_cmd, "install_command": inst_cmd},
                )
                return project

            # Full processing pipeline (skips WISDOM/REQ, uses existing analysis)
            await self._phase_architecture(project)
            plan = await self._phase_planning(project)
            await self._phase_development(project, plan)
            validation_result = await self._phase_validation(project)
            await self._phase_docs(project)

            if self._can_reach_done(validation_result):
                project.state = ProjectState.DONE
                self.lineage.record_complete(project.id, "done")
            else:
                project.state = ProjectState.FAILED
                self._notify(
                    "Pipeline detenido: errores críticos en el código generado.",
                    "PIPELINE_ERROR",
                    {"failed_modules": validation_result.get("failed_modules", [])},
                )
            self._save_state(project)
            await self._phase_evolution(project)

            _oap_event = "DONE" if project.state == ProjectState.DONE else "FAILED"
            _oap_msg = (
                "Procesamiento de proyecto externo completo."
                if project.state == ProjectState.DONE
                else "Procesamiento de proyecto externo detenido con errores."
            )
            self._notify(
                _oap_msg,
                _oap_event,
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


    def _project_from_disk(self, project_id: str) -> "Project":
        """Reconstruct a Project object from persisted metadata on disk."""
        workspace = self.projects_dir / project_id
        meta_path = workspace / "metadata.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"No se encontró metadata para '{project_id}'")
        with open(meta_path, encoding="utf-8") as f:
            data = json.load(f)

        arch_path = workspace / "architecture.json"
        architecture = {}
        if arch_path.exists():
            with open(arch_path, encoding="utf-8") as f:
                architecture = json.load(f)

        blueprint_path = workspace / "blueprint.json"
        blueprint = data.get("blueprint") or {}
        if not blueprint and blueprint_path.exists():
            with open(blueprint_path, encoding="utf-8") as f:
                blueprint = json.load(f)

        goal_tree_path = workspace / "goal_tree.json"
        goal_tree = data.get("goal_tree") or {}
        if not goal_tree and goal_tree_path.exists():
            with open(goal_tree_path, encoding="utf-8") as f:
                goal_tree = json.load(f)

        try:
            state = ProjectState(data.get("state", "idle"))
        except ValueError:
            state = ProjectState.FAILED

        project = Project(
            id=project_id,
            description=data.get("description", ""),
            state=state,
            workspace=workspace,
            blueprint=blueprint,
            architecture=architecture,
            skills=data.get("skills") or [],
            profile=data.get("profile") or "",
            project_type=data.get("project_type") or "",
            capability_packs=data.get("capability_packs") or [],
            goal_tree=goal_tree,
            intensity_level=data.get("intensity_level") or "",
            reference_report=data.get("reference_report") or {},
            created_at=data.get("created_at") or datetime.now().isoformat(),
        )
        return project

    async def resume(self, project_id: str) -> "Project":
        """Resume a truncated project from where it left off."""
        self.perf_tracker.reset()
        project = self._project_from_disk(project_id)
        self._active_project = project

        print(f"\n{'='*55}")
        print(f"SODA — RESUME: {project.id}")
        print(f"Estado guardado: {project.state.value}")
        print(f"{'='*55}")

        self._notify(
            f"Reanudando proyecto '{project.id}' desde estado: {project.state.value}",
            "RESUME_START",
            {"project_id": project.id, "state": project.state.value},
        )

        state = project.state

        try:
            # Determine which phases are already complete based on what exists on disk
            has_blueprint = (project.workspace / "blueprint.json").exists() and project.blueprint
            has_architecture = (project.workspace / "architecture.json").exists() and project.architecture
            has_topology = (project.workspace / "topology.json").exists()
            has_plan = (project.workspace / "execution_plan.json").exists()
            has_master_contract = (project.workspace / "master_contract.json").exists()

            if not has_blueprint:
                self._current_phase = "capabilities"
                await self._phase_capabilities(project)
                self._current_phase = "wisdom"
                await self._phase_wisdom(project)
                self._current_phase = "requirements"
                await self._phase_requirements(project)
                self._git_commit(project, "Fase 1: Blueprint generado (resume)")

            # Legacy migration: project has architecture.json but not topology.json/master_contract.json
            if has_architecture and not has_topology and not has_master_contract:
                self._notify(
                    "Proyecto legacy detectado — migrando a esquema v2 (topology + master_contract)...",
                    "LOG", {"phase": "legacy_migration"},
                )
                await self._migrate_legacy_architecture(project)
                has_topology = True
                has_master_contract = (project.workspace / "master_contract.json").exists()
                self._git_commit(project, "chore: migrated legacy architecture to v2 schema")

            if not has_architecture or not has_topology or not has_master_contract:
                self._current_phase = "architecture"
                await self._phase_architecture(project)
                self._git_commit(project, "Fase 2: Arquitectura generada (resume)")

            if not has_plan:
                self._current_phase = "planning"
                plan = await self._phase_planning(project)
            else:
                plan_path = project.workspace / "execution_plan.json"
                with open(plan_path, encoding="utf-8") as f:
                    plan_data = json.load(f)
                plan = ExecutionPlan(
                    levels=plan_data.get("levels", []),
                    order=plan_data.get("order", []),
                    parallelizable=plan_data.get("parallelizable", True),
                )
                print(f"[RESUME] Plan cargado desde disco ({len(plan.levels)} niveles)")

            self._current_phase = "design"
            await self._phase_design(project)

            self._current_phase = "development"
            await self._phase_development(project, plan, skip_existing=True)

            self._current_phase = "verify"
            await self._phase_verify(project)
            self._git_commit(project, "feat: conformance verify — resume")

            integrity_report = self.goal_validator.validate_project_integrity(project.architecture)
            if not integrity_report.get("is_clean", True):
                self._notify("Se detectó código huérfano.", "HEALTH_WARN", integrity_report)

            self._git_commit(project, "Fase 4: Desarrollo completado (resume)")
            await self._phase_import_validation(project)
            await self._phase_security_review(project)
            await self._phase_test_generation(project)
            await self._phase_run_and_triage_tests(project)
            await self._phase_api_contract(project)
            await self._phase_audit(project)

            validation_result = await self._validate_and_maybe_regen(project)
            await self._phase_boot_agent(project)
            await self._phase_visual_inspection(project)
            await self._phase_docs(project)
            self._git_commit(project, "Fase 5: Documentación generada (resume)")

            await self._phase_evolution(project)
            project.state = ProjectState.DONE
            self._save_state(project)

            self._notify(
                f"Proyecto '{project.id}' reanudado y completado.",
                "DONE",
                {"project_id": project.id},
            )
            print(f"\n[RESUME DONE] {project.id} completado.")

        except Exception as e:
            import traceback
            project.state = ProjectState.FAILED
            self._save_state(project)
            self._notify(f"Error al reanudar: {e}", "PIPELINE_ERROR", {"project_id": project.id})
            print(f"\n[RESUME ERROR] {traceback.format_exc()}")

        return project


if __name__ == "__main__":
    orchestrator = SodaOrchestrator()
    asyncio.run(orchestrator.run(
        "Quiero una app web CRUD simple para gestionar una lista de tareas: "
        "crear, leer, actualizar y eliminar tareas con titulo, descripcion y estado."
    ))
