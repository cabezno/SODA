import asyncio
from pathlib import Path
from typing import Optional, Any, Callable

class ServiceContainer:
    """
    Inyector de Dependencias centralizado para SODA FUSION.
    Gestiona el ciclo de vida de los agentes, drivers y servicios del kernel.
    """
    def __init__(self, orchestrator):
        self.orch = orchestrator
        self._instances = {}

    def _get_or_create(self, key: str, factory: Callable) -> Any:
        if key not in self._instances:
            self._instances[key] = factory()
        return self._instances[key]

    @property
    def builder(self):
        from kernel.context.context_builder import ContextBuilder
        return self._get_or_create("builder", lambda: ContextBuilder())

    @property
    def gemini(self):
        from kernel.drivers.gemini_driver import GeminiDriver
        from kernel.drivers.provider_hub import AIProxy
        return self._get_or_create("gemini", lambda: AIProxy(GeminiDriver(), "gemini-2.5-flash", self.orch.blackbox))

    @property
    def ollama(self):
        return self.gemini

    @property
    def deepseek(self):
        return self.gemini

    @property
    def ai_hub(self):
        def _factory():
            from kernel.drivers.provider_hub import AIProviderHub, ModelLockedProxy
            
            hub = AIProviderHub(
                providers={
                    "gemini": self.gemini,
                    "ollama": ModelLockedProxy(self.gemini, "gemini-2.5-flash"),
                    "claude": ModelLockedProxy(self.gemini, "gemini-2.5-pro"),
                    "deepseek": ModelLockedProxy(self.gemini, "gemini-2.5-pro"),
                },
                routes=self.orch._load_ai_routing(),
            )
            hub.blackbox = self.orch.blackbox
            return hub
        return self._get_or_create("ai_hub", _factory)

    @property
    def code_gen(self):
        def _factory():
            from kernel.code_generator import CodeGenerator
            cg = CodeGenerator(self.ollama, self.gemini)
            cg.observer = self.orch.observer
            cg.coach = self.orch.coach
            cg.notify = self.orch._notify
            cg.orch = self.orch
            return cg
        return self._get_or_create("code_gen", _factory)

    @property
    def capability_pack_registry(self):
        from kernel.capabilities.capability_packs import CapabilityPackRegistry
        return self._get_or_create("capability_pack_registry", lambda: CapabilityPackRegistry())

    @property
    def skill_matcher(self):
        from kernel.capabilities.skill_matcher import SkillMatcher
        return self._get_or_create("skill_matcher", lambda: SkillMatcher(self.gemini, self.builder))

    @property
    def profile_matcher(self):
        from kernel.capabilities.profile_matcher import ProfileMatcher
        return self._get_or_create("profile_matcher", lambda: ProfileMatcher(self.gemini, self.builder))

    @property
    def skill_manager(self):
        from kernel.capabilities.skill_manager import SkillManager
        return self._get_or_create("skill_manager", lambda: SkillManager(self.skill_matcher))

    @property
    def profile_manager(self):
        from kernel.capabilities.profile_manager import ProfileManager
        return self._get_or_create("profile_manager", lambda: ProfileManager(self.profile_matcher))

    @property
    def liaison_agent(self):
        def _factory():
            from kernel.intelligence.liaison_agent import LiaisonAgent
            return LiaisonAgent(
                gemini_driver=self.gemini,
                ai_hub=self.ai_hub,
                workspace=self.orch._active_project.workspace if self.orch._active_project else None,
                notify_fn=self.orch._notify,
                orchestrator=self.orch
            )
        return self._get_or_create("liaison_agent", _factory)

    @property
    def wisdom_agent(self):
        from kernel.intelligence.wisdom_agent import WisdomAgent
        return self._get_or_create("wisdom_agent", lambda: WisdomAgent(self.gemini, self.builder, ai_hub=self.ai_hub, notify_fn=self.orch._notify, orchestrator=self.orch))

    @property
    def goal_interpreter(self):
        from kernel.intelligence.goal_interpreter import GoalInterpreter
        return self._get_or_create("goal_interpreter", lambda: GoalInterpreter(self.gemini, self.builder))

    @property
    def impact_analyzer(self):
        from kernel.intelligence.impact_analyzer import ImpactAnalyzer
        return self._get_or_create("impact_analyzer", lambda: ImpactAnalyzer(self.gemini, self.builder))

    @property
    def reference_analyzer(self):
        from kernel.intelligence.reference_analyzer import ReferenceAnalyzer
        return self._get_or_create("reference_analyzer", lambda: ReferenceAnalyzer())

    @property
    def refoundation(self):
        from kernel.intelligence.refoundation import RefoundationEngine
        return self._get_or_create("refoundation", lambda: RefoundationEngine(self.gemini, self.builder))

    @property
    def profile_evolution(self):
        from kernel.capabilities.profile_evolution import ProfileEvolutionEngine
        return self._get_or_create("profile_evolution", lambda: ProfileEvolutionEngine(self.gemini, self.builder))

    @property
    def copilot_consultant(self):
        from kernel.intelligence.copilot_consultant import CopilotConsultant
        return self._get_or_create("copilot_consultant", lambda: CopilotConsultant(self.gemini, self.builder))

    @property
    def chroma_manager(self):
        from kernel.knowledge.chromadb_manager import ChromaDBManager
        return self._get_or_create("chroma_manager", lambda: ChromaDBManager())

    @property
    def knowledge_orchestrator(self):
        from kernel.knowledge.chromadb_manager import KnowledgeOrchestrator
        return self._get_or_create("knowledge_orchestrator", lambda: KnowledgeOrchestrator(self.chroma_manager))

    @property
    def goal_validator(self):
        from kernel.integrity.goal_integrity_validator import GoalIntegrityValidator
        return self._get_or_create("goal_validator", lambda: GoalIntegrityValidator())

    @property
    def lineage(self):
        from kernel.lineage.project_lineage import ProjectLineage
        return self._get_or_create("lineage", lambda: ProjectLineage(self.orch.base_dir))

    @property
    def branch_manager(self):
        from kernel.lineage.branching import BranchManager
        return self._get_or_create("branch_manager", lambda: BranchManager(self.orch.projects_dir))

    @property
    def project_runner(self):
        from kernel.execution.project_runner import ProjectRunner
        return self._get_or_create("project_runner", lambda: ProjectRunner())

    @property
    def smoke_tester(self):
        from kernel.execution.smoke_tester import SmokeTester
        return self._get_or_create("smoke_tester", lambda: SmokeTester())

    @property
    def service_orchestrator(self):
        from kernel.execution.service_orchestrator import ServiceOrchestrator
        return self._get_or_create("service_orchestrator", lambda: ServiceOrchestrator())

    @property
    def output_generator(self):
        from kernel.outputs.output_generator import OutputGenerator
        return self._get_or_create("output_generator", lambda: OutputGenerator())

    @property
    def intensity(self):
        from kernel.orchestration.intensity_orchestrator import IntensityOrchestrator
        return self._get_or_create("intensity", lambda: IntensityOrchestrator())

    @property
    def project_types(self):
        from kernel.projects.project_types import ProjectTypeRegistry
        return self._get_or_create("project_types", lambda: ProjectTypeRegistry())

    @property
    def project_manager(self):
        from kernel.projects.project_manager import ProjectManager
        return self._get_or_create("project_manager", lambda: ProjectManager(self.orch.base_dir))

    @property
    def git_manager(self):
        from kernel.git_manager import GitManager
        return self._get_or_create("git_manager", lambda: GitManager())

    @property
    def health(self):
        from kernel.intelligence.context_health_monitor import ContextHealthMonitor
        return self._get_or_create("health", lambda: ContextHealthMonitor(notify_fn=self.orch._notify))

    @property
    def telegram(self):
        # Evitar conflictos de múltiples instancias: usar la que ya tenga el orquestador o la UI
        return self._get_or_create("telegram", lambda: self.orch._get_shared_telegram())

    @property
    def vision_capturer(self):
        from kernel.vision.vision_capturer import VisionCapturer
        return self._get_or_create("vision_capturer", lambda: VisionCapturer())

    @property
    def visual_inspector(self):
        from kernel.vision.visual_inspector import VisualInspector
        return self._get_or_create("visual_inspector", lambda: VisualInspector(gemini_driver=self.gemini))

    @property
    def web_researcher(self):
        from kernel.external.web_researcher import WebResearcher
        return self._get_or_create("web_researcher", lambda: WebResearcher())

    @property
    def import_validator(self):
        from kernel.validation.import_dependency_validator import ImportDependencyValidator
        return self._get_or_create("import_validator", lambda: ImportDependencyValidator(notify_fn=self.orch._notify))

    @property
    def api_enforcer(self):
        from kernel.validation.api_contract_enforcer import APIContractEnforcer
        return self._get_or_create("api_enforcer", lambda: APIContractEnforcer(notify_fn=self.orch._notify))

    @property
    def security_reviewer(self):
        from kernel.security.security_reviewer import SecurityReviewer
        return self._get_or_create("security_reviewer", lambda: SecurityReviewer(self.gemini, self.builder, self.orch._notify))

    @property
    def test_generator(self):
        from kernel.testing.test_generator import TestGenerator
        return self._get_or_create("test_generator", lambda: TestGenerator(self.ollama, self.builder, self.orch._notify))

    @property
    def functional_test_generator(self):
        from kernel.testing.functional_test_generator import FunctionalTestGenerator
        return self._get_or_create("functional_test_generator", lambda: FunctionalTestGenerator(self.gemini, self.builder, self.orch._notify))

    @property
    def boot_agent(self):
        from kernel.execution.boot_agent import BootAgent
        return self._get_or_create("boot_agent", lambda: BootAgent(self.gemini, None, self.builder, self.orch._notify))

    @property
    def ui_design_agent(self):
        from kernel.design.ui_design_agent import UIDesignAgent
        return self._get_or_create("ui_design_agent", lambda: UIDesignAgent())

    @property
    def observer(self):
        from kernel.learning.behavior_observer import BehaviorObserver
        return self._get_or_create("observer", lambda: BehaviorObserver())

    @property
    def knowledge_base(self):
        from kernel.learning.knowledge_base import KnowledgeBase
        return self._get_or_create("knowledge_base", lambda: KnowledgeBase())

    @property
    def coach(self):
        from kernel.learning.local_ai_coach import LocalAICoach
        return self._get_or_create("coach", lambda: LocalAICoach(self.knowledge_base))

    @property
    def perf_tracker(self):
        from kernel.monitoring.performance_tracker import PerformanceTracker
        return self._get_or_create("perf_tracker", lambda: PerformanceTracker())

    @property
    def telemetry(self):
        from kernel.monitoring.hardware_telemetry import HardwareTelemetry
        return self._get_or_create("telemetry", lambda: HardwareTelemetry())

    @property
    def conformance_verifier(self):
        from kernel.intelligence.conformance_verifier import ConformanceVerifier
        return self._get_or_create("conformance_verifier", lambda: ConformanceVerifier(self.gemini, self.perf_tracker, notify_fn=self.orch._notify))

    @property
    def template_manager(self):
        from kernel.execution.template_manager import TemplateManager
        return self._get_or_create("template_manager", lambda: TemplateManager(self.orch.base_dir / "templates"))

    @property
    def symbol_generator(self):
        from kernel.intelligence.symbol_generator import SymbolGenerator
        return self._get_or_create("symbol_generator", lambda: SymbolGenerator())

    @property
    def gbrain(self):
        from kernel.knowledge.gbrain_service import GBrainService
        return self._get_or_create("gbrain", lambda: GBrainService(self.orch))

    @property
    def observatory(self):
        from soda_beta.observatory.hooks import SODAObservatory
        return self._get_or_create("observatory", lambda: SODAObservatory())

    @property
    def dynamic_tracker(self):
        from soda_beta.observatory.dynamic_tracker import DynamicTracker
        return self._get_or_create("dynamic_tracker", lambda: DynamicTracker())
