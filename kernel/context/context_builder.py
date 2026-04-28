import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List

from kernel.context.provider_prompt_builder import build_provider_system


@dataclass
class BuiltContext:
    """Rich context object with traceability metadata.

    Callers that only need system/user strings can access them directly.
    All other fields provide observability for debugging and logging.
    """
    system: str
    user: str
    provider: str
    role: str
    estimated_tokens: int = 0
    active_skills: List[str] = field(default_factory=list)
    active_profile: Optional[str] = None
    knowledge_sources: List[str] = field(default_factory=list)
    cache_key: Optional[str] = None

    # Allow dict-style access for backwards compatibility
    def __getitem__(self, key: str) -> str:
        if key == "system":
            return self.system
        if key == "user":
            return self.user
        raise KeyError(key)

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return ("system", "user")

    def _estimate_tokens(self) -> int:
        return max(1, (len(self.system) + len(self.user)) // 4)


class ContextBuilder:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.prompts_dir = self.base_dir / "prompts"
        # In-session cache: (provider, role, skills, profile, learning, few_shot) → system_instruction
        # Avoids rebuilding identical strings for every file in the same module.
        self._system_cache: dict[tuple, str] = {}

    def build_payload(
        self,
        provider: str,
        role: str,
        task_content: str,
        extra_context: Optional[str] = None,
        skills_context: Optional[str] = None,
        profile_context: Optional[str] = None,
        skill_role: Optional[str] = None,
        rag_context: Optional[str] = None,
        active_skills: Optional[List[str]] = None,
        active_profile: Optional[str] = None,
        learning_context: Optional[str] = None,
        few_shot_examples: Optional[str] = None,
    ) -> BuiltContext:
        prompt_path = self.prompts_dir / provider / f"{role}.md"
        knowledge_sources: List[str] = []

        _sig = (provider, role, skills_context, profile_context, learning_context, few_shot_examples)
        if _sig in self._system_cache:
            system_instruction = self._system_cache[_sig]
        else:
            if prompt_path.exists():
                base_instruction = prompt_path.read_text(encoding="utf-8")
                knowledge_sources.append(str(prompt_path.relative_to(self.base_dir)))
            else:
                base_instruction = f"You are a SODA agent specialized in {role}."

            if role == "code_generator" and provider in ("claude", "gemini", "ollama"):
                system_instruction = build_provider_system(
                    provider=provider,
                    role=role,
                    base_instruction=base_instruction,
                    skills_context=skills_context,
                    profile_context=profile_context,
                    learning_context=learning_context,
                    few_shot_examples=few_shot_examples,
                )
            else:
                system_instruction = base_instruction
                if skills_context:
                    system_instruction += f"\n\n## Active Skills\n\n{skills_context}"
                if profile_context:
                    system_instruction += f"\n\n## Active Profile Conventions\n\n{profile_context}"
                if learning_context:
                    system_instruction += f"\n\n## Learned Patterns\n\n{learning_context}"
            self._system_cache[_sig] = system_instruction

        if skills_context:
            knowledge_sources.append("skills_context")
        if profile_context:
            knowledge_sources.append("profile_context")
        if learning_context or few_shot_examples:
            knowledge_sources.append("learning_kb")

        user_message = task_content

        # Prepend RAG context from past similar projects
        if rag_context:
            user_message = f"{rag_context}\n\n---\n\n{user_message}"
            knowledge_sources.append("rag_chromadb")

        if extra_context:
            user_message = f"PREVIOUS CONTEXT:\n{extra_context}\n\nCURRENT TASK:\n{user_message}"

        cache_key = hashlib.sha256(
            f"{provider}:{role}:{system_instruction}".encode("utf-8")
        ).hexdigest()[:16]

        ctx = BuiltContext(
            system=system_instruction,
            user=user_message,
            provider=provider,
            role=role,
            active_skills=active_skills or [],
            active_profile=active_profile,
            knowledge_sources=knowledge_sources,
            cache_key=cache_key,
        )
        ctx.estimated_tokens = ctx._estimate_tokens()
        return ctx
