"""CopilotConsultant — code review agent with structured output.

Improvement D: Structured Feedback via tool_use.
When Gemini is available, _ask() uses tool_use to return a strictly-typed
dict directly — no regex/JSON parsing, no "dirty JSON" cleanup. The output
of the Copilot is the direct input to Qwen's next generation round.

Fix strategy:
- < 30% change ratio → Haiku applies surgical function-level patches
- ≥ 30% change ratio → systemic issue, logged and escalated (no Haiku fix attempt)
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, List

SYSTEMIC_THRESHOLD = 0.30  # if more than 30% of functions need fixing → systemic issue


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

# ── Contract validation tool schema ─────────────────────────────────────────

_CONTRACT_VALIDATION_TOOL: dict = {
    "name": "submit_contract_validation",
    "description": (
        "Submit the results of validating a MasterContract against its blueprint. "
        "Always call this — use is_coherent=true when no issues are found."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "is_coherent": {
                "type": "boolean",
                "description": "True if the contract fully and correctly covers the blueprint.",
            },
            "coverage_gaps": {
                "type": "array",
                "description": "Blueprint funcionalidades not covered by any module interface.",
                "items": {
                    "type": "object",
                    "properties": {
                        "funcionalidad_id": {"type": "string"},
                        "missing_behavior": {"type": "string"},
                        "suggested_module": {"type": "string"},
                    },
                    "required": ["funcionalidad_id", "missing_behavior"],
                },
            },
            "interface_issues": {
                "type": "array",
                "description": "Methods or interfaces that are wrong, incomplete or inconsistent with the module purpose.",
                "items": {
                    "type": "object",
                    "properties": {
                        "module_id": {"type": "string"},
                        "interface_name": {"type": "string"},
                        "issue": {"type": "string"},
                        "fix": {"type": "string"},
                    },
                    "required": ["module_id", "issue", "fix"],
                },
            },
            "communication_issues": {
                "type": "array",
                "description": (
                    "Dependency mismatches: module A depends on B but B doesn't expose "
                    "what A needs, or the depends_on graph is incomplete."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "consumer_module": {"type": "string"},
                        "provider_module": {"type": "string"},
                        "issue": {"type": "string"},
                        "fix": {"type": "string"},
                    },
                    "required": ["consumer_module", "provider_module", "issue", "fix"],
                },
            },
            "communication_map": {
                "type": "object",
                "description": (
                    "For each module_id: what it receives from its dependencies "
                    "and what it exposes to its consumers. Used by code generator."
                ),
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "receives_from": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "module_id": {"type": "string"},
                                    "methods_used": {"type": "array", "items": {"type": "string"}},
                                },
                            },
                        },
                        "exposes_to": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "module_ids that consume this module's interfaces.",
                        },
                    },
                },
            },
        },
        "required": ["is_coherent", "coverage_gaps", "interface_issues", "communication_issues", "communication_map"],
    },
}


# ── Contract validation result ───────────────────────────────────────────────

@dataclass
class ContractValidationResult:
    is_coherent: bool = True
    coverage_gaps: List[dict] = field(default_factory=list)
    interface_issues: List[dict] = field(default_factory=list)
    communication_issues: List[dict] = field(default_factory=list)
    communication_map: Dict[str, dict] = field(default_factory=dict)

    @property
    def total_issues(self) -> int:
        return len(self.coverage_gaps) + len(self.interface_issues) + len(self.communication_issues)


# ── Surgical fix tool schema ─────────────────────────────────────────────────

_FIX_TOOL: dict = {
    "name": "submit_fix",
    "description": (
        "Submit surgical patches for specific broken functions/methods. "
        "Each patch replaces exactly one function. "
        "Set needs_full_regen=true if more than 30% of the code is broken — "
        "do NOT attempt to patch in that case."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "needs_full_regen": {
                "type": "boolean",
                "description": (
                    "True if the breakage is systemic (>30% of code is wrong, "
                    "wrong architecture, wrong imports throughout). "
                    "When true, patches must be empty — Qwen will regenerate."
                ),
            },
            "systemic_cause": {
                "type": "string",
                "description": (
                    "Root cause when needs_full_regen=true. "
                    "E.g. 'wrong base class used throughout', 'entire async model is wrong'."
                ),
            },
            "patches": {
                "type": "array",
                "description": "List of surgical function-level patches. Empty when needs_full_regen=true.",
                "items": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string", "description": "Relative file path."},
                        "function_name": {
                            "type": "string",
                            "description": "Exact name of the function or method to replace.",
                        },
                        "new_code": {
                            "type": "string",
                            "description": (
                                "Complete replacement for that function only — "
                                "including the def/async def line and full body. "
                                "Preserve original indentation level."
                            ),
                        },
                        "reason": {
                            "type": "string",
                            "description": "One sentence explaining what was wrong.",
                        },
                    },
                    "required": ["file", "function_name", "new_code"],
                },
            },
        },
        "required": ["needs_full_regen", "patches"],
    },
}


# ── Surgical patch merger ────────────────────────────────────────────────────

@dataclass
class Patch:
    file: str
    function_name: str
    new_code: str
    reason: str = ""


@dataclass
class FixResult:
    """Result of a fix_module_code call."""
    patched_files: Dict[str, str] = field(default_factory=dict)
    is_systemic: bool = False
    systemic_cause: str = ""
    patches_applied: List[str] = field(default_factory=list)


def _apply_patch(source: str, patch: Patch) -> tuple[str, bool]:
    """Replace a single function/method in source code.

    Finds the function by its def line (handles async def, indented methods).
    Returns (new_source, success).
    """
    fn = re.escape(patch.function_name)
    # Match 'def fname' or 'async def fname' at any indentation level
    pattern = re.compile(
        rf"^([ \t]*(?:async[ \t]+)?def[ \t]+{fn}[ \t]*\()",
        re.MULTILINE,
    )
    m = pattern.search(source)
    if not m:
        return source, False

    start = m.start()
    indent = len(m.group(1)) - len(m.group(1).lstrip())
    indent_str = " " * indent

    # Find where the function body ends: next line at same or lower indentation
    # that is not blank, after at least one body line
    lines = source[start:].splitlines(keepends=True)
    end_offset = len(source[start:])  # default: rest of file
    in_body = False
    for i, line in enumerate(lines[1:], 1):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue  # blank / comment — keep scanning
        line_indent = len(line) - len(line.lstrip())
        if line_indent <= indent and in_body:
            end_offset = sum(len(l) for l in lines[:i])
            break
        in_body = True

    # Normalize patch indentation to match original
    new_lines = patch.new_code.splitlines()
    if new_lines:
        patch_indent = len(new_lines[0]) - len(new_lines[0].lstrip())
        if patch_indent != indent:
            delta = indent - patch_indent
            new_lines = [
                indent_str + l[patch_indent:] if l.strip() else l
                for l in new_lines
            ]
    new_fn = "\n".join(new_lines) + "\n"

    new_source = source[:start] + new_fn + source[start + end_offset:]
    return new_source, True


def apply_patches(files: Dict[str, str], patches: List[Patch]) -> Dict[str, str]:
    """Apply a list of surgical patches to a file map. Returns only modified files."""
    modified: Dict[str, str] = {}
    for patch in patches:
        original = files.get(patch.file, "")
        updated, ok = _apply_patch(original, patch)
        if ok and updated != original:
            files = {**files, patch.file: updated}
            modified[patch.file] = updated
    return modified


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
    Uses structured tool_use output (Improvement D) when Gemini is available,
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
        client = None  # Anthropic SDK removed — Gemini driver handles this
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
            # Use Gemini driver to keep copilot-consultant working without Anthropic API
            system_block = (
                "Eres un revisor de código senior. "
                "Analiza el código y devuelve un JSON con 'message' (string) y 'changes' (array de objetos con filepath, original, suggested).\n\n"
                + REPLY_FORMAT
            )
            full_prompt = f"{SYSTEM}\n\n{prompt}\n\n{system_block}"
            dr = await self.ai.call(full_prompt, "", max_tokens=512, temperature=0.3)
            content = dr.content if hasattr(dr, 'content') else str(dr)
            result = _parse_json(content)
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
    # Pre-DEV: Contract coherence validation                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_struct_communication_map(master_contract: dict) -> dict:
        """Build a structural communication map from depends_on relationships.

        This is pure Python (no AI) — it derives who-calls-whom from the
        contract graph. Haiku enriches it with the actual methods used.
        """
        modules = master_contract.get("modules") or []
        # Index interfaces by module_id
        iface_by_module: dict[str, list] = {}
        for mod in modules:
            methods = []
            for iface in (mod.get("interfaces") or []):
                for m in (iface.get("methods") or []):
                    methods.append(m.get("name", ""))
            iface_by_module[mod["id"]] = [m for m in methods if m]

        # Who depends on whom
        consumers_of: dict[str, list] = {mod["id"]: [] for mod in modules}
        comm_map: dict[str, dict] = {}
        for mod in modules:
            mid = mod["id"]
            deps = mod.get("depends_on") or []
            comm_map[mid] = {
                "receives_from": [
                    {"module_id": dep, "methods_available": iface_by_module.get(dep, [])}
                    for dep in deps
                ],
                "exposes_to": [],
            }
            for dep in deps:
                if dep in consumers_of:
                    consumers_of[dep].append(mid)

        for mid, consumers in consumers_of.items():
            if mid in comm_map:
                comm_map[mid]["exposes_to"] = consumers

        return comm_map

    async def validate_contract_coherence(
        self,
        blueprint: dict,
        master_contract: dict,
    ) -> ContractValidationResult:
        """Pre-DEV validation: Haiku checks blueprint ↔ contract coherence + communication map.

        Returns ContractValidationResult with all issues and the enriched
        communication_map. The caller applies contract patches before development starts.
        """
        modules = master_contract.get("modules") or []
        funcs = blueprint.get("funcionalidades") or []

        # Structural map (Python, free)
        struct_map = self._build_struct_communication_map(master_contract)

        # Compact representations for the prompt
        blueprint_funcs = json.dumps(
            [{"id": f.get("id"), "nombre": f.get("nombre"), "descripcion": str(f.get("descripcion", ""))[:120]}
             for f in funcs],
            ensure_ascii=False, indent=2,
        )
        contract_modules = json.dumps(
            [
                {
                    "id": m["id"],
                    "purpose": str(m.get("purpose", ""))[:100],
                    "depends_on": m.get("depends_on", []),
                    "goal_ids": m.get("goal_ids", []),
                    "interfaces": [
                        {
                            "name": i.get("name"),
                            "methods": [
                                {"name": mt.get("name"), "params": mt.get("parameters", {}), "returns": mt.get("returns")}
                                for mt in (i.get("methods") or [])
                            ],
                        }
                        for i in (m.get("interfaces") or [])
                    ],
                }
                for m in modules
            ],
            ensure_ascii=False, indent=2,
        )
        struct_map_json = json.dumps(struct_map, ensure_ascii=False, indent=2)

        prompt = f"""\
