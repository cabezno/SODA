"""Architect — generates and refines MasterContracts (Arquitecto v2).

Uses Claude with model selection based on project complexity:
- simple  → claude-haiku-4-5-20251001
- medium  → claude-sonnet-4-6
- complex → claude-opus-4-7
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from kernel.drivers.claude_driver import ClaudeDriver
from kernel.intelligence.complexity_classifier import (
    MODEL_ASSIGNMENT_BY_COMPLEXITY,
    MODEL_CALL_CONFIG,
    ComplexityLevel,
)
from kernel.intelligence.contract_schemas import MasterContract

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "claude"
_GEMINI_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "gemini"

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
        topology: dict | None = None,
        active_skills: list | None = None,
        active_profile: dict | None = None,
        goal_tree: dict | None = None,
        attempt_number: int = 1,
    ) -> MasterContract:
        """Generate the initial MasterContract.

        topology is the output of Gemini's global_architect (topology.json).
        When provided, Claude inherits the physical module structure (IDs,
        archivos_principales, depende_de_ids) and fills in typed interfaces.
        """
        model = MODEL_ASSIGNMENT_BY_COMPLEXITY[complexity.value]
        system_prompt = self._load_prompt(_COMPLEXITY_PROMPT_MAP[complexity])
        user_message = self._build_generation_prompt(
            blueprint=blueprint,
            skills=active_skills or [],
            profile=active_profile or {},
            goal_tree=goal_tree or {},
            topology=topology or {},
        )

        response = await self.driver.call(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            **MODEL_CALL_CONFIG[model],
            metadata={
                "phase": "master_contract",
                "action": "generate",
                "complexity": complexity.value,
                "attempt_number": attempt_number,
            },
        )

        if response.error_code:
            raise RuntimeError(
                f"Architect generation failed [{response.error_code}]: {response.content}"
            )

        contract_data = self._parse_json(response.content)
        self._dump_raw(contract_data, label=f"generate_attempt{attempt_number}_{complexity.value}")
        contract_data = self._normalize_contract_data(contract_data)
        contract_data["complexity_level"] = complexity.value
        contract_data["model_used"] = model

        try:
            contract = MasterContract(**contract_data)
        except Exception as exc:
            from pydantic import ValidationError
            if isinstance(exc, ValidationError):
                fields = "\n".join(
                    f"  {'.'.join(str(l) for l in e['loc'])}: {e['msg']}"
                    for e in exc.errors()[:12]
                )
                raise RuntimeError(
                    f"MasterContract schema validation failed ({len(exc.errors())} error(s)):\n{fields}"
                ) from exc
            raise

        if topology:
            contract = self._apply_topology_autofix(contract, topology)
        return contract

    async def refine_contract(
        self,
        current_contract: MasterContract,
        audit_feedback: object,  # AuditReport — avoid circular import
        complexity: ComplexityLevel,
        attempt_number: int = 2,
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
            metadata={
                "phase": "master_contract",
                "action": "refine",
                "complexity": complexity.value,
                "attempt_number": attempt_number,
            },
        )

        if response.error_code:
            raise RuntimeError(
                f"Architect refinement failed [{response.error_code}]: {response.content}"
            )

        contract_data = self._parse_json(response.content)
        self._dump_raw(contract_data, label=f"refine_attempt{attempt_number}_{complexity.value}")
        contract_data = self._normalize_contract_data(contract_data)
        contract_data["complexity_level"] = complexity.value
        contract_data["model_used"] = model

        try:
            return MasterContract(**contract_data)
        except Exception as exc:
            from pydantic import ValidationError
            if isinstance(exc, ValidationError):
                fields = "\n".join(
                    f"  {'.'.join(str(l) for l in e['loc'])}: {e['msg']}"
                    for e in exc.errors()[:12]
                )
                raise RuntimeError(
                    f"MasterContract schema validation failed ({len(exc.errors())} error(s)):\n{fields}"
                ) from exc
            raise

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_generation_prompt(
        self,
        blueprint: dict,
        skills: list,
        profile: dict,
        goal_tree: dict,
        topology: dict | None = None,
    ) -> str:
        blueprint_goal_ids = self._extract_goal_ids_from_blueprint(blueprint)

        if goal_tree:
            goal_section = (
                "```json\n" + json.dumps(goal_tree, indent=2, ensure_ascii=False) + "\n```"
            )
        elif blueprint_goal_ids:
            goal_section = (
                "Los goal_ids OBLIGATORIOS para este proyecto son los siguientes "
                "(provienen directamente del blueprint — no los cambies ni inventes otros):\n"
                + "\n".join(f"- `{gid}`" for gid in blueprint_goal_ids)
            )
        else:
            goal_section = (
                "(árbol de objetivos aún no construido — generá goal_ids descriptivos basados en el blueprint)"
            )

        # Build topology section — canonical module structure from Gemini
        if topology and topology.get("modulos"):
            topo_lines = ["La siguiente topología fue definida por el agente de infraestructura.",
                          "DEBES usar exactamente estos IDs de módulos y estas dependencias.",
                          "Tu trabajo es añadir interfaces tipadas, data_types, error_types y extension_points.",
                          "NO cambies los IDs, NO cambies depende_de_ids, NO inventes módulos adicionales.\n"]
            for mod in topology["modulos"]:
                topo_lines.append(
                    f"- id: `{mod['id']}` | archivos: {mod.get('archivos_principales', [])} "
                    f"| depende_de: {mod.get('depende_de_ids', [])}"
                )
                topo_lines.append(f"  responsabilidad: {mod.get('responsabilidad', '')}")
            topology_section = "\n".join(topo_lines)
        else:
            topology_section = "(topología no disponible — generá los módulos basándote en el blueprint)"

        return f"""Generá el contrato maestro para este proyecto.

