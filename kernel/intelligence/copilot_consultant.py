"""CopilotConsultant — code review agent with structured output.

Improvement D: Structured Feedback via tool_use.
When Claude is available, _ask() uses tool_use to return a strictly-typed
dict directly — no regex/JSON parsing, no "dirty JSON" cleanup. The output
of the Copilot is the direct input to Qwen's next generation round.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional, Dict


# ── Tool schema (D: Structured Feedback Protocol) ──────────────────────────

_REVIEW_TOOL: dict = {
    "name": "submit_review",
    "description": (
        "Submit the results of a code or architecture review. "
        "Call this ALWAYS — use has_suggestion=false when everything is correct."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "has_suggestion": {
                "type": "boolean",
                "description": "True if issues were found, false if everything is correct.",
            },
            "message": {
                "type": "string",
                "description": "1-2 sentence summary of all issues found. Empty string when has_suggestion=false.",
            },
            "changes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Each item is one concrete change: what to fix and how. Empty list when has_suggestion=false.",
            },
            "severity": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low"],
                "description": "Worst severity level across all issues found.",
            },
            "scope": {
                "type": "string",
                "enum": ["file", "module", "architecture", "project"],
                "description": "Broadest scope affected by the issues.",
            },
            "target_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "File paths directly affected. Empty list if unknown.",
            },
            "target_modules": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Module names directly affected. Empty list if unknown.",
            },
            "diagnosis": {
                "type": "string",
                "description": "Root cause explanation in 1-2 sentences.",
            },
            "proposed_fix": {
                "type": "string",
                "description": "Most impactful single fix to apply.",
            },
            "repair_mode": {
                "type": "string",
                "enum": ["annotate", "regenerate", "rephase", "ignore"],
                "description": (
                    "Suggested action: annotate=note only, regenerate=rebuild module(s), "
                    "rephase=rerun the entire phase, ignore=skip."
                ),
            },
            "verification": {
                "type": "string",
                "description": "How to verify the fix was applied correctly.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence in the diagnosis, 0.0 to 1.0.",
            },
        },
        "required": ["has_suggestion", "changes"],
    },
}

# Enriched field names — used by normalize_review and consumers
_ENRICHED_FIELDS = (
    "severity", "scope", "target_files", "target_modules",
    "diagnosis", "proposed_fix", "repair_mode", "verification", "confidence",
)


def normalize_review(review: Optional[Dict]) -> Optional[Dict]:
    """Ensure every review dict carries all enriched fields.

    Backward-compatible: legacy payloads (has_suggestion + message + changes only)
    get sensible defaults added; enriched payloads pass through unchanged.
    Returns None when review is None (no issues found).
    """
    if review is None:
        return None
    if not review.get("has_suggestion"):
        return None

    changes = review.get("changes") or []
    message = review.get("message", "")

    review.setdefault("severity", "medium")
    review.setdefault("scope", "module")
    review.setdefault("target_files", [])
    review.setdefault("target_modules", [])
    review.setdefault("diagnosis", changes[0] if changes else message)
    review.setdefault("proposed_fix", "\n".join(changes) if changes else message)
    review.setdefault("repair_mode", "annotate")
    review.setdefault("verification", "")
    review.setdefault("confidence", 0.5)
    return review

SYSTEM = "Eres un Consultor Senior de Arquitectura y Software (Copilot). Sos directo, conciso y técnico."

# Fallback format used when tool_use is unavailable (Gemini/Ollama drivers)
REPLY_FORMAT = """\
Si todo está correcto responde SOLO con "OK".
Si encontrás problemas, listá TODOS en una única respuesta con este JSON (sin texto extra):
{
  "has_suggestion": true,
  "message": "Resumen de todos los problemas encontrados (1-2 oraciones)",
  "changes": [
    "Cambio 1: descripción técnica concreta del primer problema y su solución",
    "Cambio 2: descripción técnica concreta del segundo problema y su solución"
  ]
}
IMPORTANTE: incluí TODOS los problemas que encontrés en esta única respuesta.
No reserves issues para rondas posteriores."""


def _parse_json(text: str) -> Optional[Dict]:
    """Fallback JSON parser used when tool_use is unavailable."""
    if not text or "OK" in text.strip()[:10]:
        return None
    try:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        raw = m.group(1) if m else text
        parsed = json.loads(raw)
        if "proposed_change" in parsed and "changes" not in parsed:
            change = parsed.pop("proposed_change")
            parsed["changes"] = [change] if change else []
        if "changes" not in parsed:
            parsed["changes"] = []
        return parsed
    except Exception:
        return None


def _extract_fix_json(text: str) -> Optional[Dict]:
    """Extract the {files: {...}} JSON from a Copilot fix response."""
    if not text or text.startswith("ERROR:"):
        return None
    # Try direct parse
    for attempt in (text, text[text.find("{"):text.rfind("}") + 1] if "{" in text else ""):
        try:
            data = json.loads(attempt)
            if isinstance(data.get("files"), dict):
                return data
        except Exception:
            pass
    # Try code block
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if m:
        try:
            data = json.loads(m.group(1))
            if isinstance(data.get("files"), dict):
                return data
        except Exception:
            pass
    return None


class CopilotConsultant:
    """Observer agent present at every pipeline phase.

    Reviews outputs and generates proactive suggestions after each step.
    Uses structured tool_use output (Improvement D) when Claude is available,
    falling back to JSON parsing for other drivers.
    """

    def __init__(self, ai_driver, context_builder):
        self.ai = ai_driver
        self.builder = context_builder
        self._anthropic_client = None  # lazy-loaded for tool_use calls

    def _get_anthropic_client(self):
        if self._anthropic_client is not None:
            return self._anthropic_client
        try:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self._anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)
        except ImportError:
            pass
        return self._anthropic_client

    async def _ask(self, prompt: str, cached_context: str | None = None) -> Optional[Dict]:
        """Call the AI with structured tool_use output (D).

        Falls back to JSON parsing if the Anthropic client is unavailable.
        cached_context: static context block (A+B) sent cached before the prompt.
        """
        client = self._get_anthropic_client()
        if client is None:
            # Fallback: use generic driver without tool_use
            dr = await self.ai.call(SYSTEM, prompt + "\n\n" + REPLY_FORMAT, max_tokens=512, temperature=0.3)
            return normalize_review(_parse_json(dr.content))

        # Build user content with optional cached prefix (A+B)
        if cached_context:
            user_content = [
                {"type": "text", "text": cached_context, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": prompt},
            ]
        else:
            user_content = prompt

        try:
            from anthropic import AsyncAnthropic
            model = getattr(self.ai, "model", None) or "claude-haiku-4-5-20251001"
            # Haiku is cheapest and fast enough for code review
            review_model = "claude-haiku-4-5-20251001"
            system_block = [
                {"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}
            ]
            message = await client.messages.create(
                model=review_model,
                max_tokens=512,
                system=system_block,
                tools=[_REVIEW_TOOL],
                tool_choice={"type": "any"},
                messages=[{"role": "user", "content": user_content}],
            )
            # Extract tool_use block — always present because tool_choice="any"
            for block in message.content:
                if block.type == "tool_use" and block.name == "submit_review":
                    result: dict = block.input
                    result.setdefault("message", "")
                    result.setdefault("changes", [])
                    return normalize_review(result)
        except Exception:
            pass

        # Final fallback: generic driver + regex parse
        dr = await self.ai.call(SYSTEM, prompt + "\n\n" + REPLY_FORMAT, max_tokens=512, temperature=0.3)
        return normalize_review(_parse_json(dr.content))

    # ------------------------------------------------------------------ #
    # Phase: Capabilities                                                  #
    # ------------------------------------------------------------------ #

    async def review_capabilities(self, skills: list, profile: str, description: str) -> Optional[Dict]:
        """After CAP: ¿el perfil y skills elegidos son los mejores para este proyecto?"""
        prompt = f"""\