Validá si el MasterContract es coherente con el Blueprint del usuario.

## Blueprint — funcionalidades pedidas
{blueprint_funcs[:2000]}

## MasterContract — módulos e interfaces
{contract_modules[:3000]}

## Mapa de comunicación estructural (depends_on)
{struct_map_json[:1500]}

Verificá:
1. COBERTURA: ¿cada funcionalidad del blueprint tiene al menos un método en alguna interfaz?
2. INTERFACES: ¿los métodos tienen sentido para el propósito del módulo? ¿Parámetros y retornos son correctos?
3. COMUNICACIÓN: ¿si módulo A depende de B, B expone los métodos que A necesita? ¿Hay dependencias faltantes?
4. MAPA DE COMUNICACIÓN: para cada módulo, qué métodos específicos usa de cada dependencia (enriches_from).

Sé estricto pero justo — solo reportá problemas reales que afecten la generación de código."""

        client = None  # Anthropic SDK removed — Gemini driver handles this
        if client:
            try:
                message = await client.messages.create(
                    model="gemini-3-flash-preview",
                    max_tokens=4096,
                    system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                    tools=[_CONTRACT_VALIDATION_TOOL],
                    tool_choice={"type": "any"},
                    messages=[{"role": "user", "content": prompt}],
                )
                for block in message.content:
                    if block.type == "tool_use" and block.name == "submit_contract_validation":
                        d = block.input
                        # Merge Haiku's enriched map with the structural base
                        comm_map = struct_map.copy()
                        for mid, data in (d.get("communication_map") or {}).items():
                            if mid in comm_map:
                                comm_map[mid].update(data)
                            else:
                                comm_map[mid] = data
                        return ContractValidationResult(
                            is_coherent=bool(d.get("is_coherent", True)),
                            coverage_gaps=d.get("coverage_gaps") or [],
                            interface_issues=d.get("interface_issues") or [],
                            communication_issues=d.get("communication_issues") or [],
                            communication_map=comm_map,
                        )
            except Exception:
                pass

        # Fallback: return structural map without semantic validation
        return ContractValidationResult(communication_map=struct_map)

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

    @staticmethod
    def _extract_module_contract(module_name: str, master_contract: Optional[dict]) -> str:
        """Extract the interface contract for a specific module from master_contract.

        Matches by module id or name (case-insensitive, ignores spaces/underscores).
        Returns a formatted string ready to inject into prompts, or empty string if not found.
        """
        if not master_contract:
            return ""
        modules = master_contract.get("modules") or []
        needle = module_name.lower().replace(" ", "_").replace("-", "_")

        matched = None
        for mod in modules:
            mod_id = str(mod.get("id", "")).lower().replace(" ", "_").replace("-", "_")
            mod_name = str(mod.get("name", "")).lower().replace(" ", "_").replace("-", "_")
            if needle in (mod_id, mod_name) or mod_id in needle or needle in mod_id:
                matched = mod
                break

        if not matched:
            return ""

        interfaces = matched.get("interfaces") or []
        if not interfaces:
            return ""

        lines = [f"CONTRATO DEL MÓDULO '{module_name}' (interfaces que DEBE implementar):"]
        for iface in interfaces:
            lines.append(f"\nInterfaz: {iface.get('name', '?')}")
            for method in iface.get("methods") or []:
                params = ", ".join(
                    f"{k}: {v}" for k, v in (method.get("parameters") or {}).items()
                )
                lines.append(
                    f"  - {method.get('name', '?')}({params}) → {method.get('returns', 'None')}"
                )
                if method.get("description"):
                    lines.append(f"    {method['description']}")
        return "\n".join(lines)

    async def review_module_code(
        self, module_name: str, files: dict, blueprint: dict,
        master_contract: Optional[dict] = None,
    ) -> Optional[Dict]:
        """Review actual code content against its MasterContract interfaces.

        A+B: stack + contract context sent cached (static per module).
        Variable part: the generated code content.
        D: result comes directly from tool_use — no parsing needed.
        """
        if not files:
            return None

        files_preview = "\n\n".join(
            f"### {path}\n```\n{content[:900]}\n```"
            for path, content in list(files.items())[:5]
        )
        contract_block = self._extract_module_contract(module_name, master_contract)

        cached_context = (
            f"STACK DEL PROYECTO:\n"
            f"{json.dumps(blueprint.get('stack_sugerido', {}), ensure_ascii=False)}\n\n"
            f"MÓDULO EN REVISIÓN: {module_name}"
            + (f"\n\n{contract_block}" if contract_block else "")
        )
        contract_instruction = (
            "\n¿El código implementa correctamente TODOS los métodos del contrato? "
            "¿Faltan firmas, parámetros incorrectos o tipos de retorno distintos al contrato?"
            if contract_block else ""
        )
        prompt = f"""\
