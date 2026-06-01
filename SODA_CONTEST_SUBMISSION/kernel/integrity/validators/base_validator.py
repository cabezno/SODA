"""Base class for all contract validators (Arquitecto v2)."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod

from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.audit_schemas import Issue, ValidatorResult


class BaseValidator(ABC):
    """Abstract base for contract validators.

    Each concrete validator implements _validate() returning a list of Issues.
    The public validate() method wraps that with timing and status computation.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this validator."""

    @abstractmethod
    async def _validate(self, contract: MasterContract) -> list[Issue]:
        """Validation logic. Return list of Issues (empty = all good)."""

    async def validate(self, contract: MasterContract) -> ValidatorResult:
        """Run validation, measure time, and return a ValidatorResult."""
        start = time.perf_counter()

        try:
            issues = await self._validate(contract)
        except Exception as exc:
            issues = [
                Issue(
                    severity="error",
                    rule=f"{self.name}_exception",
                    location="validator",
                    description=f"El validador falló con excepción: {exc}",
                    suggestion="Revisar el contrato por problemas graves de estructura",
                )
            ]

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        if any(i.severity == "error" for i in issues):
            status = "failed"
        elif any(i.severity == "warning" for i in issues):
            status = "passed_with_warnings"
        else:
            status = "passed"

        return ValidatorResult(
            validator_name=self.name,
            status=status,
            issues=issues,
            execution_time_ms=elapsed_ms,
        )
