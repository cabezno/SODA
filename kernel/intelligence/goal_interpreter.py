import asyncio
import json
import re
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class ModificationPlan:
    change_type: str
    affected_modules: list[str]
    new_modules: list[str]
    description: str
    requires_regeneration: bool
    regeneration_scope: str
    impact_summary: str
    # Set when Claude detected ambiguity and the user resolved it
    clarification_used: str = ""

    def to_dict(self) -> dict:
        return {
            "change_type": self.change_type,
            "affected_modules": self.affected_modules,
            "new_modules": self.new_modules,
            "description": self.description,
            "requires_regeneration": self.requires_regeneration,
            "regeneration_scope": self.regeneration_scope,
            "impact_summary": self.impact_summary,
            "clarification_used": self.clarification_used,
        }


_AMBIGUITY_PROMPT = """\
You are an assistant analyzing a user's modification request for a software project.
Determine whether the request is ambiguous or unclear.

Respond ONLY with valid JSON:
{
  "is_ambiguous": true|false,
  "ambiguity_reason": "short explanation if ambiguous, else empty string",
  "clarification_options": ["option A", "option B", "option C"],
  "clarification_question": "question to ask the user (if ambiguous)"
}

If the request is clear and unambiguous, set is_ambiguous to false and leave the other fields empty.
"""


class GoalInterpreter:
    def __init__(self, claude_driver, context_builder):
        self.claude = claude_driver
        self.builder = context_builder
        # Optional: inject ask_fn to interactively resolve ambiguity.
        # Signature: async ask_fn(question: str, options: list[str]) -> str
        self.ask_fn: Optional[Callable] = None

    async def _check_ambiguity(self, user_request: str, arch_summary: str) -> dict:
        """Ask Claude whether the request is ambiguous. Returns parsed dict."""
        msg = (
            f"USER REQUEST:\n{user_request}\n\n"
            f"PROJECT MODULES SUMMARY:\n{arch_summary[:800]}"
        )
        raw = await self.claude.prompt(_AMBIGUITY_PROMPT, msg)
        try:
            data = json.loads(raw)
        except Exception:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            try:
                data = json.loads(m.group(0)) if m else {}
            except Exception:
                data = {}
        return data

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

        # Step 1: detect ambiguity
        clarification_used = ""
        ambiguity = await self._check_ambiguity(user_request, arch_summary)
        if ambiguity.get("is_ambiguous") and self.ask_fn:
            question = ambiguity.get("clarification_question", "¿Podés ser más específico sobre el cambio?")
            options = ambiguity.get("clarification_options", [])
            try:
                answer = await self.ask_fn(question, options)
                if answer:
                    user_request = f"{user_request}\n\nClarification: {answer}"
                    clarification_used = answer
            except Exception:
                pass  # if ask_fn fails, proceed with original request

        # Step 2: full interpretation
        task = (
            f"USER REQUEST:\n{user_request}\n\n"
            f"CURRENT ARCHITECTURE:\n{arch_summary}\n\n"
            f"CURRENT BLUEPRINT:\n{blueprint_summary}"
        )
        payload = self.builder.build_payload("claude", "goal_interpreter", task)
        raw = await self.claude.prompt(payload["system"], payload["user"])
        plan = self._parse(raw)
        plan.clarification_used = clarification_used
        return plan

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