CÓDIGO GENERADO:
{files_preview[:3000]}

¿El código es correcto y completo? ¿Hay bugs, imports faltantes, lógica incompleta o violaciones del stack?{contract_instruction}"""
        return await self._ask(prompt, cached_context=cached_context)

    async def fix_module_code(
        self, module_name: str, files: dict, review: dict, blueprint: dict,
        master_contract: Optional[dict] = None,
    ) -> FixResult:
        """Surgical function-level fix using the _FIX_TOOL schema.

        If Haiku signals needs_full_regen (>30% breakage), returns a FixResult
        with is_systemic=True and no patches — the caller escalates to Qwen regen.
        Otherwise applies patches only to the specific broken functions.
        """
        changes = review.get("changes") or []
        if not changes:
            return FixResult()

        contract_block = self._extract_module_contract(module_name, master_contract)
        changes_block = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(changes))
        files_block = "\n\n".join(
            f"### {path}\n```python\n{content}\n```"
            for path, content in list(files.items())[:6]
        )
        stack_json = json.dumps(blueprint.get("stack_sugerido", {}), ensure_ascii=False)
        contract_section = f"\n{contract_block}\n" if contract_block else ""

        prompt = f"""\
Módulo: {module_name}
Stack: {stack_json}
{contract_section}
PROBLEMAS ENCONTRADOS:
{changes_block}