El sistema eligió automáticamente estas capacidades para el proyecto:

DESCRIPCIÓN: {description[:600]}
PERFIL ELEGIDO: {profile}
SKILLS ELEGIDOS: {', '.join(skills) or 'ninguno'}

¿El perfil y los skills son los óptimos para este proyecto? ¿Falta algún skill crítico o el perfil no es el más adecuado?

{REPLY_FORMAT}"""
        return await self._ask(prompt)

    # ------------------------------------------------------------------ #
    # Phase: Requirements / Blueprint                                      #
    # ------------------------------------------------------------------ #

    async def review_blueprint(self, blueprint: dict, description: str) -> Optional[Dict]:
        """After REQ: ¿el blueprint captura todo lo necesario?"""
        prompt = f"""\
SODA generó este Blueprint a partir de la descripción del usuario.

DESCRIPCIÓN: {description[:400]}
BLUEPRINT: {json.dumps(blueprint, ensure_ascii=False, indent=2)[:1800]}

¿Falta alguna funcionalidad crítica? ¿El stack es el óptimo? ¿Hay inconsistencias?

{REPLY_FORMAT}"""
        return await self._ask(prompt)

    # ------------------------------------------------------------------ #
    # Phase: Architecture                                                  #
    # ------------------------------------------------------------------ #

    async def review_architecture(self, architecture: dict, blueprint: dict) -> Optional[Dict]:
        """After ARCH: ¿la arquitectura de módulos es sólida?"""
        modulos = architecture.get("modulos", [])
        prompt = f"""\
