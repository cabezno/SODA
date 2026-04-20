import asyncio
import json
import sys
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kernel.drivers.claude_driver import ClaudeDriver
from kernel.drivers.gemini_driver import GeminiDriver
from kernel.drivers.ollama_driver import OllamaDriver
from kernel.context.context_builder import ContextBuilder


class ProjectState(Enum):
    IDLE = "idle"
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

    # --- Utilidades ---

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extrae JSON de una respuesta que puede venir envuelta en markdown."""
        import re
        # Intentar parsear directo
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Buscar bloque ```json ... ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Buscar primer { ... } en el texto
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {"raw": text}

    # --- Gestión de proyectos ---

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
                "created_at": project.created_at,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # --- Llamadas a modelos ---

    async def _call_claude(self, role: str, task: str) -> str:
        payload = self.builder.build_payload("claude", role, task)
        return await self.claude.prompt(payload["system"], payload["user"])

    async def _call_gemini(self, role: str, task: str) -> str:
        payload = self.builder.build_payload("gemini", role, task)
        return await asyncio.to_thread(self.gemini.prompt, payload["system"], payload["user"])

    async def _call_ollama(self, role: str, task: str) -> str:
        payload = self.builder.build_payload("ollama", role, task)
        return await self.ollama.prompt(payload["system"], payload["user"])

    async def _call_with_escalation(self, role: str, task: str, project: Project) -> str:
        """Intenta con Qwen local hasta MAX_LOCAL_RETRIES, luego escala a Claude."""
        for attempt in range(1, self.MAX_LOCAL_RETRIES + 1):
            print(f"  [Qwen] Intento {attempt}/{self.MAX_LOCAL_RETRIES}...")
            result = await self._call_ollama(role, task)
            if "Error" not in result:
                return result
            print(f"  [!] Fallo en intento {attempt}: {result[:80]}")

        print("  [↑] Escalando a Claude Sonnet...")
        result = await self._call_claude(role, task)
        if "Error" not in result:
            return result

        project.state = ProjectState.FAILED
        raise RuntimeError(
            f"Todos los modelos fallaron para el rol '{role}'. Checkpoint humano requerido."
        )

    # --- Fases ---

    async def _phase_requirements(self, project: Project) -> None:
        print("\n[FASE 1] Requerimientos — entrevistando con Claude Sonnet...")
        project.state = ProjectState.REQUIREMENTS

        response = await self._call_claude("requirements_interviewer", project.description)

        project.blueprint = self._extract_json(response)

        out = project.workspace / "blueprint.json"
        out.write_text(json.dumps(project.blueprint, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [✓] Blueprint → {out}")
        self._save_state(project)

    async def _phase_architecture(self, project: Project) -> None:
        print("\n[FASE 2] Arquitectura — diseñando con Gemini Pro...")
        project.state = ProjectState.ARCHITECTURE

        blueprint_str = json.dumps(project.blueprint, ensure_ascii=False)
        response = await self._call_gemini("global_architect", blueprint_str)

        project.architecture = self._extract_json(response)

        out = project.workspace / "architecture.json"
        out.write_text(json.dumps(project.architecture, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [✓] Arquitectura → {out}")
        self._save_state(project)

    # --- Entry point ---

    async def run(self, description: str) -> Project:
        project = self._new_project(description)
        print(f"\n{'='*55}")
        print(f"SODA — Proyecto: {project.id}")
        print(f"Descripción: {description[:80]}")
        print(f"{'='*55}")

        await self._phase_requirements(project)

        print(f"\n[CHECKPOINT 1] Blueprint listo.")
        print(f"  Revisar en: {project.workspace / 'blueprint.json'}")
        print("  Continuando a arquitectura...")

        await self._phase_architecture(project)

        print(f"\n[CHECKPOINT 2] Arquitectura lista.")
        print(f"  Revisar en: {project.workspace / 'architecture.json'}")

        project.state = ProjectState.DONE
        self._save_state(project)
        print(f"\n[✓] Pipeline completado. Workspace: {project.workspace}")
        return project


if __name__ == "__main__":
    orchestrator = SodaOrchestrator()
    asyncio.run(orchestrator.run(
        "Quiero una app web CRUD simple para gestionar una lista de tareas: "
        "crear, leer, actualizar y eliminar tareas con título, descripción y estado."
    ))
