import asyncio
import json
import re
from dataclasses import dataclass


@dataclass
class ModificationPlan:
    change_type: str
    affected_modules: list[str]
    new_modules: list[str]
    description: str
    requires_regeneration: bool
    regeneration_scope: str
    impact_summary: str

    def to_dict(self) -> dict:
        return {
            "change_type": self.change_type,
            "affected_modules": self.affected_modules,
            "new_modules": self.new_modules,
            "description": self.description,
            "requires_regeneration": self.requires_regeneration,
            "regeneration_scope": self.regeneration_scope,
            "impact_summary": self.impact_summary,
        }


class GoalInterpreter:
    def __init__(self, claude_driver, context_builder):
        self.claude = claude_driver
        self.builder = context_builder

    async def interpret(
        self,
        user_request: str,
        architecture: dict,
        blueprint: dict,
    ) -> ModificationPlan:
        arch_summary = json.dumps(
            {"modulos": architecture.get("modulos", [])},
            ensure_ascii=False,
            indent=2,
        )
        blueprint_summary = json.dumps(blueprint, ensure_ascii=False, indent=2)

        task = (
            f"USER REQUEST:\n{user_request}\n\n"
            f"CURRENT ARCHITECTURE:\n{arch_summary}\n\n"
            f"CURRENT BLUEPRINT:\n{blueprint_summary}"
        )
        payload = self.builder.build_payload("claude", "goal_interpreter", task)
        raw = await self.claude.prompt(payload["system"], payload["user"])
        return self._parse(raw)

    def _parse(self, text: str) -> ModificationPlan:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            data = json.loads(match.group(0)) if match else {}

        return ModificationPlan(
            change_type=data.get("change_type", "behavior"),
            affected_modules=data.get("affected_modules", []),
            new_modules=data.get("new_modules", []),
            description=data.get("description", ""),
            requires_regeneration=data.get("requires_regeneration", True),
            regeneration_scope=data.get("regeneration_scope", "partial"),
            impact_summary=data.get("impact_summary", ""),
        )