## Blueprint del proyecto
```json
{json.dumps(blueprint, indent=2, ensure_ascii=False)}
```

## Topología de módulos (estructura física — NO modificar IDs ni dependencias)
{topology_section}

## Árbol de objetivos / Goal IDs
{goal_section}

## Skills activas
{self._format_skills(skills)}

## Perfil activo
{self._format_profile(profile)}

## Instrucciones
Generá un contrato maestro siguiendo el schema MasterContract.
Para cada módulo de la topología debés:
- Usar el mismo `id` exacto (snake_case, tal cual aparece arriba)
- Copiar `archivos_principales` de la topología al campo del módulo
- Usar los mismos `depende_de_ids` como `depends_on`
- Agregar al menos una `interface` con métodos tipados (parámetros y retornos reales)

Además asegurate de incluir en el contrato global:
- Al menos 3 puntos de extensión (tipos: middleware_slot, metadata_field, event_channel)
- Al menos 3 tipos de error estandarizados
- Todos los módulos con al menos un goal_id de la lista provista
- Convenciones de nombres consistentes (ver system prompt)

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

    @staticmethod
    def _apply_topology_autofix(contract: MasterContract, topology: dict) -> MasterContract:
        """Force topology's physical structure onto the contract (last-resort safety net).

        After Claude's refinement loop, topology.json is the ground truth for:
          - module IDs
          - archivos_principales
          - depends_on

        Claude's typed interfaces, data_types, error_types are preserved as-is.
        This prevents a broken depends_on from crashing the Kahn topological sort.
        """
        topo_by_id = {
            m["id"]: m
            for m in topology.get("modulos", [])
            if isinstance(m, dict) and m.get("id")
        }
        if not topo_by_id:
            return contract

        for mod in contract.modules:
            topo_mod = topo_by_id.get(mod.id)
            if not topo_mod:
                continue
            # Override physical fields with topology's authoritative values
            mod.depends_on = topo_mod.get("depende_de_ids", [])
            if topo_mod.get("archivos_principales"):
                mod.archivos_principales = topo_mod["archivos_principales"]

        return contract

    @staticmethod
    def _extract_goal_ids_from_blueprint(blueprint: dict) -> list[str]:
        """Return the list of func IDs from blueprint funcionalidades (new schema).

        Returns an empty list if funcionalidades use the old schema (no 'id' field).
        """
        ids = []
        for func in blueprint.get("funcionalidades", []):
            if isinstance(func, dict) and func.get("id"):
                ids.append(func["id"])
        return ids

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
    def _dump_raw(data: dict, label: str = "raw") -> None:
        """Persist raw parsed JSON to debug/ for post-mortem analysis."""
        debug_dir = Path(__file__).resolve().parent.parent.parent / "debug"
        debug_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = debug_dir / f"architect_{label}_{ts}.json"
        try:
            out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  [Architect] raw dump -> {out.name}")
        except Exception as e:
            print(f"  [Architect] dump failed: {e}")

    @staticmethod
    def _parse_json(content: str) -> dict:
        """Extract JSON from response using multiple strategies.

        1. Direct parse (Claude returned bare JSON).
        2. Fence extraction (```json ... ``` or ``` ... ```).
        3. Regex extraction of the outermost { ... } block (preamble before JSON).
        """
        text = content.strip()

        # Strategy 1: bare JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 2: fenced block
        fence_match = re.search(r"```(?:json)?\s*\n([\s\S]*?)```", text)
        if fence_match:
            try:
                return json.loads(fence_match.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 3: outermost { ... } block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

        raise json.JSONDecodeError("No valid JSON found in Architect response", text, 0)

    # Placeholder items used when Claude generates fewer than the schema minimum.
    # They satisfy Pydantic's min_length=3 while keeping the contract structurally valid.
    _PLACEHOLDER_EXTENSION_POINTS: list[dict] = [
        {
            "id": "ep_middleware_slot",
            "type": "middleware_slot",
            "location": "application layer",
            "contract": "Async callable receiving (request, next) context dict",
            "description": "Reserved middleware slot for cross-cutting concerns such as logging or auth",
            "example_use_case": "Request logging, authentication middleware, rate limiting",
        },
        {
            "id": "ep_event_channel",
            "type": "event_channel",
            "location": "domain events",
            "contract": "Typed event payload conforming to the declared DataType schema",
            "description": "Reserved event channel for domain event emission and subscription",
            "example_use_case": "Domain events, audit trail, notification dispatch",
        },
        {
            "id": "ep_metadata_field",
            "type": "metadata_field",
            "location": "domain entities",
            "contract": "Additional metadata field conforming to declared DataType, serializable to JSON",
            "description": "Reserved metadata field for domain entity enrichment without schema migration",
            "example_use_case": "Custom tags, audit metadata, feature flags per entity",
        },
    ]

    _PLACEHOLDER_ERROR_TYPES: list[dict] = [
        {
            "name": "SystemError",
            "code": "SYSTEM_ERROR",
            "message_template": "An unexpected system error occurred: {detail}",
            "recoverable": False,
            "retry_strategy": None,
            "http_status": 500,
        },
        {
            "name": "ValidationError",
            "code": "VALIDATION_ERROR",
            "message_template": "Validation failed on field '{field}': {reason}",
            "recoverable": True,
            "retry_strategy": None,
            "http_status": 422,
        },
        {
            "name": "NotFoundError",
            "code": "NOT_FOUND",
            "message_template": "{resource} with id '{id}' was not found",
            "recoverable": True,
            "retry_strategy": None,
            "http_status": 404,
        },
    ]

    # Layer keywords used to infer the architectural layer when a module omits it.
    _LAYER_KEYWORDS: dict[str, list[str]] = {
        "presentation": ["route", "router", "controller", "api", "endpoint", "view",
                         "handler", "rest", "graphql", "websocket", "ui", "frontend"],
        "application":  ["service", "usecase", "use_case", "orchestrat", "workflow",
                         "manager", "coordinator", "command", "query", "app"],
        "infrastructure": ["repo", "repository", "cache", "db", "database", "storage",
                            "queue", "broker", "email", "smtp", "s3", "redis", "postgres",
                            "mongo", "firebase", "external", "integration", "adapter"],
        "domain":       ["model", "entity", "value", "aggregate", "domain",
                         "business", "rule", "policy", "event", "spec"],
    }

    @classmethod
    def _infer_layer(cls, mod: dict) -> str:
        """Guess the architectural layer from module id/name/purpose."""
        text = " ".join([
            mod.get("id", ""),
            mod.get("name", ""),
            mod.get("purpose", ""),
        ]).lower()
        for layer, keywords in cls._LAYER_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return layer
        return "application"  # safe default

    @staticmethod
    def _placeholder_method(interface_name: str) -> dict:
        """Minimal valid InterfaceMethod to satisfy min_length=1 on methods."""
        return {
            "name": "get_status",
            "parameters": {},
            "returns": "dict",
            "raises": [],
            "description": f"Returns the current status of {interface_name}.",
            "example_usage": f"instance.get_status()",
            "is_async": False,
        }

    @classmethod
    def _normalize_contract_data(cls, data: dict) -> dict:
        """Fill in minimum required fields before Pydantic validation.

        Claude sometimes generates fewer than the minimum 3 extension_points or
        error_types. This step adds generic placeholders so Pydantic validation
        passes. The CompletenessValidator then flags any remaining gaps as errors
        that feed back into the refinement loop.
        """
        # extension_points: schema requires min_length=3
        eps: list = data.get("extension_points") or []
        existing_ep_ids = {ep.get("id") for ep in eps if isinstance(ep, dict)}
        for placeholder in cls._PLACEHOLDER_EXTENSION_POINTS:
            if len(eps) >= 3:
                break
            if placeholder["id"] not in existing_ep_ids:
                eps.append(placeholder)
        data["extension_points"] = eps

        # error_types: schema requires min_length=3
        ets: list = data.get("error_types") or []
        existing_et_names = {et.get("name") for et in ets if isinstance(et, dict)}
        for placeholder in cls._PLACEHOLDER_ERROR_TYPES:
            if len(ets) >= 3:
                break
            if placeholder["name"] not in existing_et_names:
                ets.append(placeholder)
        data["error_types"] = ets

        # Module IDs must be snake_case lowercase alphanumeric
        for mod in data.get("modules") or []:
            if not isinstance(mod, dict):
                continue
            mid = mod.get("id", "")
            if mid:
                normalized = "".join(c if c.isalnum() or c == "_" else "_" for c in mid.lower())
                mod["id"] = normalized.strip("_") or "module"
            if not mod.get("goal_ids"):
                mod["goal_ids"] = ["general_objective"]

            # layer is required — infer from module name/purpose if missing
            if not mod.get("layer"):
                mod["layer"] = cls._infer_layer(mod)

            # interfaces[].methods requires min_length=1 — inject placeholder if empty
            for iface in mod.get("interfaces") or []:
                if not isinstance(iface, dict):
                    continue
                methods = iface.get("methods")
                if not methods:
                    iface["methods"] = [cls._placeholder_method(iface.get("name", "Interface"))]

        # data_types[].fields values must be strings (not dicts/lists)
        for dt in data.get("data_types") or []:
            if not isinstance(dt, dict):
                continue
            fields = dt.get("fields")
            if isinstance(fields, dict):
                dt["fields"] = {k: str(v) if not isinstance(v, str) else v
                                for k, v in fields.items()}
            # values for enums must be list[str]
            values = dt.get("values")
            if isinstance(values, list):
                dt["values"] = [str(v) for v in values]

        # EventChannel names must contain a dot (e.g. "user.created")
        for ch in data.get("event_channels") or []:
            if isinstance(ch, dict) and "." not in ch.get("name", ""):
                ch["name"] = ch.get("name", "event") + ".event"

        # http_status in error_types must be None or 400-599
        for et in data.get("error_types") or []:
            if not isinstance(et, dict):
                continue
            hs = et.get("http_status")
            if hs is None:
                continue
            try:
                hs = int(hs)
            except (TypeError, ValueError):
                et["http_status"] = None
                continue
            if hs < 400 or hs > 599:
                et["http_status"] = None  # drop invalid value rather than guess

        return data


class GeminiArchitect:
    """Fallback Architect that uses GeminiDriver to generate MasterContracts.

    Used when all Claude attempts fail. Reuses the same schema prompts,
    normalization logic, and JSON extraction as the primary Architect.
    """

    GEMINI_MAX_TOKENS = 8192

    def __init__(self, gemini_driver):
        self.driver = gemini_driver

    # Shared formatting helpers (copied from Architect — kept in sync)
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
            return "Perfil genérico"
        name = profile.get("name", "Desconocido")
        desc = profile.get("description", "")
        return f"{name}: {desc}" if desc else name

    async def generate_master_contract(
        self,
        blueprint: dict,
        complexity: ComplexityLevel,
        topology: dict | None = None,
        active_skills: list | None = None,
        active_profile: dict | None = None,
        goal_tree: dict | None = None,
        attempt_number: int = 1,
    ) -> MasterContract:
        prompt_file = _COMPLEXITY_PROMPT_MAP[complexity]
        system_prompt = self._load_prompt(prompt_file)
        user_message = Architect._build_generation_prompt(
            self,
            blueprint=blueprint,
            skills=active_skills or [],
            profile=active_profile or {},
            goal_tree=goal_tree or {},
            topology=topology,
        )

        response = await self.driver.call(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=self.GEMINI_MAX_TOKENS,
            metadata={
                "phase": "master_contract",
                "action": "generate_gemini_fallback",
                "complexity": complexity.value,
                "attempt_number": attempt_number,
            },
        )

        if response.error_code:
            raise RuntimeError(
                f"Gemini Architect generation failed [{response.error_code}]: {response.content}"
            )

        contract_data = Architect._parse_json(response.content)
        Architect._dump_raw(contract_data, label=f"gemini_generate_attempt{attempt_number}_{complexity.value}")
        contract_data = Architect._normalize_contract_data(contract_data)
        contract_data["complexity_level"] = complexity.value
        contract_data["model_used"] = f"gemini-fallback/{getattr(self.driver, 'active_model', 'gemini')}"

        try:
            return MasterContract(**contract_data)
        except Exception as exc:
            from pydantic import ValidationError
            if isinstance(exc, ValidationError):
                fields = "\n".join(
                    f"  {'.'.join(str(l) for l in e['loc'])}: {e['msg']}"
                    for e in exc.errors()[:12]
                )
                raise RuntimeError(
                    f"MasterContract schema validation failed (Gemini, {len(exc.errors())} error(s)):\n{fields}"
                ) from exc
            raise

    async def refine_contract(
        self,
        current_contract: MasterContract,
        audit_feedback: object,
        complexity: ComplexityLevel,
        attempt_number: int = 2,
    ) -> MasterContract:
        system_prompt = self._load_prompt("architect_refinement.md")
        feedback_text = audit_feedback.to_architect_feedback()
        user_message = Architect._build_refinement_prompt(
            self,  # type: ignore[arg-type]
            current_contract=current_contract,
            feedback=feedback_text,
        )

        response = await self.driver.call(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=self.GEMINI_MAX_TOKENS,
            metadata={
                "phase": "master_contract",
                "action": "refine_gemini_fallback",
                "complexity": complexity.value,
                "attempt_number": attempt_number,
            },
        )

        if response.error_code:
            raise RuntimeError(
                f"Gemini Architect refinement failed [{response.error_code}]: {response.content}"
            )

        contract_data = Architect._parse_json(response.content)
        Architect._dump_raw(contract_data, label=f"gemini_refine_attempt{attempt_number}_{complexity.value}")
        contract_data = Architect._normalize_contract_data(contract_data)
        contract_data["complexity_level"] = complexity.value
        contract_data["model_used"] = f"gemini-fallback/{getattr(self.driver, 'active_model', 'gemini')}"

        try:
            return MasterContract(**contract_data)
        except Exception as exc:
            from pydantic import ValidationError
            if isinstance(exc, ValidationError):
                fields = "\n".join(
                    f"  {'.'.join(str(l) for l in e['loc'])}: {e['msg']}"
                    for e in exc.errors()[:12]
                )
                raise RuntimeError(
                    f"MasterContract schema validation failed (Gemini refinement, {len(exc.errors())} error(s)):\n{fields}"
                ) from exc
            raise

    @staticmethod
    def _load_prompt(filename: str) -> str:
        path = _PROMPTS_DIR / filename
        return path.read_text(encoding="utf-8")
