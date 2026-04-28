"""TopologyConsistencyValidator — cross-checks master_contract against topology.json.

Verifies:
  1. Module IDs in the contract match exactly the IDs defined by Gemini's topology.
  2. depends_on in each contract module matches depende_de_ids in topology.
"""
from __future__ import annotations

from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.audit_schemas import Issue
from kernel.integrity.validators.base_validator import BaseValidator


class TopologyConsistencyValidator(BaseValidator):
    """Validates that Claude's master_contract is consistent with Gemini's topology."""

    def __init__(self, topology: dict) -> None:
        self._topology = topology

    @property
    def name(self) -> str:
        return "topology_consistency"

    async def _validate(self, contract: MasterContract) -> list[Issue]:
        issues: list[Issue] = []

        topo_modules = self._topology.get("modulos", [])
        topology_ids = {m["id"] for m in topo_modules if isinstance(m, dict) and m.get("id")}
        contract_ids = {m.id for m in contract.modules}

        # 1. Claude must not invent or drop modules relative to topology
        missing = topology_ids - contract_ids
        invented = contract_ids - topology_ids

        for mid in sorted(missing):
            issues.append(Issue(
                severity="error",
                rule="topology_module_missing",
                location=f"modules[id={mid}]",
                description=f"El módulo '{mid}' está definido en topology.json pero no aparece en el contrato.",
                suggestion=f"Agregá un módulo con id='{mid}' al contrato. Sus archivos físicos son los que Gemini definió.",
            ))

        for mid in sorted(invented):
            issues.append(Issue(
                severity="error",
                rule="topology_module_invented",
                location=f"modules[id={mid}]",
                description=f"El módulo '{mid}' existe en el contrato pero NO está en topology.json.",
                suggestion=f"Eliminá el módulo '{mid}' o renombralo para que coincida con un ID de topology.json.",
            ))

        # 2. depends_on must match depende_de_ids from topology
        topo_deps: dict[str, set[str]] = {
            m["id"]: set(m.get("depende_de_ids", []))
            for m in topo_modules
            if isinstance(m, dict) and m.get("id")
        }

        for mod in contract.modules:
            if mod.id not in topo_deps:
                continue
            expected = topo_deps[mod.id]
            actual = set(mod.depends_on)
            if expected != actual:
                issues.append(Issue(
                    severity="error",
                    rule="topology_dependency_mismatch",
                    location=f"modules[id={mod.id}].depends_on",
                    description=(
                        f"El módulo '{mod.id}' tiene dependencias incorrectas. "
                        f"topology.json exige: {sorted(expected)}. "
                        f"El contrato declara: {sorted(actual)}."
                    ),
                    suggestion=f"Cambiá depends_on de '{mod.id}' a exactamente {sorted(expected)}.",
                ))

        return issues
