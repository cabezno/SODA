from __future__ import annotations

import json
from pathlib import Path


class ProjectChat:
    """Project-scoped chat helper that builds context and delegates answering."""

    def build_user_payload(self, meta: dict, source_dir: Path, message: str) -> str:
        blueprint = json.dumps(meta.get("blueprint", {}), ensure_ascii=False, indent=2)
        architecture = json.dumps(meta.get("architecture", {}), ensure_ascii=False, indent=2)

        file_list = ""
        if source_dir.exists():
            files = sorted(str(p.relative_to(source_dir)) for p in source_dir.rglob("*") if p.is_file())
            file_list = "\n".join(files[:40])

        return (
            f"BLUEPRINT:\n{blueprint}\n\n"
            f"ARQUITECTURA:\n{architecture}\n\n"
            f"ARCHIVOS GENERADOS:\n{file_list or '(ninguno aun)'}\n\n"
            f"PREGUNTA: {message}"
        )

    async def answer(self, driver, meta: dict, source_dir: Path, message: str) -> str:
        system = (
            "Sos el asistente del proyecto generado por SODA. "
            "Responde en espanol de forma concisa y util."
        )
        user = self.build_user_payload(meta, source_dir, message)
        return await driver.prompt(system, user)
