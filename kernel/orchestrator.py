import asyncio
import json
import os
import re
import sys
import time
import requests
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kernel.dependency_graph import DependencyGraph, ExecutionPlan
from kernel.orchestration.intensity_orchestrator import IntensityOrchestrator
from kernel.orchestration.omega_engine import OmegaEngine
from kernel.projects.project_types import ProjectTypeRegistry
from kernel.projects.project_manager import ProjectManager
from kernel.utils.blackbox_logger import SodaLogger
from kernel.utils.tree_exporter import TreeExporter


def _strip_code_fence(content: str) -> str:
    """Strip markdown code fences that LLMs sometimes wrap around generated files."""
    lines = content.strip().splitlines()
    if not lines: return content
    if lines[0].startswith("```"): lines = lines[1:]
    if lines and lines[-1].strip() == "```": lines = lines[:-1]
    return "\n".join(lines)


class ProjectState(Enum):
    IDLE = "idle"
    CAPABILITIES = "capabilities"
    BOOT_FAILED = "boot_failed"
    BOOT_AGENT = "boot_agent"
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
    topology: dict = field(default_factory=dict)
    skills: list = field(default_factory=list)
    profile: str = ""
    project_type: str = "software"
    capability_packs: list = field(default_factory=list)
    intensity_level: str = "medium"
    reference_report: dict = field(default_factory=dict)
    goal_tree: dict = field(default_factory=dict)
    created_at: str = ""


