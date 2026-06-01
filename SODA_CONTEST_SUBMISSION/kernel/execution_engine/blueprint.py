from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
import networkx as nx

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class Task(BaseModel):
    id: str
    description: str
    language: str
    target_files: List[str] = [] # Rutas específicas definidas por el arquitecto
    dependencies: List[str] = []
    status: TaskStatus = TaskStatus.PENDING
    contract: str  # Definición estricta de lo que debe hacer

class ProjectBlueprint:
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.graph = nx.DiGraph()
        self.tasks: Dict[str, Task] = {}

    def add_task(self, task: Task):
        self.tasks[task.id] = task
        self.graph.add_node(task.id)
        for dep in task.dependencies:
            self.graph.add_edge(dep, task.id)

    def get_next_runnable_task(self) -> Optional[Task]:
        for node in nx.topological_sort(self.graph):
            if self.tasks[node].status == TaskStatus.PENDING:
                # Verificar si dependencias están completas
                deps = list(self.graph.predecessors(node))
                if all(self.tasks[d].status == TaskStatus.COMPLETED for d in deps):
                    return self.tasks[node]
        return None

    def update_task_status(self, task_id: str, status: TaskStatus):
        if task_id in self.tasks:
            self.tasks[task_id].status = status