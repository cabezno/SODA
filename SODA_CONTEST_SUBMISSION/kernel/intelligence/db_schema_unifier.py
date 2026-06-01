"""
DBSchemaUnifier — unifica el schema de base de datos de todos los módulos antes
de que el L4 Coder genere código.

Problema que resuelve:
    Dos módulos sin dependencia directa entre sí (ej. AUTH-001 y ORDERS-003)
    pueden generar tablas 'users' con columnas incompatibles porque el L4 Coder
    de cada uno trabaja en aislamiento.

Solución:
    Tras L2 (Decompose) y antes de L4 (Coder), hace UNA llamada a Gemini Flash
    con todos los contratos atómicos serializados y pide un schema canónico
    unificado. El resultado se guarda en db_schema_map.json y se inyecta en
    el prompt L4 de cada módulo con skills de DB.

Uso:
    unifier = DBSchemaUnifier(gemini_driver, notify_fn)
    await unifier.unify(contracts_pool, workspace_path)
    # Genera workspace/db_schema_map.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, Optional


_DB_SKILLS = {
    "skill_sqlite", "skill_postgres", "skill_postgresql", "skill_mysql",
    "skill_mongodb", "skill_redis", "skill_dynamodb", "skill_firestore",
    "skill_typeorm", "skill_prisma", "skill_sequelize", "skill_sqlalchemy",
    "skill_alembic", "skill_mongoose", "skill_drizzle",
}

_SYSTEM_PROMPT = """\
You are a database architect. Your job is to analyze a set of microservice contracts
and identify all shared data entities, then define a canonical unified schema.

Rules:
- Only include entities that appear in more than one module OR are central to the domain.
- Use simple SQL-style column types: UUID, VARCHAR(N), TEXT, INTEGER, BIGINT, BOOLEAN,
  TIMESTAMP, JSONB, DECIMAL(p,s).
- Always include id (UUID PK) and created_at (TIMESTAMP) in every table.
- Foreign keys: use the pattern {entity}_id (UUID FK → {entity}s.id).
- Respond ONLY with valid JSON. No markdown, no explanation.

