"""
ProviderPromptBuilder — formats system prompts according to each AI provider's
documentation and best practices.

Why this matters:
  - Claude (Anthropic): Responds best to XML-structured input, Constitutional AI
    formatting, clear role definition, and explicit output format instructions.
  - Gemini (Google): Works best with markdown-structured instructions, explicit
    JSON schemas, step-by-step directives, and clear persona assignment.
  - Qwen/Ollama: Benefits from simple direct instructions, few-shot examples,
    strong format enforcement ("ONLY output code"), and shorter system prompts.

Each builder method takes the base system prompt (from the .md file) plus optional
skill context, profile context, and learned examples, and returns an optimized
system string ready for the provider's API.

Reference docs:
  - Claude: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering
  - Gemini: https://ai.google.dev/gemini-api/docs/system-instructions
  - Ollama/Qwen: General instruction-following LLM best practices
"""
from __future__ import annotations

from typing import Optional


# ─── Claude (Anthropic) ─────────────────────────────────────────────────────

_CLAUDE_WRAPPER = """\
<role>
{role_instruction}
</role>

<behavior>
- Always produce complete, production-ready output. Never truncate or use placeholder comments.
- Follow the task JSON fields exactly — they define what to generate.
- If a field like `especificacion_diseno` or `codigo_generado_dependencias` is present, it is authoritative.
- Output ONLY the requested file content. No explanations, no markdown wrappers.
</behavior>
{skills_block}{profile_block}{learning_block}"""

_CLAUDE_SKILLS_BLOCK = """
<active_skills>
{skills}
</active_skills>
"""

_CLAUDE_PROFILE_BLOCK = """
<developer_profile>
{profile}
</developer_profile>
"""

_CLAUDE_LEARNING_BLOCK = """
<learned_patterns>
{learning}
</learned_patterns>
"""


def build_claude_system(
    role: str,
    base_instruction: str,
    skills_context: Optional[str] = None,
    profile_context: Optional[str] = None,
    learning_context: Optional[str] = None,
) -> str:
    """Build Claude-optimized system prompt using XML structured tags."""
    skills_block = _CLAUDE_SKILLS_BLOCK.format(skills=skills_context) if skills_context else ""
    profile_block = _CLAUDE_PROFILE_BLOCK.format(profile=profile_context) if profile_context else ""
    learning_block = _CLAUDE_LEARNING_BLOCK.format(learning=learning_context) if learning_context else ""

    return _CLAUDE_WRAPPER.format(
        role_instruction=base_instruction.strip(),
        skills_block=skills_block,
        profile_block=profile_block,
        learning_block=learning_block,
    ).strip()


# ─── Gemini (Google) ────────────────────────────────────────────────────────

_GEMINI_WRAPPER = """\
# System Role: {role_title}

{role_instruction}

## Output Requirements
- Respond ONLY with what is explicitly requested.
- When JSON is requested, output valid JSON only — no markdown, no code fences.
- When code is requested, output only the code — no explanations.
- Be thorough and complete. Never truncate output.
{skills_block}{profile_block}{learning_block}
## Task Execution
Follow the user message instructions precisely. The task fields are authoritative.
When `codigo_generado_dependencias` is present, use it as the source of truth for imports and identifiers.
"""

_GEMINI_SKILLS_BLOCK = """
## Active Skills & Domain Knowledge
{skills}

"""

_GEMINI_PROFILE_BLOCK = """
## Developer Profile Conventions
{profile}

"""

_GEMINI_LEARNING_BLOCK = """
## Learned Patterns from Previous Projects
{learning}

"""


def build_gemini_system(
    role: str,
    base_instruction: str,
    skills_context: Optional[str] = None,
    profile_context: Optional[str] = None,
    learning_context: Optional[str] = None,
) -> str:
    """Build Gemini-optimized system prompt with markdown structure."""
    # Derive a clean title from the role identifier
    role_title = role.replace("_", " ").title()

    skills_block = _GEMINI_SKILLS_BLOCK.format(skills=skills_context) if skills_context else ""
    profile_block = _GEMINI_PROFILE_BLOCK.format(profile=profile_context) if profile_context else ""
    learning_block = _GEMINI_LEARNING_BLOCK.format(learning=learning_context) if learning_context else ""

    return _GEMINI_WRAPPER.format(
        role_title=role_title,
        role_instruction=base_instruction.strip(),
        skills_block=skills_block,
        profile_block=profile_block,
        learning_block=learning_block,
    ).strip()


# ─── Qwen / Ollama ──────────────────────────────────────────────────────────

_OLLAMA_WRAPPER = """\
{role_instruction}
{skills_block}{profile_block}{few_shot_block}
REGLA ABSOLUTA: Solo código. Sin explicaciones, sin texto adicional, sin bloques markdown.
El output debe ser exactamente el contenido del archivo solicitado y nada más."""

_OLLAMA_SKILLS_BLOCK = """
## Conocimiento de dominio activo
{skills}
"""

_OLLAMA_PROFILE_BLOCK = """
## Convenciones del perfil activo
{profile}
"""

_OLLAMA_FEWSHOT_BLOCK = """
## Referencia de calidad — ejemplos previos exitosos
{examples}
"""


def build_ollama_system(
    role: str,
    base_instruction: str,
    skills_context: Optional[str] = None,
    profile_context: Optional[str] = None,
    few_shot_examples: Optional[str] = None,
) -> str:
    """Build Qwen/Ollama-optimized system prompt with few-shot examples."""
    skills_block = _OLLAMA_SKILLS_BLOCK.format(skills=skills_context) if skills_context else ""
    profile_block = _OLLAMA_PROFILE_BLOCK.format(profile=profile_context) if profile_context else ""
    few_shot_block = _OLLAMA_FEWSHOT_BLOCK.format(examples=few_shot_examples) if few_shot_examples else ""

    return _OLLAMA_WRAPPER.format(
        role_instruction=base_instruction.strip(),
        skills_block=skills_block,
        profile_block=profile_block,
        few_shot_block=few_shot_block,
    ).strip()


# ─── Router ─────────────────────────────────────────────────────────────────

def build_provider_system(
    provider: str,
    role: str,
    base_instruction: str,
    skills_context: Optional[str] = None,
    profile_context: Optional[str] = None,
    learning_context: Optional[str] = None,
    few_shot_examples: Optional[str] = None,
) -> str:
    """Route to the correct provider-specific builder."""
    if provider in ("claude", "claude_haiku"):
        return build_claude_system(
            role=role,
            base_instruction=base_instruction,
            skills_context=skills_context,
            profile_context=profile_context,
            learning_context=learning_context,
        )
    elif provider == "gemini":
        return build_gemini_system(
            role=role,
            base_instruction=base_instruction,
            skills_context=skills_context,
            profile_context=profile_context,
            learning_context=learning_context,
        )
    else:  # ollama / qwen / any local model
        return build_ollama_system(
            role=role,
            base_instruction=base_instruction,
            skills_context=skills_context,
            profile_context=profile_context,
            few_shot_examples=few_shot_examples or learning_context,
        )