SODA generó esta arquitectura de módulos.

BLUEPRINT BASE: {json.dumps(blueprint, ensure_ascii=False)[:600]}
MÓDULOS ({len(modulos)}): {json.dumps([{'nombre': m.get('nombre'), 'responsabilidad': m.get('responsabilidad','')[:80], 'dependencias': m.get('dependencias',[])} for m in modulos], ensure_ascii=False, indent=2)[:1800]}

¿Hay cuellos de botella, dependencias circulares, módulos mal separados o patrones de diseño faltantes (seguridad, caché, autenticación)?

{REPLY_FORMAT}"""
        return await self._ask(prompt)

    # ------------------------------------------------------------------ #
    # Phase: Planning                                                      #
    # ------------------------------------------------------------------ #

    async def review_plan(self, plan_levels: list, architecture: dict) -> Optional[Dict]:
        """After PLAN: ¿el orden de ejecución es el más eficiente?"""
        modulos = architecture.get("modulos", [])
        prompt = f"""\
SODA construyó este plan de ejecución (niveles de paralelismo):

NIVELES DE EJECUCIÓN: {json.dumps(plan_levels, ensure_ascii=False)}
TOTAL MÓDULOS: {len(modulos)}

¿El orden de ejecución tiene sentido? ¿Hay algo que debería generarse antes o después para evitar dependencias rotas?

{REPLY_FORMAT}"""
        return await self._ask(prompt)

    # ------------------------------------------------------------------ #
    # Phase: Development (per module)                                      #
    # ------------------------------------------------------------------ #

    async def review_module(self, module_name: str, generated_files: list, blueprint: dict) -> Optional[Dict]:
        """After each module: ¿el código generado cumple los contratos? (validation-status based)"""
        files_summary = [{"file": gf.filepath, "validated": gf.validated, "attempts": gf.attempts} for gf in generated_files]
        has_failures = any(not gf.validated for gf in generated_files)
        if not has_failures:
            return None  # solo sugiere si hay problemas
        prompt = f"""\
SODA generó el módulo '{module_name}' con estos resultados:

ARCHIVOS: {json.dumps(files_summary, ensure_ascii=False)}
STACK DEL PROYECTO: {json.dumps(blueprint.get('stack_sugerido', {}), ensure_ascii=False)}

Algunos archivos no pasaron validación (validated=false). ¿Qué ajuste técnico recomendás para la siguiente regeneración?

{REPLY_FORMAT}"""
        return await self._ask(prompt)

    async def review_module_code(
        self, module_name: str, files: dict, blueprint: dict
    ) -> Optional[Dict]:
        """Review actual code content — fires every Qwen→Copilot round.

        A+B: stack context sent as cached_context (static across all files
        of the same project), code content sent as variable user_message.
        D: result comes directly from tool_use — no parsing needed.
        """
        files_preview = "\n\n".join(
            f"### {path}\n```\n{content[:900]}\n```"
            for path, content in list(files.items())[:5]
        )
        # A+B: static block → cached; variable block → prompt
        cached_context = (
            f"STACK DEL PROYECTO:\n"
            f"{json.dumps(blueprint.get('stack_sugerido', {}), ensure_ascii=False)}\n\n"
            f"MÓDULO EN REVISIÓN: {module_name}"
        )
        prompt = f"""\
CÓDIGO GENERADO:
{files_preview[:3000]}

