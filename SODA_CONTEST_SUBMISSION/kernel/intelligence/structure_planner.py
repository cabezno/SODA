"""
StructurePlanner (L3.5) — define la estructura de directorios, convenciones de
imports y el entry point del proyecto ANTES de que L4 genere código.

Problema que resuelve:
    Sin estructura predefinida, cada módulo inventa sus propias rutas de import.
    ROOT-001 genera `from ../database/db import session` y ROOT-003 genera
    `from ../../shared/db import get_db`. Ambos referencian el mismo objeto
    pero con rutas incompatibles — el proyecto no resuelve los imports.

Solución:
    Una sola llamada LLM (Gemini Flash) tras L3 genera project_structure.json:
    - Un directorio canónico por módulo atómico
    - Archivos compartidos (db, middleware, types, config)
    - El entry point que registra todos los routers en orden topológico
    - El import alias (@/ para TS, o ruta relativa para Python)

    Este JSON se inyecta en TODOS los prompts L4 para que cada módulo
    use las mismas rutas de import.

Uso:
    planner = StructurePlanner(gemini_driver, notify_fn)
    structure = await planner.plan(contracts_pool, lang, workspace)
    # Genera workspace/project_structure.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT_TS = """\
You are a senior software architect. Given a set of microservice/module contracts,
define the complete project directory structure and import conventions.

Rules:
- Use a clean src/ layout. Each module gets its own directory under src/.
- Shared resources (db connection, middleware, config, types) live in src/shared/.
- The entry point (src/index.ts or src/main.ts) imports and registers all module routers.
- Use "@/" as the TypeScript path alias for the src/ root (already in tsconfig paths).
- Every module directory MUST contain: router.ts, controller.ts, service.ts (and optionally model.ts, dto.ts).
- List files in topological order (dependencies before dependents).

Respond ONLY with valid JSON. No markdown fences, no explanation.

Response format:
{
  "entry_point": "src/index.ts",
  "import_alias": "@",
  "shared": {
    "database": "src/shared/db.ts",
    "middleware": "src/shared/middleware.ts",
    "types": "src/shared/types.ts",
    "config": "src/shared/config.ts"
  },
  "modules": {
    "CONTRACT_ID": {
      "dir": "src/module-name",
      "router_file": "src/module-name/router.ts",
      "router_export": "moduleNameRouter",
      "controller_file": "src/module-name/controller.ts",
      "service_file": "src/module-name/service.ts",
      "model_file": "src/module-name/model.ts"
    }
  },
  "entry_point_template": "complete content of src/index.ts that imports and mounts all routers"
}
"""

_SYSTEM_PROMPT_PYTHON = """\
You are a senior software architect. Given a set of module contracts,
define the complete Python project directory structure and import conventions.

Rules:
- Use a src/ layout with one package per module (directory with __init__.py).
- Shared resources (db, middleware, config, models base) live in src/shared/.
- The entry point (src/main.py) creates the FastAPI app and includes all routers.
- Use absolute imports from the project root (e.g. from src.auth.router import router).
- Every module package MUST contain: router.py, service.py (and optionally models.py, schemas.py).
- List modules in topological order (dependencies before dependents).

Respond ONLY with valid JSON. No markdown fences, no explanation.

Response format:
{
  "entry_point": "src/main.py",
  "import_style": "absolute",
  "shared": {
    "database": "src/shared/database.py",
    "middleware": "src/shared/middleware.py",
    "config": "src/shared/config.py",
    "base_model": "src/shared/base.py"
  },
  "modules": {
    "CONTRACT_ID": {
      "package": "src/module_name",
      "router_file": "src/module_name/router.py",
      "router_var": "router",
      "service_file": "src/module_name/service.py",
      "models_file": "src/module_name/models.py",
      "schemas_file": "src/module_name/schemas.py",
      "prefix": "/module-name"
    }
  },
  "entry_point_template": "complete content of src/main.py that creates FastAPI app and includes all routers"
}
"""

_SYSTEM_PROMPT_GENERIC = """\
You are a senior software architect. Define the project structure for a multi-module
application. Rules: clean layout, one directory per module, shared utilities in
a shared/ directory, one entry point that wires everything together.
Respond ONLY with valid JSON.
"""


_SYSTEM_PROMPT_POLYGLOT = """\
You are a senior software architect. Given a set of module contracts for a POLYGLOT project,
define the complete project directory structure and import conventions.