CÓDIGO ACTUAL:
{files_block[:5000]}

Analizá el alcance del problema:
- Si los problemas afectan funciones aisladas (<30% del código) → listá patches quirúrgicos por función.
- Si el problema es sistémico (arquitectura incorrecta, modelo async equivocado, imports rotos en todo el archivo, >30% del código) → marcá needs_full_regen=true con la causa raíz.

NO intentes parchear si es sistémico."""

        client = None  # Anthropic SDK removed — Gemini driver handles this
        if client:
            try:
                message = await client.messages.create(
                    model="gemini-3-flash-preview",
                    max_tokens=4096,
                    system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                    tools=[_FIX_TOOL],
                    tool_choice={"type": "any"},
                    messages=[{"role": "user", "content": prompt}],
                )
                for block in message.content:
                    if block.type == "tool_use" and block.name == "submit_fix":
                        data = block.input
                        if data.get("needs_full_regen"):
                            return FixResult(
                                is_systemic=True,
                                systemic_cause=data.get("systemic_cause", "unspecified"),
                            )
                        raw_patches = [
                            Patch(
                                file=p["file"],
                                function_name=p["function_name"],
                                new_code=p["new_code"],
                                reason=p.get("reason", ""),
                            )
                            for p in (data.get("patches") or [])
                            if p.get("file") and p.get("function_name") and p.get("new_code")
                        ]
                        if not raw_patches:
                            return FixResult()
                        patched = apply_patches(dict(files), raw_patches)
                        return FixResult(
                            patched_files=patched,
                            patches_applied=[f"{p.file}::{p.function_name}" for p in raw_patches],
                        )
            except Exception:
                pass

        # Fallback: generic driver, JSON response (no tool_use)
        fallback_prompt = prompt + f"""

