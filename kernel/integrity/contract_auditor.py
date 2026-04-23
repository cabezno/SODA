"""ContractAuditor — orchestrates all validators (Arquitecto v2)."""
from __future__ import annotations

import asyncio

from kernel.integrity.audit_schemas import AuditReport
from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.validators.consistency import ConsistencyValidator
from kernel.integrity.validators.completeness import CompletenessValidator
from kernel.integrity.validators.dependency import DependencyValidator
from kernel.integrity.validators.naming import NamingValidator
from kernel.integrity.validators.extensibility import ExtensibilityValidator
from kernel.integrity.validators.traceability import TraceabilityValidator


class ContractAuditor:
    """Runs all validators concurrently and consolidates the AuditReport."""

    def __init__(self, goal_tree: dict | None = None):
        self.validators = [
            ConsistencyValidator(),
            CompletenessValidator(),
            DependencyValidator(),
            NamingValidator(),
            ExtensibilityValidator(),
            TraceabilityValidator(goal_tree=goal_tree),
        ]

    async def audit(self, contract: MasterContract) -> AuditReport:
        """Run all validators in parallel and return a consolidated report."""
        results = await asyncio.gather(
            *(v.validate(contract) for v in self.validators)
        )

        has_errors = any(r.has_errors for r in results)
        has_warnings = any(r.has_warnings for r in results)

        if has_errors:
            overall = "failed"
        elif has_warnings:
            overall = "passed_with_warnings"
        else:
            overall = "passed"

        return AuditReport(
            contract_id=contract.project_id,
            results=list(results),
            overall_status=overall,
        )
