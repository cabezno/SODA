"""ContractRefinementLoop — orchestrates Architect ↔ ContractAuditor (Arquitecto v2)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from kernel.intelligence.architect import Architect
from kernel.intelligence.complexity_classifier import ComplexityLevel
from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.audit_schemas import AuditReport
from kernel.integrity.contract_auditor import ContractAuditor


class RefinementAttempt(BaseModel):
    attempt_number: int
    contract: MasterContract
    audit_report: AuditReport
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ContractResult(BaseModel):
    """Result of the full refinement loop."""

    status: Literal["approved", "approved_with_warnings", "requires_user_intervention"]
    contract: MasterContract | None
    attempts: list[RefinementAttempt]
    final_issues: AuditReport | None = None
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0


class ContractRefinementLoop:
    """Orchestrates the Architect ↔ ContractAuditor refinement cycle.

    Flow:
    1. Architect generates initial contract
    2. ContractAuditor validates it
    3. If failed → Architect refines based on feedback (up to max_attempts)
    4. If approved (with or without warnings) → return result
    5. If max_attempts exhausted → escalate to user
    """

    def __init__(
        self,
        architect: Architect,
        auditor: ContractAuditor,
        max_attempts: int = 3,
    ):
        self.architect = architect
        self.auditor = auditor
        self.max_attempts = max_attempts

    async def execute(
        self,
        blueprint: dict,
        complexity: ComplexityLevel,
        active_skills: list | None = None,
        active_profile: dict | None = None,
        goal_tree: dict | None = None,
    ) -> ContractResult:
        """Run the full generate → audit → refine cycle."""
        attempts: list[RefinementAttempt] = []
        current_contract: MasterContract | None = None

        for attempt_num in range(self.max_attempts):
            try:
                # Generate if we don't have a contract yet (first call, or after
                # a failed generation). Refine only if a previous contract exists.
                if current_contract is None:
                    current_contract = await self.architect.generate_master_contract(
                        blueprint=blueprint,
                        complexity=complexity,
                        active_skills=active_skills,
                        active_profile=active_profile,
                        goal_tree=goal_tree,
                        attempt_number=attempt_num + 1,
                    )
                else:
                    current_contract = await self.architect.refine_contract(
                        current_contract=current_contract,
                        audit_feedback=attempts[-1].audit_report,
                        complexity=complexity,
                        attempt_number=attempt_num + 1,
                    )
            except Exception as exc:
                # Architect failed (API error, bad JSON, schema validation) —
                # record as a failed attempt and continue if we have attempts left
                if attempt_num == self.max_attempts - 1:
                    return ContractResult(
                        status="requires_user_intervention",
                        contract=current_contract,
                        attempts=attempts,
                        final_issues=attempts[-1].audit_report if attempts else None,
                    )
                # On non-final failures, skip to next attempt (no contract to audit)
                continue

            audit_report = await self.auditor.audit(current_contract)

            attempts.append(RefinementAttempt(
                attempt_number=attempt_num + 1,
                contract=current_contract,
                audit_report=audit_report,
            ))

            if audit_report.overall_status == "passed":
                return ContractResult(
                    status="approved",
                    contract=current_contract,
                    attempts=attempts,
                )

            if audit_report.overall_status == "passed_with_warnings":
                return ContractResult(
                    status="approved_with_warnings",
                    contract=current_contract,
                    attempts=attempts,
                )

            # Status is "failed" — continue to next attempt (refinement)

        # Exhausted all attempts without approval
        return ContractResult(
            status="requires_user_intervention",
            contract=current_contract,
            attempts=attempts,
            final_issues=attempts[-1].audit_report if attempts else None,
        )