Rules:
- For Python modules: use a src/ layout with one package per module (directory with __init__.py). Use .py extensions.
- For TypeScript/Frontend modules: use a clean src/ layout. Use .ts or .tsx extensions.
- Shared resources (db, middleware, config) live in src/shared/. Use the appropriate extension for the primary backend language.
- The entry point (e.g. src/main.py or src/index.ts) should be the main gateway.
- Use absolute imports from project root for Python. Use "@/" alias for TypeScript.
- List files in topological order (dependencies before dependents).

Respond ONLY with valid JSON. No markdown fences, no explanation.

Response format:
{
  "entry_point": "src/main.py",
  "import_alias": "@",
  "shared": {
    "database": "src/shared/database.py",
    "middleware": "src/shared/middleware.py",
    "config": "src/shared/config.py"
  },
  "modules": {
    "CONTRACT_ID": {
      "dir": "src/module-name",
      "router_file": "src/module-name/router.py",  // Use correct extension based on module skills!
      "router_var": "router",
      "service_file": "src/module_name/service.py",
      "prefix": "/module-name"
    }
  },
  "entry_point_template": "complete content of entry point"
}
"""


def _pick_prompt(lang: str) -> str:
    l = lang.lower()
    if "+" in l or "mixed" in l or "polyglot" in l:
        return _SYSTEM_PROMPT_POLYGLOT
    if any(k in l for k in ("typescript", "javascript", "node", "next", "nest", "react", "express")):
        return _SYSTEM_PROMPT_TS
    if any(k in l for k in ("python", "fastapi", "flask", "django")):
        return _SYSTEM_PROMPT_PYTHON
    return _SYSTEM_PROMPT_GENERIC


# ── Helpers ───────────────────────────────────────────────────────────────────

def _contracts_summary(contracts_pool: Dict[str, Any], lang: str) -> str:
    """Compact JSON summary of atomic contracts for the LLM prompt."""
    modules = {}
    from kernel.utils.language_detector import detect_language
    for cid, c in contracts_pool.items():
        if not getattr(c, "is_atomic", False):
            continue
        persona = getattr(c, "dynamic_persona", None) or {}
        iface = getattr(c, "interface", None)
        outputs = []
        if iface:
            outputs = [
                getattr(o, "name", "") for o in (getattr(iface, "outputs_provided", None) or [])
            ]
        
        # En polyglot, detectamos el lenguaje sugerido para este módulo específico
        skills = list(getattr(persona, "required_skills", None) or [])
        suggested_lang = detect_language(skills)

        modules[cid] = {
            "title": getattr(c, "title", cid),
            "description": (getattr(c, "description", "") or "")[:120],
            "skills": skills[:4],
            "suggested_language": suggested_lang,
            "depends_on": list(getattr(c, "dependencies", None) or []),
            "outputs": outputs[:5],
        }
    return json.dumps({"language": lang, "modules": modules}, ensure_ascii=False, indent=2)


def _fallback_structure(contracts_pool: Dict[str, Any], lang: str) -> dict:
    """
    Genera una estructura determinista mínima sin LLM.
    Usado cuando la llamada LLM falla o retorna JSON inválido.
    """
    from kernel.utils.language_detector import detect_language, language_to_extension
    
    is_python = "python" in lang.lower() or "fastapi" in lang.lower()
    is_mixed = "+" in lang or "mixed" in lang
    
    entry = "src/main.py" if is_python else "src/index.ts"
    alias = "" if is_python else "@"

    shared: dict = {}
    if is_python:
        shared = {
            "database": "src/shared/database.py",
            "middleware": "src/shared/middleware.py",
            "config": "src/shared/config.py",
        }
    else:
        shared = {
            "database": "src/shared/db.ts",
            "middleware": "src/shared/middleware.ts",
            "config": "src/shared/config.ts",
            "types": "src/shared/types.ts",
        }

    modules: dict = {}
    for cid, c in contracts_pool.items():
        if not getattr(c, "is_atomic", False):
            continue
        
        skills = getattr(getattr(c, "dynamic_persona", None), "required_skills", []) or []
        m_lang = detect_language(skills) if is_mixed else lang
        m_ext = language_to_extension(m_lang)
        
        # Convert CID to directory name: ROOT-001-AUTH → auth
        parts = cid.lower().replace("root-", "").split("-")
        dir_name = parts[-1] if len(parts) > 1 else parts[0]
        dir_name = re.sub(r'^\d+$', 'module', dir_name)

        if m_lang == "python":
            pkg = f"src/{dir_name}"
            modules[cid] = {
                "package": pkg,
                "router_file": f"{pkg}/router.py",
                "router_var": "router",
                "service_file": f"{pkg}/service.py",
                "models_file": f"{pkg}/models.py",
                "schemas_file": f"{pkg}/schemas.py",
                "prefix": f"/{dir_name}",
            }
        elif m_lang in ("typescript", "javascript"):
            sdir = f"src/{dir_name}"
            router_name = f"{dir_name}Router"
            modules[cid] = {
                "dir": sdir,
                "router_file": f"{sdir}/router{m_ext}",
                "router_export": router_name,
                "controller_file": f"{sdir}/controller{m_ext}",
                "service_file": f"{sdir}/service{m_ext}",
                "model_file": f"{sdir}/model{m_ext}",
            }
        else:
            # Default generic structure
            sdir = f"src/{dir_name}"
            modules[cid] = {
                "dir": sdir,
                "main_file": f"{sdir}/main{m_ext}",
                "prefix": f"/{dir_name}",
            }

    return {
        "entry_point": entry,
        "import_alias": alias,
        "shared": shared,
        "modules": modules,
        "entry_point_template": "",
        "_generated_by": "fallback",
    }


# ── Main class ────────────────────────────────────────────────────────────────

class StructurePlanner:
    """
    L3.5 — Planning layer between TechLead (L3) and Coder (L4).
    Generates project_structure.json once, before any code is written.
    """

    def __init__(
        self,
        gemini_driver,
        notify_fn: Optional[Callable] = None,
    ):
        self.gemini = gemini_driver
        self.notify = notify_fn or (lambda msg, lvl="LOG", *a, **kw: None)

    def _notify(self, msg: str, level: str = "LOG") -> None:
        try:
            self.notify(level, msg)
        except Exception:
            pass

    async def plan(
        self,
        contracts_pool: Dict[str, Any],
        lang: str,
        workspace: Path,
    ) -> dict:
        """
        Genera project_structure.json en workspace.
        Retorna el structure dict (nunca falla — usa fallback determinista si LLM falla).
        """
        atomic_count = sum(1 for c in contracts_pool.values() if getattr(c, "is_atomic", False))
        if atomic_count == 0:
            return {}

        self._notify(
            f"[StructurePlanner] Planificando estructura para {atomic_count} módulos ({lang})...",
            "LOG"
        )

        structure: Optional[dict] = None

        try:
            contracts_json = _contracts_summary(contracts_pool, lang)
            system_prompt = _pick_prompt(lang)

            resp = await self.gemini.call(
                system_prompt=system_prompt,
                user_message=(
                    f"Define the project structure for these {atomic_count} modules.\n\n"
                    f"{contracts_json}"
                ),
                model=None,
                temperature=0.1,
            )

            if resp and resp.content:
                raw = resp.content.strip()
                raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
                raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    structure = json.loads(m.group(0))
                    # Basic validation
                    if "modules" not in structure or not structure["modules"]:
                        structure = None

        except Exception as e:
            self._notify(f"[StructurePlanner] LLM call failed: {e} — using fallback.", "WARNING")

        if not structure:
            self._notify("[StructurePlanner] Usando estructura determinista (fallback).", "WARNING")
            structure = _fallback_structure(contracts_pool, lang)

        # Ensure every atomic contract has an entry in modules (fill missing with fallback)
        fallback = _fallback_structure(contracts_pool, lang)
        for cid in fallback["modules"]:
            if cid not in structure.get("modules", {}):
                structure.setdefault("modules", {})[cid] = fallback["modules"][cid]

        # Save to workspace
        out_path = workspace / "project_structure.json"
        out_path.write_text(json.dumps(structure, indent=2, ensure_ascii=False), encoding="utf-8")

        self._notify(
            f"[StructurePlanner] Estructura guardada: {len(structure.get('modules', {}))} módulos "
            f"— entry point: {structure.get('entry_point', '?')}",
            "LOG"
        )
        return structure


# ── Injection helper ──────────────────────────────────────────────────────────

def load_structure_context_for_module(
    workspace: Path,
    contract_id: str,
    is_small_model: bool = False,
) -> str:
    """
    Carga project_structure.json y retorna el contexto formateado para
    inyectar en el prompt L4 del módulo dado.

    Incluye:
    - El directorio y archivos del módulo actual
    - Los archivos compartidos (db, middleware, config)
    - El entry point
    - Los paths de los módulos de los que depende (para imports correctos)

    Retorna "" si no hay project_structure.json.
    """
    path = workspace / "project_structure.json"
    if not path.exists():
        return ""

    try:
        structure = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    modules = structure.get("modules", {})
    own = modules.get(contract_id)
    if not own:
        return ""

    alias = structure.get("import_alias", "")
    shared = structure.get("shared", {})
    entry = structure.get("entry_point", "")
    entry_template = structure.get("entry_point_template", "")

    lines = ["## PROJECT STRUCTURE — MANDATORY"]
    lines.append("Use EXACTLY these file paths. Do NOT invent alternative paths or directory names.\n")

    # Own module files
    lines.append(f"YOUR MODULE ({contract_id}):")
    for key, val in own.items():
        if isinstance(val, str) and ("file" in key or "dir" == key or "package" == key):
            lines.append(f"  {key}: {val}")

    # Import alias
    if alias:
        lines.append(f"\nImport alias: '{alias}/' maps to 'src/'")
        lines.append(f"  Example: import {{ db }} from '{alias}/shared/db'")
    else:
        lines.append("\nUse absolute imports from project root.")
        lines.append("  Example: from src.shared.database import get_db")

    # Shared files
    if shared:
        lines.append("\nSHARED FILES (import from these — do NOT recreate them):")
        for name, filepath in shared.items():
            lines.append(f"  {name}: {filepath}")

    # Entry point info
    if entry:
        lines.append(f"\nEntry point: {entry}")
        if entry_template and not is_small_model:
            # Include entry point template for non-small models
            preview = entry_template[:600]
            if len(entry_template) > 600:
                preview += "\n... (truncated)"
            lines.append(f"Entry point template:\n```\n{preview}\n```")

    # Dependency module paths (so imports are correct)
    dep_lines = []
    for dep_id, dep_info in modules.items():
        if dep_id == contract_id:
            continue
        router = dep_info.get("router_file") or dep_info.get("router_file", "")
        export = dep_info.get("router_export") or dep_info.get("router_var", "router")
        title = dep_id
        if router:
            dep_lines.append(f"  {dep_id}: {router} (export: {export})")
    if dep_lines and not is_small_model:
        lines.append("\nOTHER MODULES (for cross-module imports):")
        lines.extend(dep_lines[:8])

    return "\n".join(lines) + "\n"