class SodaOrchestrator:
    def __init__(self, copilot_temperature: str = "media"):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.projects_dir = self.base_dir / "projects"
        self.projects_dir.mkdir(exist_ok=True)

        self._copilot_temperature = copilot_temperature
        self._copilot_max_passes = 3

        # Logger BlackBox — simple, sin dependencias pesadas
        self.blackbox = SodaLogger()
        
        # SODA FUSION: Guardian de Procesos
        from kernel.utils.process_watchdog import ProcessWatchdog
        self.watchdog = ProcessWatchdog("GLOBAL")

        # ════ Componentes lazy: no instanciar nada hasta que se use ════
        self._builder = None
        self._raw_gemini = None
        self._raw_ollama = None
        self._gemini = None
        self._ollama = None
        self._deepseek = None
        self._ai_hub = None
        self._code_gen = None
        self._capability_pack_registry = None
        self._skill_matcher = None
        self._profile_matcher = None
        self._skill_manager = None
        self._profile_manager = None
        self._wisdom_agent = None
        self._goal_interpreter = None
        self._impact_analyzer = None
        self._reference_analyzer = None
        self._refoundation = None
        self._profile_evolution = None
        self._copilot_consultant = None
        self._chroma_manager = None
        self._knowledge_orchestrator = None
        self._goal_validator = None
        self._lineage = None
        self._branch_manager = None
        self._project_runner = None
        self._smoke_tester = None
        self._service_orchestrator = None
        self._output_generator = None
        self._intensity = None
        self._project_types = None
        self._project_manager = None
        self._git_manager = None
        self._health = None
        self._telegram = None
        self._vision_capturer = None
        self._visual_inspector = None
        self._web_researcher = None
        self._import_validator = None
        self._api_enforcer = None
        self._security_reviewer = None
        self._test_generator = None
        self._functional_test_generator = None
        self._boot_agent = None
        self._ui_design_agent = None
        self._observer = None
        self._knowledge_base = None
        self._coach = None
        self._perf_tracker = None
        self._conformance_verifier = None
        self._template_manager = None
        self._symbol_generator = None

        self._ui_url = "http://127.0.0.1:8000/api/event"
        self._active_project = None

        # ════ Notify worker asyncio ════
        self._notify_queue: asyncio.Queue = asyncio.Queue()
        self._notify_worker_task: Optional[asyncio.Task] = None

    def _ensure_notify_worker(self):
        if self._notify_worker_task is None or self._notify_worker_task.done():
            self._notify_worker_task = asyncio.create_task(self._notify_worker())

    async def _notify_worker(self):
        """Background worker único para notificaciones. Cero threads."""
        from ui.websocket_handler import manager as _ws_manager
        while True:
            try:
                event_type, message, data = await asyncio.wait_for(
                    self._notify_queue.get(), timeout=30
                )
            except asyncio.TimeoutError:
                continue

            # Always print
            print(f"[{event_type}] {message}")

            # Telegram
            if self._telegram is not None:
                try:
                    await self._telegram.send_event(event_type, message, data)
                except Exception as e:
                    print(f"  [Telegram Notify Error] {e}")

            # WebSocket
            payload = {"event_type": event_type, "message": message, "data": data or {}}
            sent_via_ws = False
            try:
                if _ws_manager.active_connections:
                    await _ws_manager.broadcast(payload)
                    sent_via_ws = True
            except Exception:
                pass

            # HTTP fallback
            if not sent_via_ws:
                try:
                    requests.post(self._ui_url, json=payload, timeout=1.0)
                except Exception:
                    pass

    def _notify(self, message: str, event_type: str = "LOG", data: Optional[dict] = None) -> None:
        """Encola notificación — no bloquea, no crea threads."""
        self._ensure_notify_worker()
        try:
            self._notify_queue.put_nowait((event_type, message, data or {}))
        except Exception:
            print(f"[{event_type}] {message}")

    def _log(self, event_type: str, message: str):
        """Alias para compatibilidad con componentes que esperan _log."""
        self._notify(message, event_type)

    def _load_ai_routing(self) -> dict:
        return {
            "capabilities": "gemini",
            "wisdom": "gemini",
            "requirements": "gemini",
            "architecture": "gemini",
            "planning": "gemini",
            "development": "ollama",
            "audit": "gemini",
        }

    # ════════════════════════════════════════════════════
    # Lazy properties — componentes se inicializan al usarse
    # ════════════════════════════════════════════════════

    @property
    def builder(self):
        if self._builder is None:
            from kernel.context.context_builder import ContextBuilder
            self._builder = ContextBuilder()
        return self._builder

    @property
    def gemini(self):
        if self._gemini is None:
            from kernel.drivers.gemini_driver import GeminiDriver
            from kernel.drivers.provider_hub import AIProxy
            if self._raw_gemini is None:
                self._raw_gemini = GeminiDriver()
            self._gemini = AIProxy(self._raw_gemini, "gemini-2.5-flash", self.blackbox)
        return self._gemini

    @property
    def ollama(self):
        if self._ollama is None:
            from kernel.drivers.ollama_driver import OllamaDriver
            from kernel.drivers.provider_hub import AIProxy
            if self._raw_ollama is None:
                self._raw_ollama = OllamaDriver()
            self._ollama = AIProxy(self._raw_ollama, "qwen2.5-coder:14b", self.blackbox)
        return self._ollama

    @property
    def deepseek(self):
        if self._deepseek is None:
            from kernel.drivers.deepseek_driver import DeepSeekDriver
            from kernel.drivers.provider_hub import AIProxy
            _raw = DeepSeekDriver()
            self._deepseek = AIProxy(_raw, "deepseek-chat", self.blackbox)
        return self._deepseek

    @property
    def ai_hub(self):
        if self._ai_hub is None:
            from kernel.drivers.provider_hub import AIProviderHub
            from kernel.drivers.claude_driver import ClaudeDriver
            from kernel.drivers.gemini_driver import GeminiDriver
            from kernel.drivers.ollama_driver import OllamaDriver
            from kernel.drivers.deepseek_driver import DeepSeekDriver
            
            self._ai_hub = AIProviderHub(
                providers={
                    "gemini": self._raw_gemini or GeminiDriver(),
                    "ollama": self._raw_ollama or OllamaDriver(),
                    "claude": ClaudeDriver(model_name="claude-3-5-sonnet-latest"),
                    "deepseek": DeepSeekDriver(),
                },
                routes=self._load_ai_routing(),
            )
            self._ai_hub.blackbox = self.blackbox
        return self._ai_hub

    @property
    def code_gen(self):
        if self._code_gen is None:
            from kernel.code_generator import CodeGenerator
            cg = CodeGenerator(self.ollama, self.gemini)
            cg.observer = self.observer
            cg.coach = self.coach
            cg.notify = self._notify
            self._code_gen = cg
        return self._code_gen

    @property
    def capability_pack_registry(self):
        if self._capability_pack_registry is None:
            from kernel.capabilities.capability_packs import CapabilityPackRegistry
            self._capability_pack_registry = CapabilityPackRegistry()
        return self._capability_pack_registry

    @property
    def skill_matcher(self):
        if self._skill_matcher is None:
            from kernel.capabilities.skill_matcher import SkillMatcher
            self._skill_matcher = SkillMatcher(self.gemini, self.builder)
        return self._skill_matcher

    @property
    def profile_matcher(self):
        if self._profile_matcher is None:
            from kernel.capabilities.profile_matcher import ProfileMatcher
            self._profile_matcher = ProfileMatcher(self.gemini, self.builder)
        return self._profile_matcher

    @property
    def skill_manager(self):
        if self._skill_manager is None:
            from kernel.capabilities.skill_manager import SkillManager
            self._skill_manager = SkillManager(self.skill_matcher)
        return self._skill_manager

    @property
    def profile_manager(self):
        if self._profile_manager is None:
            from kernel.capabilities.profile_manager import ProfileManager
            self._profile_manager = ProfileManager(self.profile_matcher)
        return self._profile_manager

    @property
    def wisdom_agent(self):
        if self._wisdom_agent is None:
            from kernel.intelligence.wisdom_agent import WisdomAgent
            self._wisdom_agent = WisdomAgent(self.gemini, self.builder, ai_hub=self.ai_hub, notify_fn=self.notify)
        return self._wisdom_agent

    @property
    def goal_interpreter(self):
        if self._goal_interpreter is None:
            from kernel.intelligence.goal_interpreter import GoalInterpreter
            self._goal_interpreter = GoalInterpreter(self.gemini, self.builder)
        return self._goal_interpreter

    @property
    def impact_analyzer(self):
        if self._impact_analyzer is None:
            from kernel.intelligence.impact_analyzer import ImpactAnalyzer
            self._impact_analyzer = ImpactAnalyzer(self.gemini, self.builder)
        return self._impact_analyzer

    @property
    def reference_analyzer(self):
        if self._reference_analyzer is None:
            from kernel.intelligence.reference_analyzer import ReferenceAnalyzer
            self._reference_analyzer = ReferenceAnalyzer()
        return self._reference_analyzer

    @property
    def refoundation(self):
        if self._refoundation is None:
            from kernel.intelligence.refoundation import RefoundationEngine
            self._refoundation = RefoundationEngine(self.gemini, self.builder)
        return self._refoundation

    @property
    def profile_evolution(self):
        if self._profile_evolution is None:
            from kernel.capabilities.profile_evolution import ProfileEvolutionEngine
            self._profile_evolution = ProfileEvolutionEngine(self.gemini, self.builder)
        return self._profile_evolution

    @property
    def copilot_consultant(self):
        if self._copilot_consultant is None:
            from kernel.intelligence.copilot_consultant import CopilotConsultant
            self._copilot_consultant = CopilotConsultant(self.gemini, self.builder)
        return self._copilot_consultant

    @property
    def chroma_manager(self):
        if self._chroma_manager is None:
            from kernel.knowledge.chromadb_manager import ChromaDBManager
            self._chroma_manager = ChromaDBManager()
        return self._chroma_manager

    @property
    def knowledge_orchestrator(self):
        if self._knowledge_orchestrator is None:
            from kernel.knowledge.chromadb_manager import KnowledgeOrchestrator
            self._knowledge_orchestrator = KnowledgeOrchestrator(self.chroma_manager)
        return self._knowledge_orchestrator

    @property
    def goal_validator(self):
        if self._goal_validator is None:
            from kernel.integrity.goal_integrity_validator import GoalIntegrityValidator
            self._goal_validator = GoalIntegrityValidator()
        return self._goal_validator

    @property
    def lineage(self):
        if self._lineage is None:
            from kernel.lineage.project_lineage import ProjectLineage
            self._lineage = ProjectLineage(self.base_dir)
        return self._lineage

    @property
    def branch_manager(self):
        if self._branch_manager is None:
            from kernel.lineage.branching import BranchManager
            self._branch_manager = BranchManager(self.projects_dir)
        return self._branch_manager

    @property
    def project_runner(self):
        if self._project_runner is None:
            from kernel.execution.project_runner import ProjectRunner
            self._project_runner = ProjectRunner()
        return self._project_runner

    @property
    def smoke_tester(self):
        if self._smoke_tester is None:
            from kernel.execution.smoke_tester import SmokeTester
            self._smoke_tester = SmokeTester()
        return self._smoke_tester

    @property
    def service_orchestrator(self):
        if self._service_orchestrator is None:
            from kernel.execution.service_orchestrator import ServiceOrchestrator
            self._service_orchestrator = ServiceOrchestrator()
        return self._service_orchestrator

    @property
    def output_generator(self):
        if self._output_generator is None:
            from kernel.outputs.output_generator import OutputGenerator
            self._output_generator = OutputGenerator()
        return self._output_generator

    @property
    def intensity(self):
        if self._intensity is None:
            self._intensity = IntensityOrchestrator()
        return self._intensity

    @property
    def project_types(self):
        if self._project_types is None:
            self._project_types = ProjectTypeRegistry()
        return self._project_types

    @property
    def project_manager(self):
        if self._project_manager is None:
            self._project_manager = ProjectManager(self.base_dir)
        return self._project_manager

    @property
    def git_manager(self):
        if self._git_manager is None:
            from kernel.git_manager import GitManager
            self._git_manager = GitManager()
        return self._git_manager

    @property
    def health(self):
        if self._health is None:
            from kernel.intelligence.context_health_monitor import ContextHealthMonitor
            self._health = ContextHealthMonitor(notify_fn=self._notify)
        return self._health

    @property
    def telegram(self):
        if self._telegram is None:
            from kernel.communication.telegram_gateway import TelegramGateway
            self._telegram = TelegramGateway()
        return self._telegram

    @property
    def vision_capturer(self):
        if self._vision_capturer is None:
            from kernel.vision.vision_capturer import VisionCapturer
            self._vision_capturer = VisionCapturer()
        return self._vision_capturer

    @property
    def visual_inspector(self):
        if self._visual_inspector is None:
            from kernel.vision.visual_inspector import VisualInspector
            self._visual_inspector = VisualInspector(gemini_driver=self.gemini)
        return self._visual_inspector

    @property
    def web_researcher(self):
        if self._web_researcher is None:
            from kernel.external.web_researcher import WebResearcher
            self._web_researcher = WebResearcher()
        return self._web_researcher

    @property
    def import_validator(self):
        if self._import_validator is None:
            from kernel.validation.import_dependency_validator import ImportDependencyValidator
            self._import_validator = ImportDependencyValidator(notify_fn=self._notify)
        return self._import_validator

    @property
    def api_enforcer(self):
        if self._api_enforcer is None:
            from kernel.validation.api_contract_enforcer import APIContractEnforcer
            self._api_enforcer = APIContractEnforcer(notify_fn=self._notify)
        return self._api_enforcer

    @property
    def security_reviewer(self):
        if self._security_reviewer is None:
            from kernel.security.security_reviewer import SecurityReviewer
            self._security_reviewer = SecurityReviewer(self.gemini, self.builder, self._notify)
        return self._security_reviewer

    @property
    def test_generator(self):
        if self._test_generator is None:
            from kernel.testing.test_generator import TestGenerator
            self._test_generator = TestGenerator(self.ollama, self.builder, self._notify)
        return self._test_generator

    @property
    def functional_test_generator(self):
        if self._functional_test_generator is None:
            from kernel.testing.functional_test_generator import FunctionalTestGenerator
            self._functional_test_generator = FunctionalTestGenerator(self.gemini, self.builder, self._notify)
        return self._functional_test_generator

    @property
    def boot_agent(self):
        if self._boot_agent is None:
            from kernel.execution.boot_agent import BootAgent
            self._boot_agent = BootAgent(self.gemini, None, self.builder, self._notify)
        return self._boot_agent

    @property
    def ui_design_agent(self):
        if self._ui_design_agent is None:
            from kernel.design.ui_design_agent import UIDesignAgent
            self._ui_design_agent = UIDesignAgent()
        return self._ui_design_agent

    @property
    def observer(self):
        if self._observer is None:
            from kernel.learning.behavior_observer import BehaviorObserver
            self._observer = BehaviorObserver()
        return self._observer

    @property
    def knowledge_base(self):
        if self._knowledge_base is None:
            from kernel.learning.knowledge_base import KnowledgeBase
            self._knowledge_base = KnowledgeBase()
        return self._knowledge_base

    @property
    def coach(self):
        if self._coach is None:
            from kernel.learning.local_ai_coach import LocalAICoach
            self._coach = LocalAICoach(self.knowledge_base)
        return self._coach

    @property
    def perf_tracker(self):
        if self._perf_tracker is None:
            from kernel.monitoring.performance_tracker import PerformanceTracker
            self._perf_tracker = PerformanceTracker()
        return self._perf_tracker

    @property
    def conformance_verifier(self):
        if self._conformance_verifier is None:
            from kernel.intelligence.conformance_verifier import ConformanceVerifier
            self._conformance_verifier = ConformanceVerifier(self.gemini, self.perf_tracker, notify_fn=self._notify)
        return self._conformance_verifier

    @property
    def template_manager(self):
        if self._template_manager is None:
            from kernel.execution.template_manager import TemplateManager
            self._template_manager = TemplateManager(self.base_dir / "templates")
        return self._template_manager

    @property
    def symbol_generator(self):
        if self._symbol_generator is None:
            from kernel.intelligence.symbol_generator import SymbolGenerator
            self._symbol_generator = SymbolGenerator()
        return self._symbol_generator

    def _load_custom_providers(self) -> None:
        config_path = self.base_dir / "soda_config.json"
        if not config_path.exists(): return
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            for prov in cfg.get("custom_providers", []):
                from kernel.drivers.driver_factory import build_driver
                driver = build_driver(prov.get("name"), prov.get("api_key"), prov.get("model"), prov.get("base_url"), prov.get("driver_type"))
                self.ai_hub.register(prov.get("name").lower(), driver)
        except Exception: pass

    def _save_state(self, project: Project):
        data = {
            "id": project.id, "description": project.description, "state": project.state.value,
            "skills": project.skills, "profile": project.profile, "project_type": project.project_type,
            "capability_packs": project.capability_packs, "intensity_level": project.intensity_level,
            "created_at": project.created_at or datetime.now().isoformat()
        }
        (project.workspace / "metadata.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _new_project(self, description: str, project_name: Optional[str] = None) -> Project:
        project_id = project_name or f"proj_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        workspace = self.projects_dir / project_id
        if workspace.exists():
            project_id = f"{project_id}_{datetime.now().strftime('%H%M%S')}"
            workspace = self.projects_dir / project_id
        workspace.mkdir(parents=True, exist_ok=True)
        project = Project(id=project_id, description=description, workspace=workspace)
        from kernel.persistence.requirements_store import RequirementsStore
        RequirementsStore(workspace).save(description, project_id)
        return project

    def _project_from_disk(self, project_id: str) -> Project:
        workspace = self.projects_dir / project_id
        with open(workspace / "metadata.json", encoding="utf-8") as f:
            data = json.load(f)
        return Project(
            id=data["id"], description=data["description"], state=ProjectState(data["state"]),
            workspace=workspace, skills=data.get("skills", []), profile=data.get("profile", ""),
            project_type=data.get("project_type", "software"), created_at=data.get("created_at", "")
        )

    async def run(self, description: str, project_name: Optional[str] = None, interactive_mode: bool = False) -> Project:
        """Punto de entrada principal. SODA OMEGA asume el control para software."""
        project_type = self.project_types.classify(description)
        if project_type == "software":
            return await self.run_omega_project(description, project_name)
        
        project = self._new_project(description, project_name)
        project.project_type = project_type
        await self._run_non_software_pipeline(project)
        return project

    async def run_omega_project(self, description: str, project_name: Optional[str] = None) -> Project:
        """Ejecuta un proyecto usando el Pipeline SODA OMEGA Morphological."""
        self.perf_tracker.reset()
        project = self._new_project(description, project_name)
        self._active_project = project
        
        # SODA FUSION: Iniciar Rastreador de Misión
        from kernel.utils.mission_tracker import MissionTracker
        from kernel.utils.process_watchdog import ProcessWatchdog
        
        tracker = MissionTracker(project.workspace)
        self.watchdog = ProcessWatchdog(project.id, tracker)
        tracker.log_step("GENESIS", "INIT", "OK", f"Proyecto {project.id} creado.")

        try:
            from kernel.orchestration.mission_intelligence import MissionIntelligence
            mission_profile = MissionIntelligence.analyze_requirement(description)
            
            project.project_type = mission_profile.domain
            project.state = ProjectState.REQUIREMENTS
            self._save_state(project)
            
            self._notify(f"Misión OMEGA {project.id} iniciada. Complejidad: {mission_profile.complexity_score}/10", "START", {"project_id": project.id})
            tracker.log_step("INTELLIGENCE", "PROFILE_ANALYSIS", "OK", f"Complejidad: {mission_profile.complexity_score}")

            self.blackbox = SodaLogger(project.workspace)
            self.ai_hub.blackbox = self.blackbox

            # --- CAPA 0: WISDOM RC3 ---
            from kernel.orchestration.layer0_wisdom import resolve_ambiguities
            self._notify("Iniciando fase de Sabiduría: Analizando requerimientos...", "PHASE_START", {"phase": "wisdom"})

            # Instanciar OmegaEngine para tener el rc3_agent
            omega = OmegaEngine(self.gemini, self.ai_hub, self._notify, project.workspace, mission_profile)

            async def ask_user_wrapper(question: str) -> str:
                tracker.log_step("WISDOM", "ASK_USER", "LOG", question[:50])
                from kernel.communication.user_interaction import get_gateway
                gw = get_gateway()
                return await gw.ask(question, self._notify, workspace=project.workspace)

            final_description = await resolve_ambiguities(
                user_prompt=description,
                gemini_driver=self.gemini,
                ask_user_fn=ask_user_wrapper,
                notify_fn=self._notify,
                ai_hub=self.ai_hub,
                rc3_agent=omega.rc3
            )
            
            # --- VALIDACIÓN PRE-FLIGHT SEMÁNTICA (IMP-023) ---
            self._notify("Ejecutando validación semántica Pre-Flight...", "LOG")
            from kernel.validation.preflight_aligner import PreFlightSemanticAligner
            
            # En modo OMEGA, la descripción final actúa como el primer borrador del plan
            is_aligned, alignment_msg = PreFlightSemanticAligner.verify_alignment(description, final_description)
            if not is_aligned:
                tracker.log_step("INTELLIGENCE", "PREFLIGHT_VAL", "FAIL", alignment_msg)
                self._notify(f"CRÍTICO: Abortando pipeline por desalineación de diseño: {alignment_msg}", "ERROR")
                project.state = ProjectState.FAILED
                self._save_state(project)
                return project
            
            self._notify("✅ Pre-Flight exitoso: Paradigmas alineados.", "SUCCESS")

            project.description = final_description
            self._save_state(project)
            tracker.log_step("WISDOM", "AMBIGUITY_RESOLVED", "OK")

            # 1. Ejecutar el Pipeline RC3 Completo (Indexación + Desarrollo Consensuado)
            self._notify("Iniciando Pipeline RC3: Mando Único del Juez Supremo.", "PHASE_START")
            final_files = await omega.run_omega_pipeline(final_description, project.id)
            
            # 2. Guardar archivos finales
            src_dir = project.workspace / "source"
            src_dir.mkdir(parents=True, exist_ok=True)
            for path, content in final_files.items():
                dest = src_dir / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(_strip_code_fence(content), encoding="utf-8")

            # --- SODA FUSION: Generar Artefactos de Legado (Compatibilidad) ---
            try:
                from kernel.utils.v2_adapters import generate_legacy_artifacts
                # Simular un v2_tree básico para el adaptador
                v2_tree_simulado = {
                    "ROOT-000": {
                        "title": project.id,
                        "description": project.description,
                        "level": 0,
                        "is_atomic": False
                    }
                }
                # Añadir secciones como nodos atómicos
                index_path = project.workspace / "master_index.json"
                if index_path.exists():
                    idx_data = json.loads(index_path.read_text(encoding="utf-8"))
                    for sec in idx_data.get("sections", []):
                        v2_tree_simulado[sec["id"]] = {
                            "title": sec["title"],
                            "description": sec["description"],
                            "is_atomic": True,
                            "target_files": sec.get("target_files", [])
                        }
                
                generate_legacy_artifacts(v2_tree_simulado, project.skills, str(project.workspace))
                self._log("SUCCESS", "Artefactos de legado generados (blueprint.json, topology.json).")
            except Exception as e:
                self._log("WARNING", f"No se pudieron generar artefactos de legado: {e}")

            tracker.log_step("OMEGA", "RC3_DONE", "OK", f"{len(final_files)} archivos generados.")
            
            # --- CROSS-CHECK RELAY-TO-DISK (IMP-021) ---
            self._notify("Iniciando auditoría de consistencia Relay-to-Disk...", "LOG")
            # Consolidar todas las notas de relevo del proyecto
            index_path = project.workspace / "master_index.json"
            if index_path.exists():
                idx_data = json.loads(index_path.read_text(encoding="utf-8"))
                combined_notes = " ".join([sec.get("relay_note", "") for sec in idx_data.get("sections", []) if sec.get("relay_note")])
                
                integrity_ok, issues = self.code_gen.verify_relay_to_disk_integrity(src_dir, combined_notes)
                if not integrity_ok:
                    warn_msg = f"Detectados archivos prometidos ausentes o corruptos: {', '.join(issues)}"
                    self._notify(warn_msg, "HEALTH_WARN")
                    tracker.log_step("INTEGRITY", "RELAY_CHECK", "WARN", warn_msg)

            # 3. Boot y Finalización
            await self._phase_boot_agent_v2(project)
            tracker.log_step("GENESIS", "MISSION_DONE", "OK")

            project.state = ProjectState.DONE
            self._save_state(project)
            return project

        except Exception as e:
            tracker.log_step("KERNEL", "CRITICAL_ERROR", "FAIL", str(e))
            self._notify(f"Fallo en Pipeline OMEGA: {e}", "ERROR")
            project.state = ProjectState.FAILED
            self._save_state(project)
            return project
        finally:
            # LIMPIEZA DETERMINÍSTICA DE RECURSOS
            self.watchdog.kill_all()

    async def resume(self, project_id: str) -> Project:
        """Reanuda un proyecto existente utilizando el motor OMEGA."""
        project = self._project_from_disk(project_id)
        self._active_project = project
        self._notify(f"Reanudando proyecto OMEGA {project_id}...", "START", {"project_id": project.id})
        
        if project.project_type != "software" and project.project_type != "systems":
            await self._run_non_software_pipeline(project)
            return project

        try:
            from kernel.orchestration.mission_intelligence import MissionIntelligence
            mission_profile = MissionIntelligence.analyze_requirement(project.description)
            omega = OmegaEngine(self.gemini, self.ai_hub, self._notify, project.workspace, mission_profile)
            final_files = await omega.run_omega_pipeline(project.description, project.id)
            
            src_dir = project.workspace / "source"
            for path, content in final_files.items():
                dest = src_dir / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(_strip_code_fence(content), encoding="utf-8")

            await self._phase_boot_agent_v2(project)
            project.state = ProjectState.DONE
            self._save_state(project)
            self._notify("Reanudación OMEGA completada.", "SUCCESS", {"project_id": project.id})
            return project
        except Exception as e:
            self._notify(f"Fallo al reanudar misión OMEGA: {e}", "ERROR")
            project.state = ProjectState.FAILED
            self._save_state(project)
            return project

    async def _run_non_software_pipeline(self, project: Project) -> None:
        try:
            self._notify(f"Iniciando Pipeline No-Software ({project.project_type})...", "PHASE_START")
            from kernel.orchestration.layer0_wisdom import resolve_ambiguities
            
            async def ask_user_wrapper(question: str) -> str:
                from kernel.communication.user_interaction import get_gateway
                gw = get_gateway()
                self._notify(f"Esperando respuesta del usuario: {question[:50]}...", "LOG")
                return await gw.ask(question, self._notify, workspace=project.workspace)

            final_description = await resolve_ambiguities(project.description, self.gemini, ask_user_wrapper, self._notify, "gemini-2.5-flash")
            project.description = final_description
            self._save_state(project)

            resp = await self.gemini.call("Eres un consultor experto. Genera un entregable Markdown.", final_description)
            src_dir = project.workspace / "source"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / f"{project.project_type}_entregable.md").write_text(resp.content, encoding="utf-8")

            project.state = ProjectState.DONE
            self._save_state(project)
            self._notify("Pipeline de no-software finalizado.", "DONE", {"project_id": project.id})
        except Exception as e:
            self._notify(f"Error en no-software: {e}", "ERROR")
            project.state = ProjectState.FAILED
            self._save_state(project)

    async def _phase_boot_agent_v2(self, project: Project) -> None:
        self._notify("BootAgent: instalando y arrancando proyecto…", "PHASE_START")
        source_dir = project.workspace / "source"
        if not source_dir.exists(): return
        try:
            report = await self.boot_agent.run(source_dir, project.architecture, project.blueprint)
            (project.workspace / "boot_report.json").write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
            if report.final_ok:
                self._notify("Aplicación corriendo exitosamente.", "APP_RUNNING", {"project_id": project.id})
                project.state = ProjectState.DONE
            else:
                self._notify(f"BootAgent falló: {report.reason}", "WARNING")
                project.state = ProjectState.BOOT_FAILED
            self._save_state(project)
        except Exception as e:
            self._notify(f"BootAgent error: {e}", "ERROR")
            project.state = ProjectState.BOOT_FAILED
            self._save_state(project)

if __name__ == "__main__":
    orch = SodaOrchestrator()
    asyncio.run(orch.run("Test project"))
