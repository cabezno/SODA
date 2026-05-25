import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

# After this many similar projects, suggest creating a specialized profile
SPECIALIZE_THRESHOLD = 3


class ProfileEvolutionEngine:
    def __init__(self, gemini_driver, context_builder):
        self.gemini = gemini_driver
        self.builder = context_builder
        self.profiles_dir = Path(__file__).resolve().parent.parent.parent / "profiles"
        # Optional callback: notify_fn(message, event_type, data)
        self.notify_fn: Optional[Callable] = None

    def _count_similar_projects(self, profile_name: str) -> int:
        """Count experience entries in the profile (proxy for similar projects done)."""
        exp_dir = self.profiles_dir / "base" / profile_name / "experience"
        if not exp_dir.exists():
            return 0
        return len(list(exp_dir.glob("*_learnings.md")))

    def _check_specialization_opportunity(self, profile_name: str, skills: list[str]) -> None:
        """If enough similar projects exist, fire a specialization suggestion."""
        if not self.notify_fn:
            return
        count = self._count_similar_projects(profile_name)
        if count >= SPECIALIZE_THRESHOLD and count % SPECIALIZE_THRESHOLD == 0:
            dominant_skills = skills[:3] if skills else []
            self.notify_fn(
                f"SODA detectó {count} proyectos completados con el perfil '{profile_name}'. "
                f"Podría ser útil crear un perfil especializado para: {', '.join(dominant_skills) or 'este dominio'}.",
                "SPECIALIZATION_SUGGESTED",
                {
                    "profile_name": profile_name,
                    "project_count": count,
                    "dominant_skills": dominant_skills,
                    "action": "Revisá los aprendizajes acumulados y considerá crear un perfil custom en profiles/custom/.",
                },
            )

    async def evolve(self, project_id: str, description: str, blueprint: dict, architecture: dict, profile_name: str, skills: list[str]) -> dict:
        task = (
            f"PROJECT DESCRIPTION:\n{description}\n\n"
            f"BLUEPRINT:\n{json.dumps(blueprint, ensure_ascii=False, indent=2)[:2000]}\n\n"
            f"ARCHITECTURE MODULES:\n{json.dumps(architecture.get('modulos', []), ensure_ascii=False, indent=2)[:2000]}\n\n"
            f"ACTIVE PROFILE: {profile_name}\n"
            f"ACTIVE SKILLS: {', '.join(skills) or 'none'}"
        )
        from kernel.utils.ai_fallback import is_capacity_error
        payload = self.builder.build_payload("gemini", "profile_evolution", task)
        raw = (await self.gemini.call(payload["system"], payload["user"])).content
        if is_capacity_error(raw) and self.gemini:
            fallback = self.builder.build_payload("gemini", "profile_evolution", task)
            raw = await self.gemini.prompt(fallback["system"], fallback["user"])
        learnings = self._parse(raw)
        self._persist(project_id, profile_name, learnings)
        self._check_specialization_opportunity(profile_name, skills)
        return learnings

    def _parse(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        return {"patterns": [], "anti_patterns": [], "preferences": [], "knowledge_suggestion": None}

    def _persist(self, project_id: str, profile_name: str, learnings: dict):
        experience_dir = self.profiles_dir / "base" / profile_name / "experience"
        experience_dir.mkdir(parents=True, exist_ok=True)

        lines = [f"# Learnings from {project_id}", f"*{datetime.now().strftime('%Y-%m-%d')}*\n"]

        for item in learnings.get("patterns", []):
            lines.append(f"## Pattern: {item.get('title', '')}")
            lines.append(item.get("description", "") + "\n")

        for item in learnings.get("anti_patterns", []):
            lines.append(f"## Anti-pattern: {item.get('title', '')}")
            lines.append(item.get("description", "") + "\n")

        for item in learnings.get("preferences", []):
            lines.append(f"## Preference: {item.get('title', '')}")
            lines.append(item.get("description", "") + "\n")

        suggestion = learnings.get("knowledge_suggestion")
        if suggestion:
            lines.append(f"## Knowledge Suggestion\n{suggestion}\n")

        out = experience_dir / f"{project_id}_learnings.md"
        out.write_text("\n".join(lines), encoding="utf-8")

        # Increment experience_projects counter in identity.yaml
        import yaml
        identity_path = self.profiles_dir / "base" / profile_name / "identity.yaml"
        if identity_path.exists():
            try:
                data = yaml.safe_load(identity_path.read_text(encoding="utf-8"))
                data["experience_projects"] = data.get("experience_projects", 0) + 1
                identity_path.write_text(
                    yaml.dump(data, allow_unicode=True, default_flow_style=False),
                    encoding="utf-8",
                )
            except Exception:
                pass
