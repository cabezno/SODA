from __future__ import annotations

from kernel.capabilities.profile_matcher import ProfileMatcher


class ProfileManager:
    """Capability facade for profile selection and context loading."""

    def __init__(self, matcher: ProfileMatcher):
        self.matcher = matcher

    async def select(self, description: str, matched_skills: list[str]) -> str:
        return await self.matcher.match(description, matched_skills)

    def load_context(self, profile_name: str) -> str:
        return self.matcher.load_profile_context(profile_name)
