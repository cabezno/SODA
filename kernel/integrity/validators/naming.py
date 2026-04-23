"""NamingValidator — naming convention checks (Arquitecto v2)."""
from __future__ import annotations

import re

from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.audit_schemas import Issue
from kernel.integrity.validators.base_validator import BaseValidator


class NamingValidator(BaseValidator):
    """Verifies naming conventions across the contract.

    Conventions enforced:
    - Module IDs: snake_case
    - DataType names: PascalCase
    - Method names: snake_case
    - Constant names: UPPER_SNAKE_CASE
    - Event names: dotted.notation (entity.action)
    - Error codes: UPPER_SNAKE_CASE
    """

    _SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
    _PASCAL_CASE = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
    _UPPER_SNAKE = re.compile(r"^[A-Z][A-Z0-9_]*$")
    _DOTTED_EVENT = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")

    @property
    def name(self) -> str:
        return "naming_validator"

    async def _validate(self, contract: MasterContract) -> list[Issue]:
        issues: list[Issue] = []

        for module in contract.modules:
            if not self._SNAKE_CASE.match(module.id):
                issues.append(Issue(
                    severity="error",
                    rule="module_id_snake_case",
                    location=f"modules[{module.id}].id",
                    description=f"ID de módulo '{module.id}' no es snake_case",
                    suggestion="Usar snake_case: solo minúsculas, números y underscores",
                ))

            for interface in module.interfaces:
                for method in interface.methods:
                    if not self._SNAKE_CASE.match(method.name):
                        issues.append(Issue(
                            severity="error",
                            rule="method_name_snake_case",
                            location=(
                                f"modules[{module.id}].interfaces[{interface.name}]"
                                f".methods[{method.name}].name"
                            ),
                            description=f"Nombre de método '{method.name}' no es snake_case",
                            suggestion="Usar snake_case para nombres de métodos",
                        ))

        for dt in contract.data_types:
            if not self._PASCAL_CASE.match(dt.name):
                issues.append(Issue(
                    severity="error",
                    rule="data_type_pascal_case",
                    location=f"data_types[{dt.name}].name",
                    description=f"Nombre de tipo '{dt.name}' no es PascalCase",
                    suggestion="Usar PascalCase: empezar con mayúscula, sin underscores",
                ))

        for const in contract.constants:
            if not self._UPPER_SNAKE.match(const.name):
                issues.append(Issue(
                    severity="error",
                    rule="constant_upper_snake_case",
                    location=f"constants[{const.name}].name",
                    description=f"Nombre de constante '{const.name}' no es UPPER_SNAKE_CASE",
                    suggestion="Usar UPPER_SNAKE_CASE para constantes",
                ))

        for event in contract.event_channels:
            if not self._DOTTED_EVENT.match(event.name):
                issues.append(Issue(
                    severity="error",
                    rule="event_dotted_notation",
                    location=f"event_channels[{event.name}].name",
                    description=f"Nombre de evento '{event.name}' no usa notación con puntos",
                    suggestion="Usar 'entidad.accion', por ejemplo: 'user.created'",
                ))

        for error in contract.error_types:
            if not self._UPPER_SNAKE.match(error.code):
                issues.append(Issue(
                    severity="error",
                    rule="error_code_upper_snake_case",
                    location=f"error_types[{error.code}].code",
                    description=f"Error code '{error.code}' no es UPPER_SNAKE_CASE",
                    suggestion="Usar UPPER_SNAKE_CASE para error codes",
                ))

        return issues
