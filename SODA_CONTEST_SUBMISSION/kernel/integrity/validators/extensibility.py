"""ExtensibilityValidator — extension point quality checks (Arquitecto v2)."""
from __future__ import annotations

from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.audit_schemas import Issue
from kernel.integrity.validators.base_validator import BaseValidator


class ExtensibilityValidator(BaseValidator):
    """Verifies that extension points are sufficient and well documented.

    Rules checked:
    - At least MIN_TOTAL extension points
    - At least one of each REQUIRED_TYPES present (warning if missing)
    - Each extension point has a clear contract description (≥ 20 chars)
    - Each extension point has an example use case (info if missing)
    """

    REQUIRED_TYPES = frozenset({"middleware_slot", "metadata_field", "event_channel"})
    MIN_TOTAL = 3

    @property
    def name(self) -> str:
        return "extensibility_validator"

    async def _validate(self, contract: MasterContract) -> list[Issue]:
        issues: list[Issue] = []

        if len(contract.extension_points) < self.MIN_TOTAL:
            issues.append(Issue(
                severity="error",
                rule="minimum_extension_points",
                location="extension_points",
                description=f"Debe haber al menos {self.MIN_TOTAL} puntos de extensión",
                suggestion="Agregar más puntos de extensión para permitir evolución futura",
            ))

        present_types = {ext.type for ext in contract.extension_points}
        for missing in self.REQUIRED_TYPES - present_types:
            issues.append(Issue(
                severity="warning",
                rule="missing_extension_type",
                location="extension_points",
                description=f"No hay puntos de extensión de tipo '{missing}'",
                suggestion=(
                    f"Considerar agregar al menos un '{missing}' "
                    "para extensibilidad balanceada"
                ),
            ))

        for ext in contract.extension_points:
            if len(ext.contract) < 20:
                issues.append(Issue(
                    severity="warning",
                    rule="extension_point_contract_unclear",
                    location=f"extension_points[{ext.id}].contract",
                    description=f"Extension point '{ext.id}' tiene contrato poco claro",
                    suggestion=(
                        "Documentar claramente qué debe cumplir quien use este extension point"
                    ),
                ))

            if not ext.example_use_case:
                issues.append(Issue(
                    severity="info",
                    rule="extension_point_no_example",
                    location=f"extension_points[{ext.id}].example_use_case",
                    description=f"Extension point '{ext.id}' no tiene ejemplo de uso",
                    suggestion="Agregar un ejemplo de uso facilita la adopción futura",
                ))

        return issues
