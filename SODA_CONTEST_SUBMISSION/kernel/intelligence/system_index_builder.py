"""
SystemIndexBuilder — genera un índice comprimido del sistema completo para
inyectar en el prompt L4 de cada módulo y dar coherencia global.

Problema que resuelve:
    En proyectos de 30+ módulos, el L4 Coder solo ve su contrato y sus
    dependencias directas. Sin visión del sistema completo, un módulo de pagos
    puede inventar una entidad 'User' con campo 'user_email' cuando el módulo
    de autenticación ya definió 'email'.

Solución:
    Tras L2 (Decompose), genera system_index.json — un resumen comprimido del
    sistema completo (~200 tokens). Se inyecta al inicio de cada prompt L4.

    El resumen del sistema se genera con UNA llamada LLM (Gemini Flash).
    El dict de módulos se genera de forma determinista desde los contratos
    (sin LLM) para minimizar costo y latencia.

Uso:
    builder = SystemIndexBuilder(gemini_driver, notify_fn)
    await builder.build(contracts_pool, workspace_path)
    # Genera workspace/system_index.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, Optional


_SYSTEM_PROMPT = """\
You are a technical writer. Given a set of microservice contracts, write a single
concise paragraph (max 2 sentences, max 50 words) that summarizes the entire system:
what it does, how many services, and the main tech stack.

Respond with ONLY the paragraph text. No JSON, no markdown, no title.
"""


class SystemIndexBuilder:
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

    def _build_modules_dict(self, contracts_pool: Dict[str, Any]) -> dict:
        """
        Construye el dict de módulos de forma determinista (sin LLM).
        Solo incluye contratos atómicos.
        """
        modules = {}
        for cid, c in contracts_pool.items():
            if not getattr(c, "is_atomic", False):
                continue
            persona = getattr(c, "dynamic_persona", None) or {}
            iface = getattr(c, "interface", None)

            exposes = []
            if iface:
                for o in (getattr(iface, "outputs_provided", None) or []):
                    name = getattr(o, "name", "")
                    abstract_type = getattr(o, "abstract_type", "")
                    if name:
                        exposes.append(f"{name}: {abstract_type}" if abstract_type else name)

            skills = list(getattr(persona, "required_skills", None) or [])
            tech = _skills_to_tech(skills)

            modules[cid] = {
                "title": getattr(c, "title", cid),
                "role": (getattr(c, "description", "") or "")[:120],
                "tech": tech,
                "exposes": exposes[:5],  # cap to 5 outputs to stay compact
                "depends_on": list(getattr(c, "dependencies", None) or []),
            }
        return modules

    async def build(
        self,
        contracts_pool: Dict[str, Any],
        workspace: Path,
    ) -> Optional[dict]:
        """
        Genera system_index.json en el workspace.
        Retorna el index dict o None si falla.
        """
        atomic_count = sum(1 for c in contracts_pool.values() if getattr(c, "is_atomic", False))
        if atomic_count == 0:
            return None

        self._notify(
            f"[SystemIndex] Construyendo índice del sistema ({atomic_count} módulos atómicos)...",
            "LOG"
        )

        # Build modules dict deterministically (no LLM)
        modules_dict = self._build_modules_dict(contracts_pool)

        # Generate system summary with one LLM call
        summary = ""
        try:
            # Compact representation for the summary prompt
            compact = {
                cid: {"title": m["title"], "role": m["role"][:80], "tech": m["tech"]}
                for cid, m in modules_dict.items()
            }
            resp = await self.gemini.call(
                system_prompt=_SYSTEM_PROMPT,
                user_message=f"CONTRACTS:\n{json.dumps(compact, ensure_ascii=False, indent=2)}",
                model=None,
                temperature=0.2,
            )
            if resp and resp.content:
                summary = resp.content.strip()[:300]
        except Exception as e:
            self._notify(f"[SystemIndex] No se pudo generar resumen LLM: {e} — usando fallback.", "WARNING")
            root = next((c for c in contracts_pool.values() if getattr(c, "level", 99) == 0), None)
            summary = (
                getattr(root, "description", "") or
                f"Sistema con {atomic_count} módulos."
            )[:200]

        output = {
            "summary": summary,
            "total_modules": atomic_count,
            "modules": modules_dict,
        }

        out_path = workspace / "system_index.json"
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        self._notify(
            f"[SystemIndex] Índice guardado: {atomic_count} módulos — {out_path.name}",
            "LOG"
        )
        return output


def _skills_to_tech(skills: list) -> str:
    """Map skill list to a human-readable tech string."""
    mapping = {
        "skill_nextjs": "Next.js",
        "skill_react": "React",
        "skill_vue": "Vue",
        "skill_svelte": "Svelte",
        "skill_angular": "Angular",
        "skill_nestjs": "NestJS",
        "skill_nodejs": "Node.js",
        "skill_fastapi": "FastAPI",
        "skill_flask": "Flask",
        "skill_django": "Django",
        "skill_go": "Go",
        "skill_rust": "Rust",
        "skill_typescript": "TypeScript",
        "skill_python": "Python",
        "skill_sqlite": "SQLite",
        "skill_postgres": "PostgreSQL",
        "skill_mysql": "MySQL",
        "skill_mongodb": "MongoDB",
        "skill_redis": "Redis",
        "skill_prisma": "Prisma",
        "skill_typeorm": "TypeORM",
        "skill_sqlalchemy": "SQLAlchemy",
        "skill_jwt_auth": "JWT Auth",
        "skill_rest_api": "REST API",
        "skill_graphql": "GraphQL",
        "skill_docker": "Docker",
        "skill_kubernetes": "Kubernetes",
    }
    found = [mapping[s] for s in skills if s in mapping]
    return " + ".join(found[:4]) if found else "general"


def load_system_context_for_module(
    workspace: Path,
    contract_id: str,
    is_small_model: bool = False,
) -> str:
    """
    Carga system_index.json y retorna el contexto comprimido para inyectar
    en el prompt L4 del módulo dado.

    Para modelos pequeños (Qwen) usa solo el summary (slim version).
    Para modelos cloud incluye también el rol del módulo actual.

    Retorna "" si no hay system_index.json.
    """
    index_path = workspace / "system_index.json"
    if not index_path.exists():
        return ""

    try:
        idx = json.loads(index_path.read_text(encoding="utf-8"))
        summary = idx.get("summary", "")
        modules = idx.get("modules", {})
        own_module = modules.get(contract_id, {})
        own_role = own_module.get("role", "")
        own_tech = own_module.get("tech", "")

        if is_small_model:
            # Slim: just summary (~50 words) to preserve Qwen context budget
            if summary:
                return f"## SYSTEM CONTEXT\n{summary}\n"
            return ""

        # Full: summary + own role + brief list of other modules
        lines = ["## SYSTEM CONTEXT"]
        if summary:
            lines.append(summary)
        if own_role:
            lines.append(f"\nYour module ({contract_id}): {own_role}")
            if own_tech:
                lines.append(f"Tech: {own_tech}")

        # Brief list of other modules (title + tech only) to show the system landscape
        others = [
            f"  - {cid}: {m.get('title', '')} [{m.get('tech', '')}]"
            for cid, m in modules.items()
            if cid != contract_id
        ]
        if others:
            lines.append("\nOther services in this system:")
            lines.extend(others[:10])  # max 10 to stay compact
            if len(others) > 10:
                lines.append(f"  ... and {len(others) - 10} more")

        return "\n".join(lines) + "\n"

    except Exception:
        return ""
