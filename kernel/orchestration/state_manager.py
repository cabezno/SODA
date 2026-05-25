import json
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime

class ProjectState(Enum):
    IDLE = "idle"
    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    PLANNING = "planning"
    DEVELOPMENT = "development"
    INTEGRATION = "integration"
    DONE = "done"
    FAILED = "failed"
    BOOT_FAILED = "boot_failed"

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
    intensity_level: str = "medium"
    goal_tree: dict = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["state"] = self.state.value
        d["workspace"] = str(self.workspace) if self.workspace else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'Project':
        data["state"] = ProjectState(data["state"])
        if data.get("workspace"):
            data["workspace"] = Path(data["workspace"])
        return cls(**data)

class StateManager:
    """
    Gestiona la persistencia y transiciones de estado de un proyecto SODA.
    Implementa el patrón de Puntos de Control (Checkpoints) para permitir reanudación segura.
    """
    def __init__(self, projects_dir: Path):
        self.projects_dir = projects_dir
        self.projects_dir.mkdir(exist_ok=True)

    def save_checkpoint(self, project: Project):
        if not project.workspace:
            project.workspace = self.projects_dir / project.id
            project.workspace.mkdir(parents=True, exist_ok=True)

        meta_path = project.workspace / "metadata.json"
        project.created_at = project.created_at or datetime.now().isoformat()
        
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(project.to_dict(), f, indent=2, ensure_ascii=False)

    def load_project(self, project_id: str) -> Optional[Project]:
        workspace = self.projects_dir / project_id
        meta_path = workspace / "metadata.json"
        if not meta_path.exists():
            return None
        
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Project.from_dict(data)

    def transition_to(self, project: Project, new_state: ProjectState):
        """Transiciona el estado y guarda un checkpoint inmediato."""
        old_state = project.state
        project.state = new_state
        self.save_checkpoint(project)
        # Aquí se podrían disparar hooks de transición si fuera necesario
