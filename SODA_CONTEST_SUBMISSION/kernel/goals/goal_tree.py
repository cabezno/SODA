from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _slug(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "_")


def build_module_goal_id(module_name: str) -> str:
    return f"module__{_slug(module_name)}"


def build_file_goal_id(module_name: str, filepath: str) -> str:
    # Use the full path slugified (not just stem) to avoid collisions between
    # files that share the same filename but live in different directories.
    path_slug = _slug(filepath.replace("\\", "/").replace("/", "_").replace(".", "_"))
    return f"{_slug(module_name)}__{path_slug}"


def build_goal_hash(payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


@dataclass
class GoalNode:
    id: str
    parent_id: str | None
    type: str
    description: str
    status: str = "planned"
    implemented_by: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    hash: str = ""

    def sync_hash(self) -> str:
        self.hash = build_goal_hash(
            {
                "id": self.id,
                "parent_id": self.parent_id,
                "type": self.type,
                "description": self.description,
                "implemented_by": self.implemented_by,
                "dependencies": self.dependencies,
                "metadata": self.metadata,
            }
        )
        return self.hash

    def is_synced(self, recorded_hash: str) -> bool:
        """Return True if `recorded_hash` (stored in a code file's metadata) matches
        the current state of this goal node. A mismatch means the goal was modified
        after the file was generated — the file is stale and should be regenerated."""
        current = build_goal_hash(
            {
                "id": self.id,
                "parent_id": self.parent_id,
                "type": self.type,
                "description": self.description,
                "implemented_by": self.implemented_by,
                "dependencies": self.dependencies,
                "metadata": self.metadata,
            }
        )
        return current == recorded_hash

    def to_dict(self) -> dict:
        data = asdict(self)
        if not data["hash"]:
            data["hash"] = self.sync_hash()
        return data


def build_file_goal_node(module: dict, filepath: str, parent_id: str | None = None) -> GoalNode:
    module_name = module.get("nombre", "")
    return GoalNode(
        id=build_file_goal_id(module_name, filepath),
        parent_id=parent_id,
        type="objective",
        description=f"Implement {filepath} for module {module_name}",
        status="planned",
        implemented_by=[filepath],
        dependencies=[build_module_goal_id(dep) for dep in module.get("dependencias", [])],
        metadata={
            "module": module_name,
            "filepath": filepath,
            "responsabilidad": module.get("responsabilidad", ""),
        },
    )


@dataclass
class GoalTree:
    root_id: str
    nodes: dict[str, GoalNode] = field(default_factory=dict)

    def add_goal(self, goal: GoalNode) -> GoalNode:
        if goal.id in self.nodes:
            # Deduplicate with numeric suffix — never crash the pipeline over an ID clash
            i = 2
            while f"{goal.id}_{i}" in self.nodes:
                i += 1
            goal.id = f"{goal.id}_{i}"
        goal.sync_hash()
        self.nodes[goal.id] = goal
        return goal

    def get_goal(self, goal_id: str) -> GoalNode:
        if goal_id not in self.nodes:
            raise KeyError(f"Unknown goal: {goal_id}")
        return self.nodes[goal_id]

    def query(self, goal_id: str) -> GoalNode:
        return self.get_goal(goal_id)

    def children_of(self, parent_id: str | None) -> list[GoalNode]:
        return [goal for goal in self.nodes.values() if goal.parent_id == parent_id]

    def modify_goal(self, goal_id: str, **changes) -> GoalNode:
        goal = self.get_goal(goal_id)
        for field_name, value in changes.items():
            if value is not None and hasattr(goal, field_name):
                setattr(goal, field_name, value)
        goal.sync_hash()
        return goal

    def mark_implemented(self, goal_id: str, filepath: str | None = None) -> GoalNode:
        goal = self.get_goal(goal_id)
        if filepath and filepath not in goal.implemented_by:
            goal.implemented_by.append(filepath)
        goal.status = "implemented"
        goal.sync_hash()
        return goal

    def remove_goal(self, goal_id: str) -> None:
        children = [child.id for child in self.children_of(goal_id)]
        for child_id in children:
            self.remove_goal(child_id)
        self.nodes.pop(goal_id, None)

    def to_dict(self) -> dict:
        return {
            "root_id": self.root_id,
            "nodes": [
                self.nodes[goal_id].to_dict()
                for goal_id in sorted(self.nodes)
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GoalTree":
        tree = cls(root_id=data.get("root_id", "root"))
        for raw in data.get("nodes", []):
            goal = GoalNode(**raw)
            if not goal.hash:
                goal.sync_hash()
            tree.nodes[goal.id] = goal
        return tree

    @classmethod
    def from_architecture(cls, project_id: str, description: str, architecture: dict) -> "GoalTree":
        root_id = f"{_slug(project_id)}__root"
        tree = cls(root_id=root_id)
        tree.add_goal(
            GoalNode(
                id=root_id,
                parent_id=None,
                type="category",
                description=description or project_id,
                status="planned",
                metadata={"project_id": project_id},
            )
        )

        for module in architecture.get("modulos", []):
            module_name = module.get("nombre", "")
            module_goal_id = build_module_goal_id(module_name)
            tree.add_goal(
                GoalNode(
                    id=module_goal_id,
                    parent_id=root_id,
                    type="category",
                    description=module.get("responsabilidad", module_name),
                    status="planned",
                    dependencies=[build_module_goal_id(dep) for dep in module.get("dependencias", [])],
                    metadata={"module": module_name},
                )
            )
            for filepath in module.get("archivos_principales", []):
                tree.add_goal(build_file_goal_node(module, filepath, parent_id=module_goal_id))

        return tree