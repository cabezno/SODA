"""DependencyValidator — DAG integrity checks (Arquitecto v2)."""
from __future__ import annotations

from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.audit_schemas import Issue
from kernel.integrity.validators.base_validator import BaseValidator


class DependencyValidator(BaseValidator):
    """Verifies the dependency graph is valid.

    Rules checked:
    - No circular dependencies (DFS cycle detection)
    - Max dependency depth warning (> MAX_DEPTH)
    - Excessive direct dependencies warning (> MAX_DIRECT_DEPENDENCIES)
    """

    MAX_DEPTH = 5
    MAX_DIRECT_DEPENDENCIES = 8

    @property
    def name(self) -> str:
        return "dependency_validator"

    async def _validate(self, contract: MasterContract) -> list[Issue]:
        graph: dict[str, list[str]] = {m.id: m.depends_on for m in contract.modules}
        issues: list[Issue] = []

        for cycle in self._detect_cycles(graph):
            issues.append(Issue(
                severity="error",
                rule="no_circular_dependencies",
                location=f"modules[{','.join(cycle)}]",
                description=f"Dependencia circular: {' -> '.join(cycle)} -> {cycle[0]}",
                suggestion=(
                    "Reestructurar las dependencias para eliminar el ciclo, "
                    "posiblemente usando inversión de dependencias"
                ),
            ))

        for module_id, dep_depth in self._calculate_depths(graph).items():
            if dep_depth > self.MAX_DEPTH:
                issues.append(Issue(
                    severity="warning",
                    rule="max_dependency_depth",
                    location=f"modules[{module_id}]",
                    description=(
                        f"Profundidad de dependencias excesiva: {dep_depth} "
                        f"(máximo recomendado: {self.MAX_DEPTH})"
                    ),
                    suggestion="Considerar aplanar la jerarquía de dependencias",
                ))

        for module_id, deps in graph.items():
            if len(deps) > self.MAX_DIRECT_DEPENDENCIES:
                issues.append(Issue(
                    severity="warning",
                    rule="max_direct_dependencies",
                    location=f"modules[{module_id}].depends_on",
                    description=(
                        f"Módulo '{module_id}' tiene demasiadas dependencias directas: "
                        f"{len(deps)} (máximo recomendado: {self.MAX_DIRECT_DEPENDENCIES})"
                    ),
                    suggestion="Considerar refactorizar el módulo para reducir sus dependencias",
                ))

        return issues

    # ------------------------------------------------------------------
    # Cycle detection (DFS with color-marking)
    # ------------------------------------------------------------------

    def _detect_cycles(self, graph: dict[str, list[str]]) -> list[list[str]]:
        """Return list of cycles found (each cycle is a list of node IDs)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        colors: dict[str, int] = {node: WHITE for node in graph}
        cycles: list[list[str]] = []

        def dfs(node: str, path: list[str]) -> None:
            if colors[node] == GRAY:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:])
                return
            if colors[node] == BLACK:
                return

            colors[node] = GRAY
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor in graph:
                    dfs(neighbor, list(path))

            colors[node] = BLACK

        for node in graph:
            if colors[node] == WHITE:
                dfs(node, [])

        return cycles

    # ------------------------------------------------------------------
    # Depth calculation
    # ------------------------------------------------------------------

    def _calculate_depths(self, graph: dict[str, list[str]]) -> dict[str, int]:
        """Max transitive dependency depth for each node."""
        memo: dict[str, int] = {}

        def depth(node: str, visiting: set[str]) -> int:
            if node in memo:
                return memo[node]
            if node in visiting:
                return 0  # cycle guard
            if node not in graph or not graph[node]:
                memo[node] = 0
                return 0

            visiting = visiting | {node}
            max_child = max(
                (depth(dep, visiting) for dep in graph[node] if dep in graph),
                default=0,
            )
            memo[node] = max_child + 1
            return memo[node]

        for node in graph:
            depth(node, set())

        return memo
