"""
N8nWorkflowGenerator — genera n8n_workflow.json a partir del proyecto SODA.

Lee los artefactos que SODA deja en workspace/:
  - soda_v2_tree.json  → contratos con títulos, skills, dependencias
  - port_map.json      → module_id → port (solo microservicios)
  - blueprint.json     → nombre y descripción del proyecto

Produce:
  - n8n_workflow.json  → workflow importable en n8n

El workflow contiene:
  - Manual Trigger (start)
  - Un nodo HTTP Request por cada servicio backend (GET /api/<resource>)
  - Un nodo HTTP Request por cada frontend (GET /)
  - Conexiones en fan-out desde el trigger

El generador es completamente determinístico — no usa LLM.
Si falla, el fallo es silencioso (el pipeline de SODA no se ve afectado).
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Optional


# ── Skills que producen endpoints HTTP ────────────────────────────────────────
_BACKEND_SKILLS = {
    "skill_fastapi", "skill_rest_api", "skill_nodejs", "skill_nestjs",
    "skill_golang", "skill_java_spring", "skill_csharp_dotnet",
    "skill_php_laravel", "skill_rust",
}
_FRONTEND_SKILLS = {
    "skill_react", "skill_vue", "skill_nextjs", "skill_angular",
    "skill_svelte", "skill_html",
}
_DATA_SKILLS = {
    "skill_sqlite", "skill_postgresql", "skill_mongodb",
}

# Default port when no port_map entry exists (monolith)
_DEFAULT_BACKEND_PORT = 8000
_DEFAULT_FRONTEND_PORT = 3000


def _make_id() -> str:
    return str(uuid.uuid4())


def _slugify(text: str) -> str:
    """Convert 'UserService' or 'user-service' to 'users'."""
    slug = re.sub(r"(?<=[a-z])(?=[A-Z])", "-", text)  # camelCase → kebab
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
    for suffix in ("service", "module", "handler", "controller", "router", "api"):
        slug = re.sub(rf"-?{suffix}$", "", slug)
    # Pluralize simple nouns (best-effort)
    if slug and not slug.endswith("s"):
        slug += "s"
    return slug or "resource"


def _infer_path(title: str) -> str:
    return f"/api/{_slugify(title)}"


def _http_node(
    name: str,
    url: str,
    method: str = "GET",
    x: int = 300,
    y: int = 300,
) -> dict:
    return {
        "id": _make_id(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [x, y],
        "parameters": {
            "method": method,
            "url": url,
            "options": {},
        },
    }


def _manual_trigger_node(x: int = 0, y: int = 300) -> dict:
    return {
        "id": _make_id(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [x, y],
        "parameters": {},
    }


def _no_op_node(name: str, x: int = 600, y: int = 300) -> dict:
    """Pass-through node — useful as a visual anchor/label."""
    return {
        "id": _make_id(),
        "name": name,
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [x, y],
        "parameters": {},
    }


class N8nWorkflowGenerator:
    """
    Reads SODA workspace artifacts and produces a n8n_workflow.json.
    """

    def __init__(self, notify_fn=None):
        self._notify = notify_fn or (lambda lvl, msg, *a, **kw: None)

    def generate(self, workspace: Path) -> bool:
        """
        Generate n8n_workflow.json in workspace.
        Returns True on success, False on any error.
        """
        try:
            tree, port_map, blueprint = self._load_artifacts(workspace)
            workflow = self._build_workflow(tree, port_map, blueprint)
            out = workspace / "n8n_workflow.json"
            out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False), encoding="utf-8")
            self._notify("SUCCESS", f"n8n workflow generado: {out.name} ({len(workflow['nodes'])} nodos)")
            return True
        except Exception as e:
            self._notify("LOG", f"[n8n] Generación omitida: {e}")
            return False

    # ── Artifact loading ──────────────────────────────────────────────────────

    def _load_artifacts(self, workspace: Path):
        tree_path = workspace / "soda_v2_tree.json"
        if not tree_path.exists():
            raise FileNotFoundError("soda_v2_tree.json not found")
        tree: dict = json.loads(tree_path.read_text(encoding="utf-8"))

        port_map: dict = {}
        pm_path = workspace / "port_map.json"
        if pm_path.exists():
            try:
                port_map = json.loads(pm_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        blueprint: dict = {}
        bp_path = workspace / "blueprint.json"
        if bp_path.exists():
            try:
                blueprint = json.loads(bp_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        return tree, port_map, blueprint

    # ── Workflow builder ──────────────────────────────────────────────────────

    def _build_workflow(self, tree: dict, port_map: dict, blueprint: dict) -> dict:
        project_name = blueprint.get("nombre") or blueprint.get("name") or "SODA Project"

        # Collect atomic contracts that produce HTTP endpoints
        backend_services: list[dict] = []
        frontend_services: list[dict] = []

        for cid, contract in tree.items():
            if not contract.get("is_atomic"):
                continue
            persona = contract.get("dynamic_persona") or {}
            skills = set(persona.get("required_skills") or [])

            if skills & _BACKEND_SKILLS:
                backend_services.append({
                    "id": cid,
                    "title": contract.get("title", cid),
                    "skills": skills,
                    "deps": contract.get("dependencies") or [],
                })
            elif skills & _FRONTEND_SKILLS:
                frontend_services.append({
                    "id": cid,
                    "title": contract.get("title", cid),
                    "skills": skills,
                })

        nodes: list[dict] = []
        connections: dict[str, Any] = {}

        # ── Manual Trigger ────────────────────────────────────────────────────
        trigger = _manual_trigger_node(x=0, y=300)
        nodes.append(trigger)
        trigger_name = trigger["name"]
        connections[trigger_name] = {"main": [[]]}

        # ── Backend service nodes ─────────────────────────────────────────────
        # Layout: column x=380, spaced 140px vertically
        y_cursor = 80
        for svc in backend_services:
            port = port_map.get(svc["id"], _DEFAULT_BACKEND_PORT)
            host = f"http://localhost:{port}"
            path = _infer_path(svc["title"])
            url = f"{host}{path}"

            node = _http_node(
                name=f"GET {_slugify(svc['title']).rstrip('s').capitalize() or svc['title']}",
                url=url,
                method="GET",
                x=380,
                y=y_cursor,
            )
            nodes.append(node)
            # Connect trigger → this node
            connections[trigger_name]["main"][0].append(
                {"node": node["name"], "type": "main", "index": 0}
            )
            y_cursor += 140

        # ── Frontend service nodes ─────────────────────────────────────────────
        for svc in frontend_services:
            port = port_map.get(svc["id"], _DEFAULT_FRONTEND_PORT)
            url = f"http://localhost:{port}/"

            node = _http_node(
                name=f"UI {svc['title']}",
                url=url,
                method="GET",
                x=380,
                y=y_cursor,
            )
            nodes.append(node)
            connections[trigger_name]["main"][0].append(
                {"node": node["name"], "type": "main", "index": 0}
            )
            y_cursor += 140

        # Fallback: if no services detected, add a placeholder health-check node
        if len(nodes) == 1:
            node = _http_node(
                name="Health Check",
                url=f"http://localhost:{_DEFAULT_BACKEND_PORT}/health",
                method="GET",
                x=380,
                y=300,
            )
            nodes.append(node)
            connections[trigger_name]["main"][0].append(
                {"node": node["name"], "type": "main", "index": 0}
            )

        return {
            "name": f"{project_name} — n8n Integration",
            "nodes": nodes,
            "connections": connections,
            "active": False,
            "settings": {"executionOrder": "v1"},
            "versionId": _make_id(),
            "meta": {
                "generatedBy": "SODA",
                "instanceId": _make_id(),
            },
        }