¿El código es correcto y completo? ¿Hay bugs, imports faltantes, lógica incompleta o violaciones del stack?"""
        return await self._ask(prompt, cached_context=cached_context)

    async def fix_module_code(
        self, module_name: str, files: dict, review: dict, blueprint: dict
    ) -> Optional[Dict[str, str]]:
        """Copilot directly corrects code based on the review findings.

        Returns {filepath: corrected_content} for files that were changed,
        or None if Copilot cannot produce a fix (driver error, no changes needed).
        Only files that actually changed are returned — callers merge with originals.
        """
        changes = review.get("changes") or []
        if not changes:
            return None

        changes_block = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(changes))
        files_block = "\n\n".join(
            f"### {path}\n```python\n{content}\n```"
            for path, content in list(files.items())[:6]
        )
        stack_json = json.dumps(blueprint.get("stack_sugerido", {}), ensure_ascii=False)
        prompt = f"""\
Módulo: {module_name}
Stack: {stack_json}

PROBLEMAS ENCONTRADOS:
{changes_block}

CÓDIGO ACTUAL:
{files_block[:5000]}

Aplicá TODOS los cambios listados y devolvé el código corregido.
Respondé SOLO con JSON sin texto adicional:
{{
  "files": {{
    "ruta/del/archivo.py": "<código completo corregido>",
    "otro/archivo.py": "<código completo corregido>"
  }}
}}
Incluí SOLO los archivos que modificaste. Código completo, no snippets."""

        try:
            dr = await self.ai.call(
                SYSTEM,
                prompt,
                max_tokens=8192,
                temperature=0.15,
            )
            data = _extract_fix_json(dr.content)
            if data and isinstance(data.get("files"), dict) and data["files"]:
                return {k: v for k, v in data["files"].items() if isinstance(v, str) and v.strip()}
        except Exception:
            pass
        return None

    async def verify_module_code(
        self, module_name: str, files: dict, applied_change: str, blueprint: dict
    ) -> Optional[Dict]:
        """After Qwen applied Copilot feedback: verify the fix was actually implemented.

        A+B: static context cached; variable parts (change + new code) sent fresh.
        """
        files_preview = "\n\n".join(
            f"### {path}\n```\n{content[:900]}\n```"
            for path, content in list(files.items())[:5]
        )
        cached_context = (
            f"STACK DEL PROYECTO:\n"
            f"{json.dumps(blueprint.get('stack_sugerido', {}), ensure_ascii=False)}\n\n"
            f"MÓDULO EN VERIFICACIÓN: {module_name}"
        )
        prompt = f"""\
CAMBIO SUGERIDO PREVIAMENTE: {applied_change[:400]}

CÓDIGO REGENERADO:
{files_preview[:2500]}

¿El cambio fue implementado correctamente? ¿Queda algún problema pendiente?"""
        return await self._ask(prompt, cached_context=cached_context)

    # ------------------------------------------------------------------ #
    # Phase: Validation                                                    #
    # ------------------------------------------------------------------ #

    async def review_validation(self, validation_result: dict, blueprint: dict) -> Optional[Dict]:
        """After VALIDATION: ¿cómo resolver los errores de build?

        A+B: stack sent cached; errors (variable per build attempt) sent fresh.
        """
        errors = validation_result.get("errors_final", "") or validation_result.get("errors", "")
        if not errors:
            return None
        cached_context = (
            f"STACK DEL PROYECTO:\n"
            f"{json.dumps(blueprint.get('stack_sugerido', {}), ensure_ascii=False)}"
        )
        prompt = f"""\
El build/validación del proyecto falló con estos errores:

ERRORES: {str(errors)[:1200]}

¿Cuál es la causa raíz más probable y qué cambio concreto resolvería estos errores?"""
        return await self._ask(prompt, cached_context=cached_context)

    # ------------------------------------------------------------------ #
    # Phase: Evolution                                                     #
    # ------------------------------------------------------------------ #

    async def review_evolution(self, learnings: dict, project_description: str) -> Optional[Dict]:
        """After EVOLUTION: ¿los aprendizajes capturan lo más importante?"""
        if not learnings:
            return None
        prompt = f"""\
SODA capturó estos learnings al finalizar el proyecto:

PROYECTO: {project_description[:300]}
LEARNINGS: {json.dumps(learnings, ensure_ascii=False, indent=2)[:1000]}

¿Falta capturar algún aprendizaje clave para proyectos futuros similares?

{REPLY_FORMAT}"""
        return await self._ask(prompt)
