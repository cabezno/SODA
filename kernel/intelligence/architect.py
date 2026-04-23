"""Architect — generates and refines MasterContracts (Arquitecto v2).

Uses Claude with model selection based on project complexity:
- simple  → claude-haiku-4-5-20251001
- medium  → claude-sonnet-4-6
- complex → claude-opus-4-7
"""
from __future__ import annotations

import json
from pathlib import Path

from kernel.drivers.claude_driver import ClaudeDriver
from kernel.intelligence.complexity_classifier import (
    MODEL_ASSIGNMENT_BY_COMPLEXITY,
    MODEL_CALL_CONFIG,
    ComplexityLevel,
)
from kernel.intelligence.contract_schemas import MasterContract

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "claude"

_COMPLEXITY_PROMPT_MAP = {
    ComplexityLevel.SIMPLE: "architect_simple.md",
    ComplexityLevel.MEDIUM: "architect_medium.md",
    ComplexityLevel.COMPLEX: "architect_complex.md",
}


class Architect:
    """Generates and refines MasterContracts using Claude.

    The model is selected based on project complexity:
    - simple  → Haiku (fast, cheap)
    - medium  → Sonnet (balanced)
    - complex → Opus (most capable)
    """

    def __init__(self, claude_driver: ClaudeDriver):
        self.driver = claude_driver

    async def generate_master_contract(
        self,
        blueprint: dict,
        complexity: ComplexityLevel,
        active_skills: list | None = None,
        active_profile: dict | None = None,
        goal_tree: dict | None = None,
    ) -> MasterContract:
        """Generate the initial MasterContract.

        goal_tree may be empty ({}) on first iteration — the Architect will
        generate goal_ids internally. Full traceability validation happens
        after the GoalTree is built from the approved contract.

        TODO: The correct flow would build the GoalTree from the blueprint
        *before* this call so the Architect receives validated goal IDs upfront.
        This is left as a future refactor once the pipeline migrates fully to
        the MasterContract model.
        """
        model = MODEL_ASSIGNMENT_BY_COMPLEXITY[complexity.value]
        system_prompt = self._load_prompt(_COMPLEXITY_PROMPT_MAP[complexity])
        user_message = self._build_generation_prompt(
            blueprint=blueprint,
            skills=active_skills or [],
            profile=active_profile or {},
            goal_tree=goal_tree or {},
        )

        response = await self.driver.call(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            **MODEL_CALL_CONFIG[model],
        )

        if response.error_code:
            raise RuntimeError(
                f"Architect generation failed [{response.error_code}]: {response.content}"
            )

        contract_data = self._parse_json(response.content)
        contract_data["complexity_level"] = complexity.value
        contract_data["model_used"] = model

        return MasterContract(**contract_data)

    async def refine_contract(
        self,
        current_contract: MasterContract,
        audit_feedback: object,  # AuditReport — avoid circular import
        complexity: ComplexityLevel,
    ) -> MasterContract:
        """Refine a contract based on auditor feedback.

        Preserves everything that is correct and fixes only the reported issues.
        """
        model = MODEL_ASSIGNMENT_BY_COMPLEXITY[complexity.value]
        system_prompt = self._load_prompt("architect_refinement.md")
        feedback_text = audit_feedback.to_architect_feedback()
        user_message = self._build_refinement_prompt(
            current_contract=current_contract,
            feedback=feedback_text,
        )

        response = await self.driver.call(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            **MODEL_CALL_CONFIG[model],
        )

        if response.error_code:
            raise RuntimeError(
                f"Architect refinement failed [{response.error_code}]: {response.content}"
            )

        contract_data = self._parse_json(response.content)
        contract_data["complexity_level"] = complexity.value
        contract_data["model_used"] = model

        return MasterContract(**contract_data)

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_generation_prompt(
        self,
        blueprint: dict,
        skills: list,
        profile: dict,
        goal_tree: dict,
    ) -> str:
        goal_section = (
            "```json\n" + json.dumps(goal_tree, indent=2, ensure_ascii=False) + "\n```"
            if goal_tree
            else "(árbol de objetivos aún no construido — generá goal_ids descriptivos basados en el blueprint)"
        )

        return f"""Generá el contrato maestro para este proyecto.

## Blueprint del proyecto
```json
{json.dumps(blueprint, indent=2, ensure_ascii=False)}
```

## Árbol de objetivos
{goal_section}

## Skills activas
{self._format_skills(skills)}

## Perfil activo
{self._format_profile(profile)}

## Instrucciones
Generá un contrato maestro siguiendo el schema MasterContract.
Asegurate de incluir:
- Al menos 3 puntos de extensión (tipos: middleware_slot, metadata_field, event_channel)
- Al menos 3 tipos de error estandarizados
- Todos los módulos con al menos un goal_id descriptivo
- Convenciones de nombres consistentes (ver system prompt)
- Documentación clara en cada elemento

Respondé solo con el JSON del contrato, sin explicaciones adicionales.
"""

    def _build_refinement_prompt(
        self,
        current_contract: MasterContract,
        feedback: str,
    ) -> str:
        return f"""Refiná el siguiente contrato basándote en el feedback del auditor.

## Contrato actual
```json
{current_contract.model_dump_json(indent=2)}
```

## Feedback del auditor
{feedback}

## Instrucciones
Corregí los errores críticos identificados.
Preservá todo lo que está correcto.
Mantené el mismo schema de output.

Respondé solo con el JSON del contrato corregido.
"""

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def _format_skills(self, skills: list) -> str:
        if not skills:
            return "Ninguna skill activa"
        return "\n".join(
            f"- {s.get('name', s) if isinstance(s, dict) else s}: "
            f"{s.get('description', '') if isinstance(s, dict) else ''}"
            for s in skills
        )

    def _format_profile(self, profile: dict) -> str:
        if not profile:
            return "Sin perfil específico"
        return (
            f"Perfil: {profile.get('name', 'Desconocido')}\n"
            f"Experiencia: {profile.get('description', '')}\n"
            f"Preferencias de stack: {profile.get('preferred_stacks', [])}"
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _load_prompt(filename: str) -> str:
        path = _PROMPTS_DIR / filename
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _parse_json(content: str) -> dict:
        """Extract JSON from response, stripping markdown fences if present."""
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # Remove opening fence (```json or ```)
            start = 1
            # Find closing fence
            end = len(lines)
            for i in range(len(lines) - 1, 0, -1):
                if lines[i].strip().startswith("```"):
                    end = i
                    break
            text = "\n".join(lines[start:end])
        return json.loads(text)
