import asyncio
import json
import re
from dataclasses import dataclass

from kernel.intelligence.goal_interpreter import ModificationPlan


@dataclass
class ImpactReport:
    directly_affected: list[str]
    transitively_affected: list[str]
    unaffected: list[str]
    regeneration_order: list[str]
    risk_level: str
    risk_reason: str

    def to_dict(self) -> dict:
        return {
            "directly_affected": self.directly_affected,
            "transitively_affected": self.transitively_affected,
            "unaffected": self.unaffected,
            "regeneration_order": self.regeneration_order,
            "risk_level": self.risk_level,
            "risk_reason": self.risk_reason,
        }


class ImpactAnalyzer:
    def __init__(self, claude_driver, context_builder):
        self.claude = claude_driver
        self.builder = context_builder

    async def analyze(self, plan: ModificationPlan, architecture: dict) -> ImpactReport:
        modules_summary = json.dumps(
            {"modulos": architecture.get("modulos", [])},
            ensure_ascii=False,
            indent=2,
        )
        task = (
            f"MODIFICATION PLAN:\n{json.dumps(plan.to_dict(), indent=2)}\n\n"
            f"MODULE DEPENDENCY GRAPH:\n{modules_summary}"
        )
        payload = self.builder.build_payload("claude", "impact_analyzer", task)
        raw = await self.claude.prompt(payload["system"], payload["user"])
        return self._parse(raw, architecture)

    def _parse(self, text: str, architecture: dict) -> ImpactReport:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            data = json.loads(match.group(0)) if match else {}

        all_modules = [m["nombre"] for m in architecture.get("modulos", [])]
        directly = data.get("directly_affected", [])
        transitively = data.get("transitively_affected", [])
        affected = set(directly + transitively)

        return ImpactReport(
            directly_affected=directly,
            transitively_affected=transitively,
            unaffected=[m for m in all_modules if m not in affected],
            regeneration_order=data.get("regeneration_order", directly + transitively),
            risk_level=data.get("risk_level", "medium"),
            risk_reason=data.get("risk_reason", ""),
        )
