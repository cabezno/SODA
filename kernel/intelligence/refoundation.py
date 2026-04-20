import asyncio
import json
import re


class RefoundationEngine:
    def __init__(self, claude_driver, context_builder):
        self.claude = claude_driver
        self.builder = context_builder

    async def summarize(self, description: str, blueprint: dict, architecture: dict) -> dict:
        task = (
            f"ORIGINAL DESCRIPTION:\n{description}\n\n"
            f"BLUEPRINT:\n{json.dumps(blueprint, ensure_ascii=False, indent=2)[:2000]}\n\n"
            f"ARCHITECTURE:\n{json.dumps(architecture.get('modulos', []), ensure_ascii=False, indent=2)[:2000]}"
        )
        payload = self.builder.build_payload("claude", "refoundation", task)
        raw = await self.claude.prompt(payload["system"], payload["user"])
        return self._parse(raw)

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
        return {"refounded_description": text[:500], "key_decisions": [], "completed_modules": [], "remaining_work": None}
