import json
from pathlib import Path
import yaml


class ProfileMatcher:
    def __init__(self, gemini_driver, context_builder, claude_driver=None):
        self.gemini = gemini_driver
        self.claude = claude_driver
        self.builder = context_builder
        self.profiles_dir = Path(__file__).resolve().parent.parent.parent / "profiles"

    def _load_available_profiles(self) -> list[dict]:
        profiles = []
        for identity_path in sorted(self.profiles_dir.glob("*/*/identity.yaml")):
            try:
                data = yaml.safe_load(identity_path.read_text(encoding="utf-8"))
                data["_path"] = identity_path.parent
                profiles.append(data)
            except Exception:
                pass
        return profiles

    def _build_profiles_summary(self, profiles: list[dict]) -> str:
        lines = []
        for p in profiles:
            skills = ", ".join(p.get("skills_included", []))
            lines.append(f"- {p['name']}: {p.get('description', '')} [skills: {skills}]")
        return "\n".join(lines)

    async def match(self, description: str, matched_skills: list[str]) -> str:
        available = self._load_available_profiles()
        if not available:
            return "profile_general_dev"

        task = (
            f"PROJECT DESCRIPTION:\n{description}\n\n"
            f"MATCHED SKILLS: {', '.join(matched_skills) or 'none'}\n\n"
            f"AVAILABLE PROFILES:\n{self._build_profiles_summary(available)}"
        )
        payload = self.builder.build_payload("gemini", "profile_matcher", task)
        raw = await self._call_gemini(payload, "profile_matcher", task)
        result = self._parse_json(raw)
        matched = result.get("matched_profile", "")
        valid_names = {p["name"] for p in available}
        return matched if matched in valid_names else "profile_general_dev"

    async def _call_gemini(self, payload: dict, role: str = "profile_matcher", task: str = "") -> str:
        from kernel.utils.ai_fallback import is_capacity_error
        result = (await self.gemini.call(payload["system"], payload["user"])).content
        if is_capacity_error(result) and self.claude:
            fallback = self.builder.build_payload("claude", role, task)
            result = await self.claude.prompt(fallback["system"], fallback["user"])
        return result

    @staticmethod
    def _parse_json(text: str) -> dict:
        import re
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}

    def load_profile_context(self, profile_name: str) -> str:
        """Returns style/code_conventions.md content for the matched profile."""
        available = self._load_available_profiles()
        by_name = {p["name"]: p for p in available}
        profile = by_name.get(profile_name)
        if not profile:
            return ""
        profile_dir: Path = profile["_path"]
        parts = []
        for sf in sorted((profile_dir / "style").glob("*.md")):
            parts.append(sf.read_text(encoding="utf-8").strip())
        return "\n\n---\n\n".join(parts)
