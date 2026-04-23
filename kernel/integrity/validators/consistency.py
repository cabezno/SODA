"""ConsistencyValidator — cross-reference checks within the contract (Arquitecto v2)."""
from __future__ import annotations

from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.audit_schemas import Issue
from kernel.integrity.validators.base_validator import BaseValidator

_PRIMITIVE_TYPES = frozenset({
    "str", "int", "float", "bool", "None", "datetime", "bytes",
    "Any", "dict", "list", "tuple", "set",
})

_CONTAINER_PREFIXES = (
    "Optional[", "list[", "List[", "dict[", "Dict[",
    "set[", "Set[", "tuple[", "Tuple[", "Union[",
)


class ConsistencyValidator(BaseValidator):
    """Verifies internal consistency of the contract.

    Rules checked:
    - Module IDs are unique
    - Data types referenced in method signatures exist
    - Modules in depends_on exist
    - Events emitted/consumed are declared as channels
    - Error codes are unique
    - Extension point IDs are unique
    """

    @property
    def name(self) -> str:
        return "consistency_validator"

    async def _validate(self, contract: MasterContract) -> list[Issue]:
        issues: list[Issue] = []
        issues.extend(self._check_unique_module_ids(contract))
        issues.extend(self._check_data_types_exist(contract))
        issues.extend(self._check_dependencies_exist(contract))
        issues.extend(self._check_events_exist(contract))
        issues.extend(self._check_unique_error_codes(contract))
        issues.extend(self._check_unique_extension_ids(contract))
        return issues

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_unique_module_ids(self, contract: MasterContract) -> list[Issue]:
        seen: set[str] = set()
        duplicates: list[str] = []
        for module in contract.modules:
            if module.id in seen:
                duplicates.append(module.id)
            seen.add(module.id)
        return [
            Issue(
                severity="error",
                rule="unique_module_ids",
                location=f"modules[id={dup}]",
                description=f"ID de módulo duplicado: '{dup}'",
                suggestion="Cada módulo debe tener un ID único",
            )
            for dup in duplicates
        ]

    def _check_data_types_exist(self, contract: MasterContract) -> list[Issue]:
        defined = {dt.name for dt in contract.data_types}
        valid_types = defined | _PRIMITIVE_TYPES
        issues: list[Issue] = []

        for module in contract.modules:
            for interface in module.interfaces:
                for method in interface.methods:
                    if not self._is_valid_type(method.returns, valid_types):
                        issues.append(Issue(
                            severity="error",
                            rule="data_types_exist",
                            location=(
                                f"modules[{module.id}].interfaces[{interface.name}]"
                                f".methods[{method.name}].returns"
                            ),
                            description=f"Tipo de retorno '{method.returns}' no está definido",
                            suggestion=(
                                f"Definir '{method.returns}' en data_types "
                                "o usar un tipo primitivo"
                            ),
                        ))
                    for param_name, param_type in method.parameters.items():
                        if not self._is_valid_type(param_type, valid_types):
                            issues.append(Issue(
                                severity="error",
                                rule="data_types_exist",
                                location=(
                                    f"modules[{module.id}].interfaces[{interface.name}]"
                                    f".methods[{method.name}].parameters.{param_name}"
                                ),
                                description=f"Tipo de parámetro '{param_type}' no está definido",
                                suggestion=(
                                    f"Definir '{param_type}' en data_types "
                                    "o usar un tipo primitivo"
                                ),
                            ))
        return issues

    def _check_dependencies_exist(self, contract: MasterContract) -> list[Issue]:
        module_ids = {m.id for m in contract.modules}
        issues: list[Issue] = []
        for module in contract.modules:
            for dep in module.depends_on:
                if dep not in module_ids:
                    issues.append(Issue(
                        severity="error",
                        rule="dependencies_exist",
                        location=f"modules[{module.id}].depends_on",
                        description=f"Dependencia '{dep}' no es un módulo definido",
                        suggestion=f"Remover la dependencia o agregar el módulo '{dep}'",
                    ))
        return issues

    def _check_events_exist(self, contract: MasterContract) -> list[Issue]:
        channel_names = {ec.name for ec in contract.event_channels}
        issues: list[Issue] = []

        for module in contract.modules:
            for interface in module.interfaces:
                for event in interface.events_emitted:
                    if event not in channel_names:
                        issues.append(Issue(
                            severity="error",
                            rule="events_exist",
                            location=(
                                f"modules[{module.id}].interfaces[{interface.name}]"
                                ".events_emitted"
                            ),
                            description=f"Evento '{event}' emitido pero no declarado como channel",
                            suggestion=f"Agregar '{event}' a event_channels",
                        ))
                for event in interface.events_consumed:
                    if event not in channel_names:
                        issues.append(Issue(
                            severity="error",
                            rule="events_exist",
                            location=(
                                f"modules[{module.id}].interfaces[{interface.name}]"
                                ".events_consumed"
                            ),
                            description=f"Evento '{event}' consumido pero no declarado como channel",
                            suggestion=f"Agregar '{event}' a event_channels",
                        ))
        return issues

    def _check_unique_error_codes(self, contract: MasterContract) -> list[Issue]:
        seen: set[str] = set()
        duplicates: list[str] = []
        for error in contract.error_types:
            if error.code in seen:
                duplicates.append(error.code)
            seen.add(error.code)
        return [
            Issue(
                severity="error",
                rule="unique_error_codes",
                location=f"error_types[code={dup}]",
                description=f"Error code duplicado: '{dup}'",
                suggestion="Cada error type debe tener un code único",
            )
            for dup in duplicates
        ]

    def _check_unique_extension_ids(self, contract: MasterContract) -> list[Issue]:
        seen: set[str] = set()
        duplicates: list[str] = []
        for ext in contract.extension_points:
            if ext.id in seen:
                duplicates.append(ext.id)
            seen.add(ext.id)
        return [
            Issue(
                severity="error",
                rule="unique_extension_ids",
                location=f"extension_points[id={dup}]",
                description=f"Extension point ID duplicado: '{dup}'",
                suggestion="Cada extension point debe tener un ID único",
            )
            for dup in duplicates
        ]

    # ------------------------------------------------------------------
    # Type helper
    # ------------------------------------------------------------------

    @staticmethod
    def _is_valid_type(type_str: str, valid_types: set[str]) -> bool:
        """Check if a type string is valid, considering generics and Optional."""
        clean = type_str.strip()

        # Container types: treat as valid (inner types not recursively checked)
        for prefix in _CONTAINER_PREFIXES:
            if clean.startswith(prefix) and clean.endswith("]"):
                return True

        return clean in valid_types
