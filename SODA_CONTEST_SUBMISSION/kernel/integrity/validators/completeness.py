"""CompletenessValidator — minimum content requirements (Arquitecto v2)."""
from __future__ import annotations

from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.audit_schemas import Issue
from kernel.integrity.validators.base_validator import BaseValidator


class CompletenessValidator(BaseValidator):
    """Verifies the contract is complete.

    Rules checked:
    - At least 1 module
    - At least MIN_EXTENSION_POINTS extension points
    - At least MIN_ERROR_TYPES error types
    - Every module has at least one interface
    - Every interface has at least one method
    - Method descriptions are descriptive (≥ 10 chars)
    - DataType descriptions are descriptive (≥ 10 chars)
    """

    MIN_EXTENSION_POINTS = 3
    MIN_ERROR_TYPES = 3

    @property
    def name(self) -> str:
        return "completeness_validator"

    async def _validate(self, contract: MasterContract) -> list[Issue]:
        issues: list[Issue] = []

        if len(contract.modules) < 1:
            issues.append(Issue(
                severity="error",
                rule="minimum_modules",
                location="modules",
                description="El contrato debe tener al menos 1 módulo",
                suggestion="Definir los módulos del sistema",
            ))

        if len(contract.extension_points) < self.MIN_EXTENSION_POINTS:
            missing = self.MIN_EXTENSION_POINTS - len(contract.extension_points)
            issues.append(Issue(
                severity="error",
                rule="minimum_extension_points",
                location="extension_points",
                description=(
                    f"Debe haber al menos {self.MIN_EXTENSION_POINTS} puntos de extensión, "
                    f"hay {len(contract.extension_points)}"
                ),
                suggestion=f"Agregar al menos {missing} puntos de extensión más",
            ))

        if len(contract.error_types) < self.MIN_ERROR_TYPES:
            missing = self.MIN_ERROR_TYPES - len(contract.error_types)
            issues.append(Issue(
                severity="error",
                rule="minimum_error_types",
                location="error_types",
                description=(
                    f"Debe haber al menos {self.MIN_ERROR_TYPES} tipos de error, "
                    f"hay {len(contract.error_types)}"
                ),
                suggestion="Definir tipos de error adicionales para diferentes situaciones",
            ))

        for module in contract.modules:
            if not module.interfaces:
                issues.append(Issue(
                    severity="error",
                    rule="module_has_interfaces",
                    location=f"modules[{module.id}].interfaces",
                    description=f"Módulo '{module.id}' no tiene interfaces definidas",
                    suggestion="Todo módulo debe exponer al menos una interfaz",
                ))
                continue

            for interface in module.interfaces:
                if not interface.methods:
                    issues.append(Issue(
                        severity="error",
                        rule="interface_has_methods",
                        location=f"modules[{module.id}].interfaces[{interface.name}].methods",
                        description=f"Interfaz '{interface.name}' no tiene métodos definidos",
                        suggestion="Toda interfaz debe tener al menos un método",
                    ))

                for method in interface.methods:
                    if len(method.description) < 10:
                        issues.append(Issue(
                            severity="warning",
                            rule="method_description_too_short",
                            location=(
                                f"modules[{module.id}].interfaces[{interface.name}]"
                                f".methods[{method.name}].description"
                            ),
                            description=f"Descripción del método '{method.name}' es muy corta",
                            suggestion="Agregar descripción más detallada (mínimo 10 caracteres)",
                        ))

        for dt in contract.data_types:
            if len(dt.description) < 10:
                issues.append(Issue(
                    severity="warning",
                    rule="data_type_description_too_short",
                    location=f"data_types[{dt.name}].description",
                    description=f"Descripción del tipo '{dt.name}' es muy corta",
                    suggestion="Agregar descripción más detallada",
                ))

        return issues
