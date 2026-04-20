import json
from pathlib import Path
from typing import Optional
import yaml


class SkillMatcher:
    def __init__(self, gemini_driver, context_builder):
        self.gemini = gemini_driver
        self.builder = context_builder
        self.skills_dir = Path(__file__).resolve().parent.parent.parent / "skills"

    def _load_available_skills(self) -> list[dict]:
        skills = []
        for manifest_path in sorted(self.skills_dir.glob("*/*/manifest.yaml")):
            try:
                data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                data["_path"] = manifest_path.parent
                skills.append(data)
            except Exception:
                pass
        return skills

    def _build_skills_summary(self, skills: list[dict]) -> str:
        lines = []
        for s in skills:
            keywords = ", ".join(s.get("activation_keywords", []))
            lines.append(f"- {s['name']}: {s.get('description', '')} [keywords: {keywords}]")
        return "\n".join(lines)

    async def match(self, description: str) -> list[str]:
        available = self._load_available_skills()
        if not available:
            return []

        task = (
            f"PROJECT DESCRIPTION:\n{description}\n\n"
            f"AVAILABLE SKILLS:\n{self._build_skills_summary(available)}"
        )
        payload = self.builder.build_payload("gemini", "skill_matcher", task)
        raw = await self._call_gemini(payload)
        result = self._parse_json(raw)
        matched = result.get("matched_skills", [])
        valid_names = {s["name"] for s in available}
        return [m for m in matched if m in valid_names]

    async def _call_gemini(self, payload: dict) -> str:
        import asyncio
        return await asyncio.to_thread(self.gemini.prompt, payload["system"], payload["user"])

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

    def load_skill_context(self, skill_names: list[str]) -> str:
        """Returns concatenated system_prompt.md + knowledge/ content for matched skills."""
        available = self._load_available_skills()
        by_name = {s["name"]: s for s in available}
        parts = []
        for name in skill_names:
            skill = by_name.get(name)
            if not skill:
                continue
            skill_dir: Path = skill["_path"]
            sp = skill_dir / "system_prompt.md"
            if sp.exists():
                parts.append(sp.read_text(encoding="utf-8").strip())
            for kf in sorted((skill_dir / "knowledge").glob("*.md")):
                parts.append(kf.read_text(encoding="utf-8").strip())
        return "\n\n---\n\n".join(parts)
