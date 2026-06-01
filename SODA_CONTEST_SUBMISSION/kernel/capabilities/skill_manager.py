from __future__ import annotations

from kernel.capabilities.skill_matcher import SkillMatcher


class SkillManager:
    """Capability facade for skill selection and context loading."""

    def __init__(self, matcher: SkillMatcher):
        self.matcher = matcher

    async def select(self, description: str) -> list[str]:
        return await self.matcher.match(description)

    def load_context(self, skill_names: list[str], role: str = "code_generator") -> str:
        return self.matcher.load_skill_context(skill_names, role=role)