Respondé SOLO con JSON:
{{
  "needs_full_regen": false,
  "systemic_cause": "",
  "patches": [
    {{"file": "path.py", "function_name": "nombre_funcion", "new_code": "def nombre_funcion(...):\\n    ...", "reason": "por qué"}}
  ]
}}"""
        try:
            dr = await self.ai.call(SYSTEM, fallback_prompt, max_tokens=4096, temperature=0.15)
            m = re.search(r'\{[\s\S]*\}', dr.content)
            if m:
                data = json.loads(m.group(0))
                if data.get("needs_full_regen"):
                    return FixResult(is_systemic=True, systemic_cause=data.get("systemic_cause", ""))
                raw_patches = [
                    Patch(file=p["file"], function_name=p["function_name"],
                          new_code=p["new_code"], reason=p.get("reason", ""))
                    for p in (data.get("patches") or [])
                    if p.get("file") and p.get("function_name") and p.get("new_code")
                ]
                if raw_patches:
                    patched = apply_patches(dict(files), raw_patches)
                    return FixResult(patched_files=patched,
                                     patches_applied=[f"{p.file}::{p.function_name}" for p in raw_patches])
        except Exception:
            pass
        return FixResult()

    async def verify_module_code(
        self, module_name: str, files: dict, applied_change: str, blueprint: dict,
        master_contract: Optional[dict] = None,
    ) -> Optional[Dict]:
        """After Copilot/Qwen applied fixes: verify against code AND contract.

        A+B: static context (stack + contract) cached; variable parts sent fresh.
        """
        files_preview = "\n\n".join(
            f"### {path}\n```\n{content[:900]}\n```"
            for path, content in list(files.items())[:5]
        )
        contract_block = self._extract_module_contract(module_name, master_contract)

        cached_context = (
            f"STACK DEL PROYECTO:\n"
            f"{json.dumps(blueprint.get('stack_sugerido', {}), ensure_ascii=False)}\n\n"
            f"MÓDULO EN VERIFICACIÓN: {module_name}"
            + (f"\n\n{contract_block}" if contract_block else "")
        )
        contract_check = (
            " ¿Implementa el contrato completo (todos los métodos con las firmas correctas)?"
            if contract_block else ""
        )
        prompt = f"""\
CAMBIO APLICADO: {applied_change[:400]}

CÓDIGO RESULTANTE:
{files_preview[:2500]}

¿El cambio fue implementado correctamente? ¿Queda algún problema pendiente?{contract_check}"""
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
