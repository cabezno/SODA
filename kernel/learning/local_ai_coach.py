"""
LocalAICoach — enriches Qwen/local-model prompts with relevant learned examples.

Queries the KnowledgeBase for past successful code patterns and escalation cases,
then formats them as few-shot examples to inject into the local AI's task context.

This is the "learning feedback loop" for Qwen:
  1. BehaviorObserver records cloud AI outputs
  2. KnowledgeBase organizes them into queryable patterns
  3. LocalAICoach injects the most relevant ones into Qwen's next prompt
  4. Qwen generates better code by following proven patterns

The coach is intentionally non-blocking: if it fails for any reason, it returns
an empty string and the generation proceeds without enrichment.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _lang_from_path(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    return {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "react", ".tsx": "react_ts", ".vue": "vue",
        ".html": "html", ".css": "css", ".go": "go",
        ".java": "java", ".cs": "csharp", ".rs": "rust",
    }.get(ext, "other")


def _framework_from_task(task_json: str) -> str:
    """Extract framework hint from the task JSON string."""
    try:
        task = json.loads(task_json)
        stack = task.get("stack", {})
        stack_text = " ".join(str(v).lower() for v in stack.values())
        for fw in ("fastapi", "flask", "django", "express", "nextjs", "react",
                   "vue", "angular", "spring", "gin", "rails", "laravel"):
            if fw in stack_text:
                return fw
    except Exception:
        pass
    return ""


class LocalAICoach:
    """
    Enriches the local model's context with:
      1. Successful code patterns from previous projects (few-shot examples)
      2. Escalation recovery patterns (what cloud AI did when Qwen failed)
      3. Phase-specific guidance derived from observed cloud AI behavior
    """

    MAX_EXAMPLES = 2        # Max code examples to inject per task
    MAX_ESCALATIONS = 1     # Max escalation cases to inject
    SNIPPET_CHARS = 500     # Max chars of each code snippet

    def __init__(self, knowledge_base):
        self.kb = knowledge_base

    def build_few_shot_context(
        self,
        task_json: str,
        filepath: str,
        role: str = "code_generator",
    ) -> str:
        """
        Build a few-shot enrichment string to prepend to the local AI's task.
        Returns empty string if no relevant examples exist or on any error.
        """
        try:
            lang = _lang_from_path(filepath)
            if lang == "other":
                return ""

            framework = _framework_from_task(task_json)
            examples = self.kb.query_code_examples(
                language=lang, framework=framework, role=role, n=self.MAX_EXAMPLES
            )
            escalations = self.kb.query_escalation_patterns(language=lang, n=self.MAX_ESCALATIONS)

            if not examples and not escalations:
                return ""

            parts: list[str] = ["## Ejemplos de código exitoso previo\n"]
            parts.append("Los siguientes ejemplos fueron generados por IAs de alto rendimiento para "
                         "proyectos similares. Usálos como referencia de calidad y estilo:\n")

            for i, ex in enumerate(examples, 1):
                desc = ex.get("description", f"Ejemplo {i}")
                provider = ex.get("provider", "")
                snippet = (ex.get("example_output") or "")[:self.SNIPPET_CHARS]
                provider_label = f" [{provider}]" if provider and provider != "unknown" else ""
                parts.append(f"\n### Ejemplo {i}{provider_label} — {desc}")
                if ex.get("context_hint"):
                    parts.append(f"*Cuándo aplicar*: {ex['context_hint'][:150]}")
                parts.append(f"```\n{snippet}\n```")

            if escalations:
                parts.append("\n## Errores comunes del modelo local y cómo se corrigieron\n")
                for esc in escalations:
                    desc = esc.get("description", "Caso de escalación")
                    failure = (esc.get("failure_pattern") or "")[:200]
                    solution = (esc.get("solution_snippet") or "")[:self.SNIPPET_CHARS]
                    provider = esc.get("provider", "")
                    parts.append(f"**Problema detectado**: {desc}")
                    if failure:
                        parts.append(f"*Error típico de Qwen*: `{failure}`")
                    parts.append(f"*Solución correcta [{provider}]*:")
                    parts.append(f"```\n{solution}\n```")

            parts.append("\n---\n*Generá código de calidad equivalente o superior a los ejemplos anteriores.*\n")
            return "\n".join(parts)

        except Exception as exc:
            logger.debug("LocalAICoach.build_few_shot_context failed: %s", exc)
            return ""

    def get_architecture_guidance(self, project_description: str, project_type: str = "") -> str:
        """Return architecture patterns relevant to this project type."""
        try:
            patterns = self.kb.query_architecture_patterns(project_type=project_type, n=2)
            if not patterns:
                return ""
            parts = ["## Patrones de arquitectura aprendidos\n"]
            for p in patterns:
                parts.append(f"**{p.get('description', 'Patrón')}** ({p.get('project_type', '')})")
                if p.get("modules_summary"):
                    parts.append(f"Módulos: {p['modules_summary'][:300]}")
                if p.get("stack_hint"):
                    parts.append(f"Stack: {p['stack_hint']}")
                parts.append("")
            return "\n".join(parts)
        except Exception as exc:
            logger.debug("LocalAICoach.get_architecture_guidance failed: %s", exc)
            return ""
