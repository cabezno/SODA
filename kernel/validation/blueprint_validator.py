"""
BlueprintValidator: validates blueprint.json structure before architecture generation.

Checks:
  - Required fields: nombre_proyecto, descripcion, funcionalidades, stack_sugerido
  - Non-empty strings
  - funcionalidades is a non-empty list
  - stack_sugerido is a dict with at least 'backend' or 'frontend'
  - funcionalidades[].id: snake_case format (^[a-z0-9_]+$), unique across list
  - funcionalidades[].entidades_principales: non-empty array

Auto-fixes:
  - Strips whitespace from string fields
  - Converts funcionalidades string → single-element list
  - Generates missing id from nombre using slugification
  - Initializes missing entidades_principales to []
  - Normalizes tipo_interaccion to uppercase
"""

import copy
import re
from dataclasses import dataclass, field
from typing import Optional

from .architecture_validator import ValidationResult

_ID_RE = re.compile(r'^[a-z0-9_]+$')
_VALID_TIPO = {"API", "UI", "CRON"}


def _slugify(text: str) -> str:
    """Convert a human-readable name to a valid snake_case id."""
    slug = text.lower().strip()
    slug = re.sub(r'[^a-z0-9\s_]', '', slug)
    slug = re.sub(r'[\s]+', '_', slug)
    slug = re.sub(r'_+', '_', slug).strip('_')
    return slug or "func"


class BlueprintValidator:
    REQUIRED_FIELDS = ("nombre_proyecto", "descripcion", "funcionalidades")

    def validate(self, blueprint: dict) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if not isinstance(blueprint, dict):
            result.is_valid = False
            result.errors.append("El blueprint no es un objeto JSON válido.")
            result.fixed_blueprint = {}
            return result

        bp = copy.deepcopy(blueprint)

        for field_name in self.REQUIRED_FIELDS:
            if field_name not in bp:
                result.is_valid = False
                result.errors.append(f"Blueprint sin campo requerido '{field_name}'.")
            elif field_name == "funcionalidades":
                val = bp[field_name]
                if isinstance(val, str) and val.strip():
                    bp[field_name] = [val.strip()]
                    result.auto_fixes.append("'funcionalidades' era string — convertido a lista.")
                elif not isinstance(val, list) or not val:
                    result.warnings.append("'funcionalidades' está vacío — el scope puede quedar indefinido.")
            elif isinstance(bp[field_name], str):
                stripped = bp[field_name].strip()
                if not stripped:
                    result.warnings.append(f"'{field_name}' está vacío.")
                bp[field_name] = stripped

        stack = bp.get("stack_sugerido", {})
        if not isinstance(stack, dict):
            result.warnings.append("'stack_sugerido' no es un objeto — la selección de skills puede fallar.")
        elif not stack.get("backend") and not stack.get("frontend"):
            result.warnings.append("'stack_sugerido' no declara backend ni frontend.")

        if isinstance(bp.get("funcionalidades"), list):
            self._validate_funcionalidades(bp, result)

        result.fixed_architecture = bp
        return result

    def _validate_funcionalidades(self, bp: dict, result: ValidationResult) -> None:
        funcionalidades = bp["funcionalidades"]
        seen_ids: set[str] = set()

        for i, func in enumerate(funcionalidades):
            if not isinstance(func, dict):
                result.warnings.append(f"Funcionalidad #{i} no es un objeto — ignorada.")
                continue

            label = func.get("nombre") or func.get("id") or f"#{i}"

            # --- id field ---
            raw_id = func.get("id", "")
            if not raw_id:
                nombre = str(func.get("nombre", "")).strip()
                generated = f"func_{_slugify(nombre)}" if nombre else f"func_{i}"
                func["id"] = generated
                result.auto_fixes.append(
                    f"[{label}] 'id' faltante — generado automáticamente: '{generated}'."
                )
                raw_id = generated
            elif not _ID_RE.match(str(raw_id)):
                fixed = _slugify(str(raw_id))
                if not fixed.startswith("func"):
                    fixed = f"func_{fixed}"
                result.auto_fixes.append(
                    f"[{label}] 'id' inválido '{raw_id}' — normalizado a '{fixed}'."
                )
                func["id"] = fixed
                raw_id = fixed

            if raw_id in seen_ids:
                # Make unique by appending index
                unique = f"{raw_id}_{i}"
                result.warnings.append(
                    f"[{label}] 'id' duplicado '{raw_id}' — renombrado a '{unique}'."
                )
                func["id"] = unique
                raw_id = unique
            seen_ids.add(raw_id)

            # --- entidades_principales ---
            entidades = func.get("entidades_principales")
            if not isinstance(entidades, list):
                func["entidades_principales"] = []
                result.auto_fixes.append(
                    f"[{label}] 'entidades_principales' faltante — inicializado a []."
                )
            elif not entidades:
                result.warnings.append(
                    f"[{label}] 'entidades_principales' está vacío — el arquitecto tendrá menos contexto de dominio."
                )

            # --- tipo_interaccion ---
            tipo = str(func.get("tipo_interaccion", "")).strip().upper()
            if tipo not in _VALID_TIPO:
                func["tipo_interaccion"] = "API"
                result.auto_fixes.append(
                    f"[{label}] 'tipo_interaccion' inválido o faltante — asignado 'API' por defecto."
                )
            else:
                func["tipo_interaccion"] = tipo
