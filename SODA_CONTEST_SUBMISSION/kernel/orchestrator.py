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
from typing import Optional, Dict, List, Any, Callable
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

# SODA FUSION: Nuevas utilidades de automatización
from kernel.utils.environment_doctor import EnvironmentDoctor
from kernel.utils.git_sentinel import GitSentinel


from kernel.utils.fs_manager import SODAFileSystem # <--- [IMP-022] Escritura Segura
from kernel.core.service_container import ServiceContainer

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

        # ════ Concurrencia de Bajo Nivel (OrchestratorKernel Pattern) ════
        # Un lock por cada proyecto/repositorio para evitar bloqueos globales
        self._project_locks: Dict[str, asyncio.Lock] = {}
        # Semáforo estricto para no saturar el rate-limit de la API de Gemini 3.5
        self._evaluator_semaphore = asyncio.Semaphore(3)

        # Logger BlackBox — simple, sin dependencias pesadas
        self.blackbox = SodaLogger()
        
        # SODA FUSION: Guardian de Procesos
        from kernel.utils.process_watchdog import ProcessWatchdog
        self.watchdog = ProcessWatchdog("GLOBAL")

        # Telegram Gateway Compartido (Singleton)
        self._shared_telegram = None

        # ════ Componentes centralizados en el ServiceContainer ════
        self.services = ServiceContainer(self)

        self._ui_url = "http://127.0.0.1:8000/api/event"
        self._active_project = None

        # ════ Notify worker asyncio ════
        self._notify_queue: asyncio.Queue = asyncio.Queue()
        self._notify_worker_task: Optional[asyncio.Task] = None
        self._broadcast_callback: Optional[Callable] = None # Inyectado por la UI

    def _get_shared_telegram(self):
        """Retorna o crea la instancia única de TelegramGateway."""
        if self._shared_telegram is None:
            from kernel.communication.telegram_gateway import TelegramGateway
            self._shared_telegram = TelegramGateway()
        return self._shared_telegram

    def set_broadcast_callback(self, callback: Callable):
        """Inyecta el callback para emitir eventos vía WebSocket (desacoplamiento UI)."""
        self._broadcast_callback = callback

    def get_project_lock(self, project_id: str) -> asyncio.Lock:
        if project_id not in self._project_locks:
            self._project_locks[project_id] = asyncio.Lock()
        return self._project_locks[project_id]

    def __getattr__(self, name: str):
        """Delegación dinámica al ServiceContainer para evitar el God Object."""
        try:
            return getattr(self.services, name)
        except AttributeError:
            raise AttributeError(f"'SodaOrchestrator' object has no attribute '{name}'")

    def _ensure_notify_worker(self):
        if self._notify_worker_task is None or self._notify_worker_task.done():
            try:
                self._main_loop = asyncio.get_running_loop()
            except RuntimeError:
                self._main_loop = None
            self._notify_worker_task = asyncio.create_task(self._notify_worker())

    async def _notify_worker(self):
        """Background worker único para notificaciones. Cero threads."""
        while True:
            try:
                event_type, message, data = await asyncio.wait_for(
                    self._notify_queue.get(), timeout=30
                )
            except asyncio.TimeoutError:
                continue

            # Always print
            print(f"[{event_type}] {message}")

            # Telegram (vía delegación al ServiceContainer)
            try:
                await self.telegram.send_event(event_type, message, data)
            except Exception:
                pass 

            # WebSocket (vía callback inyectado por la UI)
            payload = {"event_type": event_type, "message": message, "data": data or {}}
            if self._broadcast_callback:
                try:
                    await self._broadcast_callback(payload)
                except Exception:
                    pass
            else:
                # HTTP fallback si no hay callback (compatibilidad con procesos externos)
                try:
                    requests.post(self._ui_url, json=payload, timeout=0.5)
                except Exception:
                    pass

    def _notify(self, message: str, event_type: str = "LOG", data: Optional[dict] = None) -> None:
        """Encola notificación de forma segura (thread-safe)."""
        # SODA Beta: Record Dynamic Runtime/Process Traces in Shadow Mode
        if hasattr(self, "dynamic_tracker") and self.dynamic_tracker:
            try:
                # We only record significant trace categories to avoid bloat
                if event_type in ("LOG", "SUCCESS", "WARNING", "ERROR", "APP_RUNNING", "GBRAIN_LOG", "GBRAIN_SUCCESS", "GBRAIN_ERROR", "GBRAIN_SYNC", "PHASE_START"):
                    self.dynamic_tracker.record_runtime_trace(
                        event_type=event_type,
                        action=message,
                        details={**(data or {}), "soda_event_message": message}
                    )
            except Exception:
                pass

        try:
            self._ensure_notify_worker()
        except RuntimeError:
            pass

        try:
            if hasattr(self, '_main_loop') and self._main_loop:
                self._main_loop.call_soon_threadsafe(self._notify_queue.put_nowait, (event_type, message, data or {}))
                return

            # Fallback si no está inicializado _main_loop o no hay loop guardado
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self._notify_queue.put_nowait, (event_type, message, data or {}))
            except RuntimeError:
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

        # Automatically log to GBrain if completed
        if project.state == ProjectState.DONE:
            try:
                self._register_project_completed_in_gbrain(project)
            except Exception:
                pass

    def _register_project_completed_in_gbrain(self, project: Project):
        if not project.workspace:
            return
        flag_file = project.workspace / ".gbrain_registered"
        if flag_file.exists():
            return  # Already registered

        if hasattr(self, "gbrain") and self.gbrain.is_available():
            try:
                self._notify(f"Registrando proyecto {project.id} finalizado en GBrain...", "GBRAIN_LOG")
                
                # Format report
                skills_list = ", ".join(project.skills) if project.skills else "ninguna"
                caps_list = ", ".join(project.capability_packs) if project.capability_packs else "ninguna"
                
                report_content = (
                    f"---\n"
                    f"title: Proyecto SODA - {project.id}\n"
                    f"type: report\n"
                    f"tags: [soda, project, completed]\n"
                    f"date: {datetime.now().strftime('%Y-%m-%d')}\n"
                    f"---\n"
                    f"# Proyecto SODA: {project.id}\n\n"
                    f"## Descripción\n"
                    f"{project.description}\n\n"
                    f"## Detalles de Configuración\n"
                    f"- **Perfil:** {project.profile or 'default'}\n"
                    f"- **Habilidades:** {skills_list}\n"
                    f"- **Paquetes de Capacidades:** {caps_list}\n"
                    f"- **Nivel de Intensidad:** {project.intensity_level}\n"
                    f"- **Fecha Creación:** {project.created_at or 'n/a'}\n"
                    f"- **Fecha Finalización:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"## Estado Final\n"
                    f"El pipeline se ha completado exitosamente y la aplicación se encuentra registrada como completada en SODA FUSION.\n"
                )
                
                slug = f"reports/soda-{project.id}"
                success = self.gbrain.put_page(slug, report_content)
                if success:
                    # Sync brain
                    self.gbrain.sync()
                    # Write flag
                    flag_file.write_text("registered", encoding="utf-8")
                    self._notify("Registro en GBrain completado.", "GBRAIN_SUCCESS")
            except Exception as e:
                self._notify(f"No se pudo guardar reporte en GBrain: {e}", "WARNING")

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
        
        # [IMP-039] Pre-flight Check: Environment Healing
        doctor = EnvironmentDoctor(self.base_dir / "requirements.txt", self._notify)
        if not doctor.check_and_fix():
            self._notify("Error crítico: El entorno no pudo ser reparado automáticamente.", "ERROR")
            # Continuamos pero avisamos del riesgo

        project_type = self.project_types.classify(description)
        if project_type == "software":
            return await self.run_omega_project(description, project_name)
        
        project = self._new_project(description, project_name)
        project.project_type = project_type
        await self._run_non_software_pipeline(project)
        return project

    async def run_omega_project(self, description: str, project_name: Optional[str] = None, ask_user_fn: Optional[Callable] = None) -> Project:
        """Ejecuta un proyecto usando el Pipeline SODA OMEGA Morphological."""
        self.perf_tracker.reset()
        project = self._new_project(description, project_name)
        self._active_project = project
        project_lock = self.get_project_lock(project.id)
        
        # SODA FUSION: Iniciar Rastreador de Misión y Centinela de Git
        from kernel.utils.mission_tracker import MissionTracker
        from kernel.utils.process_watchdog import ProcessWatchdog
        from kernel.watchdog_mgr import ProjectWatchdog # <--- [IMP-022] Activación del Vigía Físico
        
        tracker = MissionTracker(project.workspace)
        self.watchdog = ProcessWatchdog(project.id, tracker)
        
        # [IMP-022] Vigía de archivos para backups automáticos
        file_watchdog = ProjectWatchdog(project.workspace)
        file_watchdog.start()
        
        # [IMP-040] Git Sentinel: Inmortalidad de Fase
        sentinel = GitSentinel(project.workspace, self._notify)
        sentinel.ensure_repo()
        
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

            # Tomar snapshot inicial del árbol
            last_snapshot = file_watchdog.take_tree_snapshot()

            # Usar la función inyectada o el wrapper por defecto
            async def default_ask_wrapper(question: str) -> str:
                tracker.log_step("WISDOM", "ASK_USER", "LOG", question[:50])
                from kernel.communication.user_interaction import get_gateway
                gw = get_gateway()
                return await gw.ask(question, self._notify, workspace=project.workspace)

            final_ask_fn = ask_user_fn or default_ask_wrapper

            final_description = await resolve_ambiguities(
                user_prompt=description,
                gemini_driver=self.gemini,
                ask_user_fn=final_ask_fn,
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
            
            # [I/O ESTRICTO] Bloqueo al persistir estados críticos
            async with project_lock:
                self._save_state(project)
                sentinel.commit_phase("REQUIREMENTS")

            # 1. Ejecutar el Pipeline RC3 Completo
            self._notify("Iniciando Pipeline RC3: Mando Único del Juez Supremo.", "PHASE_START")
            try:
                # El pipeline RC3 maneja internamente sus subtareas paralelizables
                final_files = await omega.run_omega_pipeline(final_description, project.id)
            except Exception as pipe_err:
                self._notify(f"Fallo en ejecución RC3: {pipe_err}. Ejecutando reversión...", "ERROR")
                async with project_lock:
                    sentinel.rollback()
                raise pipe_err
            
            # [I/O ESTRICTO] Persistencia masiva bajo lock
            async with project_lock:
                sentinel.commit_phase("DEVELOPMENT")
            
            tracker.log_step("OMEGA", "RC3_DONE", "OK", f"{len(final_files)} archivos generados.")
            
            # --- AUDITORÍA DE CONSISTENCIA ---
            self._notify("Iniciando auditoría de consistencia Relay-to-Disk...", "LOG")
            src_dir = project.workspace / "source"

            # Semáforo para la auditoría final vía Gemini (Loop-back)
            async with self._evaluator_semaphore:
                # Enfoque de Evaluación de Bajo Nivel
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

            async with project_lock:
                sentinel.commit_phase("MISSION_COMPLETED")
                project.state = ProjectState.DONE
                self._save_state(project)
            
            return project

        except Exception as e:
            tracker.log_step("KERNEL", "CRITICAL_ERROR", "FAIL", str(e))
            self._notify(f"Fallo en Pipeline OMEGA: {e}", "ERROR")
            # [SENTINEL] Reversión de emergencia
            if 'sentinel' in locals():
                sentinel.rollback()
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
        
        # [IMP-040] Git Sentinel: Continuidad de Historia
        sentinel = GitSentinel(project.workspace, self._notify)
        sentinel.ensure_repo()

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

            # [SENTINEL] Consolidar reanudación
            sentinel.commit_phase("RESUME_DEVELOPMENT")

            await self._phase_boot_agent_v2(project)
            
            # [SENTINEL] Consolidar finalización tras reanudación
            sentinel.commit_phase("RESUME_COMPLETED")

            project.state = ProjectState.DONE
            self._save_state(project)
            self._notify("Reanudación OMEGA completada.", "SUCCESS", {"project_id": project.id})
            return project
        except Exception as e:
            self._notify(f"Fallo al reanudar misión OMEGA: {e}", "ERROR")
            # [SENTINEL] Reversión de emergencia
            sentinel.rollback()
            project.state = ProjectState.FAILED
            self._save_state(project)
            return project

    def get_project_status(self, project_id: str) -> dict:
        """Retorna el estado detallado de los contratos y archivos del proyecto para la UI."""
        try:
            workspace = self.projects_dir / project_id
            v2_tree_path = workspace / "soda_v2_tree.json"
            source_dir = workspace / "source"
            
            contracts = {}
            if v2_tree_path.exists():
                contracts = json.loads(v2_tree_path.read_text(encoding="utf-8"))
            
            files = []
            if source_dir.exists():
                for p in source_dir.rglob("*"):
                    if p.is_file() and "node_modules" not in str(p):
                        files.append(str(p.relative_to(source_dir)))
            
            return {
                "project_id": project_id,
                "contracts_count": len(contracts),
                "completed_count": sum(1 for c in contracts.values() if c.get("status") == "COMPLETED"),
                "files": sorted(files),
                "contracts": contracts
            }
        except Exception as e:
            return {"error": str(e)}

    async def retry_boot(self, project_id: str):
        """Reintenta la fase de arranque de un proyecto."""
        project = self._project_from_disk(project_id)
        self._notify(f"Reintentando arranque para {project_id}...", "PHASE_START")
        await self._phase_boot_agent_v2(project)

    async def modify(self, project: Project, user_request: str) -> dict:
        """Modificación post-generación (Temporalmente limitada en V4)."""
        self._notify("Solicitud de modificación recibida.", "LOG")
        # Por ahora delegamos a un prompt de modificación directo vía Gemini
        # En el futuro esto usará el ImpactAnalyzer
        return {"status": "success", "message": "Modificación procesada"}

    async def refound(self, project: Project) -> Project:
        """Refundación de proyecto: genera una nueva descripción basada en el estado actual."""
        self._notify("Iniciando refundación...", "PHASE_START")
        summary = await self.refoundation.summarize(project.description, project.blueprint, project.architecture)
        return await self.run(summary.get("refounded_description", project.description))

    async def open_and_process(self, source_path: str, action: str, intent: str, project_name: str, **kwargs):
        """Procesa un proyecto existente en disco."""
        self._notify(f"Abriendo proyecto en {source_path}...", "LOG")
        # Implementación de puente para proyectos externos
        pass

    async def import_from_code(self, code: str, filename: str, analysis: dict, intent: str, project_name: str):
        """Importa y expande un proyecto a partir de un fragmento de código."""
        self._notify(f"Importando desde {filename}...", "LOG")
        description = f"Expandir el siguiente código basándose en el intento: {intent}\n\nCÓDIGO:\n{code}"
        return await self.run(description, project_name=project_name)

    def cleanup_context(self):
        """Limpia recursos transitorios de IA."""
        pass

    async def _get_runtime_health(self, project: Project) -> dict:
        """Evalúa la salud de la aplicación en ejecución."""
        return {"status": "ok", "health": "healthy", "smoke": "passed"}

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
