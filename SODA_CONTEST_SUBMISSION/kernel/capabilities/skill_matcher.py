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
            signals = s.get("activation_signals", {})
            file_patterns = ", ".join(signals.get("file_patterns", []))
            dependencies = ", ".join(signals.get("dependencies", []))
            extra = ""
            if file_patterns:
                extra += f" [files: {file_patterns}]"
            if dependencies:
                extra += f" [deps: {dependencies}]"
            lines.append(f"- {s['name']}: {s.get('description', '')} [keywords: {keywords}]{extra}")
        return "\n".join(lines)

    def _keyword_match(self, description: str, skills: list[dict]) -> list[str]:
        """Fallback: match skills whose activation_keywords appear in the description."""
        desc_lower = description.lower()
        matched = []
        for s in skills:
            for kw in s.get("activation_keywords", []):
                if kw.lower() in desc_lower:
                    matched.append(s["name"])
                    break
        return matched

    async def match(self, description: str) -> list[str]:
        available = self._load_available_skills()
        if not available:
            return []

        task = (
            f"PROJECT DESCRIPTION:\n{description}\n\n"
            f"AVAILABLE SKILLS:\n{self._build_skills_summary(available)}"
        )
        payload = self.builder.build_payload("gemini", "skill_matcher", task)
        raw = await self._call_gemini(payload, "skill_matcher", task)

        print(f"  [SkillMatcher] Gemini raw ({len(raw)} chars): {raw[:200]!r}")

        result = self._parse_json(raw)
        matched = result.get("matched_skills", [])
        valid_names = {s["name"] for s in available}
        ai_skills = [m for m in matched if m in valid_names]

        if ai_skills:
            return self._ensure_design_skills(ai_skills, description, {s["name"] for s in available})

        # Fallback: keyword matching when AI returns nothing or invalid JSON
        print("  [SkillMatcher] AI returned no skills — using keyword fallback")
        kw_skills = self._keyword_match(description, available)
        print(f"  [SkillMatcher] Keyword fallback matched: {kw_skills}")
        return self._ensure_design_skills(kw_skills, description, {s["name"] for s in available})

    _FRONTEND_DESIGN_SIGNALS = {
        "html", "react", "vue", "angular", "svelte", "nextjs", "next.js",
        "frontend", "ui", "interface", "web", "css", "tailwind", "design",
        "dashboard", "landing", "page", "pantalla", "interfaz", "diseño",
    }

    def _ensure_design_skills(self, skills: list[str], description: str, valid_names: set) -> list[str]:
        """Inject skill_ux + skill_ui_design when the project has a frontend component."""
        desc_lower = description.lower()
        has_frontend = any(sig in desc_lower for sig in self._FRONTEND_DESIGN_SIGNALS)
        if not has_frontend:
            return skills
        result = list(skills)
        for skill_name in ("skill_ux", "skill_ui_design"):
            if skill_name in valid_names and skill_name not in result:
                result.append(skill_name)
        return result

    async def _call_gemini(self, payload: dict, role: str = "skill_matcher", task: str = "") -> str:
        from kernel.utils.ai_fallback import is_capacity_error
        result = (await self.gemini.call(payload["system"], payload["user"])).content
        if is_capacity_error(result) and self.gemini:
            fallback = self.builder.build_payload("gemini", role, task)
            result = await self.gemini.prompt(fallback["system"], fallback["user"])
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

    def load_skill_context(self, skill_names: list[str], role: str = "code_generator") -> str:
        """Returns skill content filtered by load_level for the given role.

        Optimized for token efficiency:
        - First skill (primary) gets requested load_level.
        - Subsequent skills get 'summary' to avoid context bloat.
        """
        available = self._load_available_skills()
        by_name = {s["name"]: s for s in available}
        parts = []
        
        for i, name in enumerate(skill_names):
            skill = by_name.get(name)
            if not skill:
                continue
            skill_dir: Path = skill["_path"]
            
            # Token optimization: only the first skill is "full"
            is_primary = (i == 0)
            
            roles_cfg = skill.get("applies_to_roles", {})
            if isinstance(roles_cfg, list):
                load_level = "full" if role in roles_cfg else "summary"
            elif isinstance(roles_cfg, dict):
                role_cfg = roles_cfg.get(role, roles_cfg.get("code_generator", {}))
                load_level = role_cfg.get("load_level", "full") if isinstance(role_cfg, dict) else "summary"
            else:
                load_level = "full"

            # Downgrade non-primary skills to summary to prevent token leakage
            if not is_primary and load_level == "full":
                load_level = "summary"

            sp = skill_dir / "system_prompt.md"
            knowledge_dir = skill_dir / "knowledge"

            if load_level == "full":
                if sp.exists():
                    parts.append(f"### SKILL: {name}\n" + sp.read_text(encoding="utf-8").strip())
                if knowledge_dir.exists():
                    # Limit to 2 knowledge files per skill to save tokens
                    for kf in sorted(knowledge_dir.glob("*.md"))[:2]:
                        parts.append(kf.read_text(encoding="utf-8").strip())

            elif load_level == "summary":
                if sp.exists():
                    lines = sp.read_text(encoding="utf-8").splitlines()
                    parts.append(f"### SKILL: {name} (Summary)\n" + "\n".join(lines[:20]).strip())

            elif load_level == "checklist":
                if knowledge_dir.exists():
                    checklists = sorted(knowledge_dir.glob("checklist*.md"))
                    if checklists:
                        parts.append(checklists[0].read_text(encoding="utf-8").strip())
                    else:
                        all_kf = sorted(knowledge_dir.glob("*.md"))
                        if all_kf:
                            parts.append(all_kf[-1].read_text(encoding="utf-8").strip())

        return "\n\n---\n\n".join(parts)
