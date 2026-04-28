from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional
from collections import deque

# Layer classification: any module whose ID or layer field matches these
# patterns is treated as a presentation-layer consumer (frontend).
_FRONTEND_LAYERS = {"presentation"}
_FRONTEND_ID_KEYWORDS = ("frontend", "ui", "client", "web", "app_shell", "dashboard")

# Layers that expose APIs consumed by frontend modules
_BACKEND_LAYERS = {"application", "domain", "infrastructure"}
_BACKEND_ID_KEYWORDS = ("api", "service", "backend", "server", "gateway", "auth", "db", "data")


@dataclass
class ExecutionPlan:
    levels: List[List[str]]   # each level is a group executable in parallel
    order: List[str]          # flat topological order
    parallelizable: bool      # True if any level has >1 module
    broken_edges: List[Tuple[str, str]] = field(default_factory=list)  # removed cycles
    injected_edges: List[Tuple[str, str]] = field(default_factory=list)  # synthetic layer deps


class DependencyGraph:
    """DAG of modules with Kahn topological sort.

    Accepts two initialization modes:
      - Legacy (architecture.json): list of dicts with 'nombre'/'dependencias'
      - V2 (master_contract.json modules): list of dicts with 'id'/'depends_on'
        and optional 'layer' field for hierarchy enforcement

    Cycles are broken automatically. Frontend→backend synthetic edges are
    injected when the architect forgets to declare the dependency.
    Python-only — no AI.
    """

    def __init__(self, modulos: List[dict]):
        self.graph: Dict[str, List[str]] = {}
        self.reverse: Dict[str, Set[str]] = {}
        # Store layer metadata for hierarchy enforcement
        self._layers: Dict[str, str] = {}

        # Detect schema version: v2 uses 'id'/'depends_on', legacy uses 'nombre'/'dependencias'
        uses_v2 = any("id" in m and "depends_on" in m for m in modulos if isinstance(m, dict))

        if uses_v2:
            self._init_from_contract_modules(modulos)
        else:
            self._init_from_legacy_modulos(modulos)

    def _init_from_contract_modules(self, modules: List[dict]) -> None:
        """Initialize from master_contract.json module list (snake_case IDs)."""
        valid_ids = {m["id"] for m in modules if isinstance(m, dict) and m.get("id")}
        for m in modules:
            if not isinstance(m, dict) or not m.get("id"):
                continue
            mod_id = m["id"]
            deps = [d for d in m.get("depends_on", []) if d in valid_ids and d != mod_id]
            self.graph[mod_id] = deps
            self._layers[mod_id] = m.get("layer", "")
            if mod_id not in self.reverse:
                self.reverse[mod_id] = set()
            for dep in deps:
                if dep not in self.reverse:
                    self.reverse[dep] = set()
                self.reverse[dep].add(mod_id)

    def _init_from_legacy_modulos(self, modulos: List[dict]) -> None:
        """Initialize from architecture.json module list (free-form names)."""
        valid_names = {m["nombre"] for m in modulos if isinstance(m, dict) and m.get("nombre")}
        for m in modulos:
            if not isinstance(m, dict) or not m.get("nombre"):
                continue
            nombre = m["nombre"]
            deps = [d for d in m.get("dependencias", []) if d in valid_names and d != nombre]
            self.graph[nombre] = deps
            self._layers[nombre] = m.get("layer", "")
            if nombre not in self.reverse:
                self.reverse[nombre] = set()
            for dep in deps:
                if dep not in self.reverse:
                    self.reverse[dep] = set()
                self.reverse[dep].add(nombre)

    # ------------------------------------------------------------------
    # Cycle detection and removal
    # ------------------------------------------------------------------

    def _find_back_edges(self) -> List[Tuple[str, str]]:
        """DFS to find back-edges (sources of cycles)."""
        visited: Set[str] = set()
        in_stack: Set[str] = set()
        back_edges: List[Tuple[str, str]] = []

        def dfs(node: str):
            visited.add(node)
            in_stack.add(node)
            for neighbor in list(self.graph.get(node, [])):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in in_stack:
                    back_edges.append((node, neighbor))
            in_stack.discard(node)

        for node in self.graph:
            if node not in visited:
                dfs(node)
        return back_edges

    def break_cycles(self) -> List[Tuple[str, str]]:
        """Remove back-edges until the graph is acyclic. Returns removed edges."""
        removed: List[Tuple[str, str]] = []
        for _ in range(len(self.graph)):
            back_edges = self._find_back_edges()
            if not back_edges:
                break
            for src, dst in back_edges:
                if dst in self.graph.get(src, []):
                    self.graph[src] = [d for d in self.graph[src] if d != dst]
                    self.reverse.get(dst, set()).discard(src)
                    removed.append((src, dst))
        return removed

    # ------------------------------------------------------------------
    # Layer hierarchy enforcement
    # ------------------------------------------------------------------

    def _enforce_layer_hierarchy(self) -> List[Tuple[str, str]]:
        """Force presentation modules to depend on application/domain modules.

        This is a deterministic safety net for when the architect forgets to
        declare the frontend → backend dependency. Without it, frontend and
        backend land on the same DAG level and are generated simultaneously —
        the frontend cannot see the backend's typed interfaces.

        Returns the list of synthetic edges injected.
        """
        injected: List[Tuple[str, str]] = []

        frontend_ids = [
            node for node in self.graph
            if self._layers.get(node) in _FRONTEND_LAYERS
            or any(kw in node.lower() for kw in _FRONTEND_ID_KEYWORDS)
        ]
        backend_ids = [
            node for node in self.graph
            if self._layers.get(node) in _BACKEND_LAYERS
            or any(kw in node.lower() for kw in _BACKEND_ID_KEYWORDS)
        ]

        for front_id in frontend_ids:
            for back_id in backend_ids:
                if back_id in self.graph.get(front_id, []):
                    continue  # already declared
                if front_id in self.graph.get(back_id, []):
                    continue  # would create a cycle — skip
                # Inject synthetic dependency
                self.graph[front_id].append(back_id)
                if front_id not in self.reverse.get(back_id, set()):
                    self.reverse.setdefault(back_id, set()).add(front_id)
                injected.append((front_id, back_id))

        return injected

    # ------------------------------------------------------------------
    # Execution plan
    # ------------------------------------------------------------------

    def build_execution_plan(self) -> ExecutionPlan:
        """Kahn's algorithm with level grouping.

        Order of operations:
          1. Break cycles (graph stays acyclic)
          2. Enforce layer hierarchy (frontend always after backend)
          3. Kahn topological sort with level grouping
        """
        broken = self.break_cycles()
        injected = self._enforce_layer_hierarchy()

        in_degree: Dict[str, int] = {node: len(deps) for node, deps in self.graph.items()}
        queue = deque(sorted(n for n, d in in_degree.items() if d == 0))
        levels: List[List[str]] = []
        order: List[str] = []

        while queue:
            level = list(queue)
            queue.clear()
            levels.append(level)
            order.extend(level)
            for node in level:
                for dependent in sorted(self.reverse.get(node, set())):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        # Any node still not in order (shouldn't happen after break_cycles) goes last
        remaining = [n for n in self.graph if n not in order]
        if remaining:
            levels.append(remaining)
            order.extend(remaining)

        return ExecutionPlan(
            levels=levels,
            order=order,
            parallelizable=any(len(lvl) > 1 for lvl in levels),
            broken_edges=broken,
            injected_edges=injected,
        )

    def summary(self) -> str:
        plan = self.build_execution_plan()
        lines = ["Plan de ejecución:"]
        if plan.broken_edges:
            lines.append(f"  [WARN] Ciclos rotos automáticamente: {plan.broken_edges}")
        if plan.injected_edges:
            lines.append(f"  [INFO] Dependencias sintéticas inyectadas: {plan.injected_edges}")
        for i, level in enumerate(plan.levels):
            tag = f"[paralelo x{len(level)}]" if len(level) > 1 else "[secuencial]"
            lines.append(f"  Nivel {i}: {tag} {' | '.join(level)}")
        return "\n".join(lines)
