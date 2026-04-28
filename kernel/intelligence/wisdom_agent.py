import asyncio
import json
import re
from pathlib import Path
from typing import Optional


class WisdomObservation:
    def __init__(self, obs_type: str, message: str, suggestion: str = ""):
        self.type = obs_type
        self.message = message
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        return {"type": self.type, "message": self.message, "suggestion": self.suggestion}


class WisdomAgent:
    def __init__(self, gemini_driver, context_builder, claude_driver=None):
        self.gemini = gemini_driver
        self.claude = claude_driver
        self.builder = context_builder

    async def analyze(
        self,
        description: str,
        skills: list[str],
        profile: str,
        workspace: Optional[Path] = None,
    ) -> list[WisdomObservation]:
        from kernel.utils.ai_fallback import is_capacity_error

        # PASO 2: inject historical constraints from RequirementsStore when available
        constraints_block = ""
        if workspace is not None:
            try:
                from kernel.persistence.requirements_store import RequirementsStore
                constraints_block = RequirementsStore(workspace).as_constraint_block()
            except Exception:
                pass

        task_parts = []
        if constraints_block:
            task_parts.append(
                f"<restricciones_historicas>\n{constraints_block}\n</restricciones_historicas>"
            )
        task_parts.append(
            f"PROJECT DESCRIPTION:\n{description}\n\n"
            f"MATCHED PROFILE: {profile}\n"
            f"MATCHED SKILLS: {', '.join(skills) or 'none'}"
        )
        task = "\n\n".join(task_parts)

        payload = self.builder.build_payload("gemini", "wisdom_agent", task)
        raw = (await self.gemini.call(payload["system"], payload["user"])).content
        if is_capacity_error(raw) and self.claude:
            fallback = self.builder.build_payload("claude", "wisdom_agent", task)
            raw = await self.claude.prompt(fallback["system"], fallback["user"])
        return self._parse(raw)

    def _parse(self, text: str) -> list[WisdomObservation]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return []
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return []

        observations = []
        for obs in data.get("observations", []):
            observations.append(WisdomObservation(
                obs_type=obs.get("type", "warning"),
                message=obs.get("message", ""),
                suggestion=obs.get("suggestion", ""),
            ))
        return observations
