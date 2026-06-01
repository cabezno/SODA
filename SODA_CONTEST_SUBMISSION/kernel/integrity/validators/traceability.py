"""TraceabilityValidator — goal-tree coverage checks (Arquitecto v2).

TODO: The correct architectural flow would be to build the GoalTree from the
blueprint *before* generating the architecture, so the Architect can receive
validated goal IDs upfront. Currently (convivencia temporal) the GoalTree is
built *after* architecture from architecture["modulos"], so we support two
modes here:

- Empty goal_tree (first iteration): only verify each module has non-empty
  goal_ids — cannot validate existence in the tree yet.
- Populated goal_tree: full validation including existence and coverage.
"""
from __future__ import annotations

from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.audit_schemas import Issue
from kernel.integrity.validators.base_validator import BaseValidator


class TraceabilityValidator(BaseValidator):
    """Verifies traceability between modules and the objective tree.

    Two operating modes:
    - Empty goal_tree: soft mode — only checks goal_ids are non-empty.
    - Populated goal_tree: full cross-reference validation.
    """

    def __init__(self, goal_tree: dict | None = None):
        self.goal_tree = goal_tree or {}
        self._all_goal_ids = self._extract_all_goal_ids(self.goal_tree)
        self._soft_mode = len(self._all_goal_ids) == 0

    @property
    def name(self) -> str:
        return "traceability_validator"

    async def _validate(self, contract: MasterContract) -> list[Issue]:
        if self._soft_mode:
            return self._validate_soft(contract)
        return self._validate_full(contract)

    # ------------------------------------------------------------------
    # Soft mode: goal_tree not yet built
    # ------------------------------------------------------------------

    def _validate_soft(self, contract: MasterContract) -> list[Issue]:
        """Only verify each module declares at least one goal_id."""
        issues: list[Issue] = []
        for module in contract.modules:
            if not module.goal_ids:
                issues.append(Issue(
                    severity="error",
                    rule="module_has_goals",
                    location=f"modules[{module.id}].goal_ids",
                    description=f"Módulo '{module.id}' no referencia ningún goal",
                    suggestion="Todo módulo debe mapear a al menos un objetivo",
                ))
        return issues

    # ------------------------------------------------------------------
    # Full mode: cross-reference with the goal tree
    # ------------------------------------------------------------------

    def _validate_full(self, contract: MasterContract) -> list[Issue]:
        issues: list[Issue] = []
        implemented: set[str] = set()

        for module in contract.modules:
            if not module.goal_ids:
                issues.append(Issue(
                    severity="error",
                    rule="module_has_goals",
                    location=f"modules[{module.id}].goal_ids",
                    description=f"Módulo '{module.id}' no referencia ningún goal",
                    suggestion="Todo módulo debe mapear a al menos un objetivo del árbol",
                ))
                continue

            for goal_id in module.goal_ids:
                if goal_id not in self._all_goal_ids:
                    issues.append(Issue(
                        severity="error",
                        rule="goal_ids_valid",
                        location=f"modules[{module.id}].goal_ids",
                        description=f"Goal ID '{goal_id}' no existe en el árbol de objetivos",
                        suggestion="Verificar que el goal_id corresponda a un nodo existente",
                    ))
                else:
                    implemented.add(goal_id)

        for goal_id in self._all_goal_ids - implemented:
            issues.append(Issue(
                severity="warning",
                rule="goal_has_implementation",
                location=f"goal_tree[{goal_id}]",
                description=f"Goal '{goal_id}' no está implementado por ningún módulo",
                suggestion="Asignar el goal a un módulo, o verificar si es necesario",
            ))

        return issues

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_all_goal_ids(self, tree: dict) -> set[str]:
        """Recursively extract all 'id' values from the goal tree."""
        ids: set[str] = set()

        def traverse(node: object) -> None:
            if isinstance(node, dict):
                if "id" in node:
                    ids.add(node["id"])
                for value in node.values():
                    traverse(value)
            elif isinstance(node, list):
                for item in node:
                    traverse(item)

        traverse(tree)
        return ids