Response format:
{
  "tables": {
    "table_name": {
      "columns": {
        "col_name": "TYPE [PK|FK|UNIQUE|NOT NULL|DEFAULT val]"
      },
      "owner_module": "CONTRACT_ID of the module that owns/creates this table",
      "shared_with": ["CONTRACT_ID", ...]
    }
  },
  "notes": "brief summary of decisions made"
}
"""


class DBSchemaUnifier:
    def __init__(
        self,
        gemini_driver,
        notify_fn: Optional[Callable[[str, str], None]] = None,
    ):
        self.gemini = gemini_driver
        self.notify = notify_fn or (lambda msg, lvl="LOG", *a, **kw: None)

    def _notify(self, msg: str, level: str = "LOG") -> None:
        try:
            self.notify(level, msg)
        except Exception:
            pass

    def _has_db_skills(self, contract) -> bool:
        skills = set(
            (getattr(getattr(contract, "dynamic_persona", None), "required_skills", None) or [])
        )
        return bool(skills & _DB_SKILLS)

    def _contracts_summary(self, contracts_pool: Dict[str, Any]) -> str:
        """Serialize contracts to a compact JSON for the LLM prompt."""
        summary = {}
        for cid, c in contracts_pool.items():
            if not getattr(c, "is_atomic", False):
                continue
            persona = getattr(c, "dynamic_persona", None) or {}
            iface = getattr(c, "interface", None)
            summary[cid] = {
                "title": getattr(c, "title", cid),
                "description": (getattr(c, "description", "") or "")[:300],
                "skills": list(getattr(persona, "required_skills", None) or []),
                "inputs": [
                    {"name": i.name, "type": i.abstract_type}
                    for i in (getattr(iface, "inputs_required", None) or [])
                ] if iface else [],
                "outputs": [
                    {"name": o.name, "type": o.abstract_type}
                    for o in (getattr(iface, "outputs_provided", None) or [])
                ] if iface else [],
            }
        return json.dumps(summary, ensure_ascii=False, indent=2)

    async def unify(
        self,
        contracts_pool: Dict[str, Any],
        workspace: Path,
    ) -> Optional[dict]:
        """
        Genera db_schema_map.json en el workspace.
        Retorna el schema dict o None si no hay módulos con DB o falla.
        """
        # Check if any module uses a DB skill
        db_modules = [c for c in contracts_pool.values() if self._has_db_skills(c)]
        if len(db_modules) < 1:
            self._notify("[DBSchemaUnifier] No hay módulos con skills de DB — omitiendo unificación.")
            return None

        self._notify(
            f"[DBSchemaUnifier] Unificando schema de {len(db_modules)} módulos con DB "
            f"(de {len(contracts_pool)} totales)...",
            "LOG"
        )

        contracts_json = self._contracts_summary(contracts_pool)

        user_msg = (
            f"Here are {len(contracts_pool)} microservice contracts. "
            "Identify all shared data entities and produce the canonical unified schema.\n\n"
            f"CONTRACTS:\n{contracts_json}"
        )

        try:
            resp = await self.gemini.call(
                system_prompt=_SYSTEM_PROMPT,
                user_message=user_msg,
                model=None,   # uses driver default (Flash)
                temperature=0.1,
            )

            raw = resp.content if resp else ""
            # Strip markdown fences if present
            raw = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
            raw = re.sub(r'\s*```$', '', raw.strip(), flags=re.MULTILINE)

            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if not m:
                self._notify("[DBSchemaUnifier] No se pudo extraer JSON del schema — omitiendo.", "WARNING")
                return None

            schema = json.loads(m.group(0))
            tables = schema.get("tables", {})

            if not tables:
                self._notify("[DBSchemaUnifier] Schema vacío — omitiendo.", "WARNING")
                return None

            output = {
                "tables": tables,
                "notes": schema.get("notes", ""),
                "module_count": len(db_modules),
            }

            out_path = workspace / "db_schema_map.json"
            out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
            self._notify(
                f"[DBSchemaUnifier] Schema canónico guardado: {len(tables)} tabla(s) — {out_path.name}",
                "LOG"
            )
            return output

        except Exception as e:
            self._notify(f"[DBSchemaUnifier] Error generando schema: {e} — continuando sin unificación.", "WARNING")
            return None


def load_schema_for_module(workspace: Path, contract) -> str:
    """
    Carga el db_schema_map.json y retorna solo las tablas relevantes
    para el módulo dado, formateadas para inyección en el prompt L4.

    Si el módulo no tiene skills de DB o no hay schema, retorna "".
    """
    schema_path = workspace / "db_schema_map.json"
    if not schema_path.exists():
        return ""

    skills = set(
        (getattr(getattr(contract, "dynamic_persona", None), "required_skills", None) or [])
    )
    if not (skills & _DB_SKILLS):
        return ""

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        tables = schema.get("tables", {})
        if not tables:
            return ""

        cid = getattr(contract, "contract_id", "")
        # Include tables owned by OR shared with this module, plus all if module has general DB skill
        relevant = {
            name: info for name, info in tables.items()
            if info.get("owner_module") == cid
            or cid in (info.get("shared_with") or [])
        }
        # If no specific match, include all (module has DB skill but no specific tables assigned)
        if not relevant:
            relevant = tables

        lines = ["## CANONICAL DATABASE SCHEMA — YOU MUST USE THESE EXACT TABLE/COLUMN NAMES"]
        lines.append("Do NOT invent alternative table or column names. Use this schema exactly.\n")
        for tname, tinfo in relevant.items():
            lines.append(f"Table: {tname}")
            for col, col_type in (tinfo.get("columns") or {}).items():
                lines.append(f"  {col}: {col_type}")
            owner = tinfo.get("owner_module", "")
            shared = tinfo.get("shared_with", [])
            if owner:
                lines.append(f"  [owner: {owner}, shared with: {', '.join(shared) if shared else 'none'}]")
            lines.append("")

        return "\n".join(lines)

    except Exception:
        return ""
