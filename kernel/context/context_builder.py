from pathlib import Path
from typing import Optional, Dict


class ContextBuilder:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.prompts_dir = self.base_dir / "prompts"

    def build_payload(
        self,
        provider: str,
        role: str,
        task_content: str,
        extra_context: Optional[str] = None,
        skills_context: Optional[str] = None,
        profile_context: Optional[str] = None,
    ) -> Dict[str, str]:
        prompt_path = self.prompts_dir / provider / f"{role}.md"
        if prompt_path.exists():
            system_instruction = prompt_path.read_text(encoding="utf-8")
        else:
            system_instruction = f"You are a SODA agent specialized in {role}."

        # Append skill and profile knowledge to system prompt
        if skills_context:
            system_instruction += f"\n\n## Active Skills\n\n{skills_context}"
        if profile_context:
            system_instruction += f"\n\n## Active Profile Conventions\n\n{profile_context}"

        user_message = task_content
        if extra_context:
            user_message = f"PREVIOUS CONTEXT:\n{extra_context}\n\nCURRENT TASK:\n{task_content}"

        return {"system": system_instruction, "user": user_message}
