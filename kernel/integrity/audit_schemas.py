"""Pydantic schemas for contract audit reports (Arquitecto v2)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class Issue(BaseModel):
    """Problem detected in a contract."""

    severity: Literal["error", "warning", "info"]
    rule: str = Field(..., description="Name of the violated rule")
    location: str = Field(..., description="Path within the contract")
    description: str
    suggestion: str


class ValidatorResult(BaseModel):
    """Result of a specific validator."""

    validator_name: str
    status: Literal["passed", "passed_with_warnings", "failed"]
    issues: list[Issue] = Field(default_factory=list)
    execution_time_ms: int = 0

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)


class AuditReport(BaseModel):
    """Complete audit report."""

    contract_id: str
    audited_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    results: list[ValidatorResult]
    overall_status: Literal["passed", "passed_with_warnings", "failed"]

    @property
    def all_errors(self) -> list[Issue]:
        return [i for r in self.results for i in r.issues if i.severity == "error"]

    @property
    def all_warnings(self) -> list[Issue]:
        return [
            i for r in self.results for i in r.issues if i.severity == "warning"
        ]

    def to_architect_feedback(self) -> str:
        """Format the report as feedback for the Architect."""
        lines: list[str] = []
        lines.append("# Feedback del Auditor del Contrato\n")

        errors = self.all_errors
        warnings = self.all_warnings

        if errors:
            lines.append(f"## Errores críticos ({len(errors)})\n")
            for issue in errors:
                lines.append(f"**{issue.rule}** en `{issue.location}`")
                lines.append(f"- Problema: {issue.description}")
                lines.append(f"- Corrección sugerida: {issue.suggestion}\n")

        if warnings:
            lines.append(f"\n## Warnings ({len(warnings)})\n")
            for issue in warnings:
                lines.append(f"**{issue.rule}** en `{issue.location}`")
                lines.append(f"- Observación: {issue.description}\n")

        lines.append("\n## Instrucciones\n")
        lines.append("Corregí los errores críticos listados arriba.")
        lines.append("Preservá todo lo que está correcto en el contrato actual.")
        lines.append("Los warnings pueden corregirse pero no son bloqueantes.")

        return "\n".join(lines)
