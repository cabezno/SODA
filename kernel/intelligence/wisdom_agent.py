import asyncio
import json
import re
from typing import Optional


class WisdomObservation:
    def __init__(self, obs_type: str, message: str, suggestion: str = ""):
        self.type = obs_type
        self.message = message
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        return {"type": self.type, "message": self.message, "suggestion": self.suggestion}


class WisdomAgent:
    def __init__(self, gemini_driver, context_builder):
        self.gemini = gemini_driver
        self.builder = context_builder

    async def analyze(
        self,
        description: str,
        skills: list[str],
        profile: str,
    ) -> list[WisdomObservation]:
        task = (
            f"PROJECT DESCRIPTION:\n{description}\n\n"
            f"MATCHED PROFILE: {profile}\n"
            f"MATCHED SKILLS: {', '.join(skills) or 'none'}"
        )
        payload = self.builder.build_payload("gemini", "wisdom_agent", task)
        raw = await asyncio.to_thread(self.gemini.prompt, payload["system"], payload["user"])
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
