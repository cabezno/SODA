import json
from pathlib import Path
from typing import Dict, Any

def _is_microservices_tree(v2_tree: Dict[str, Any]) -> bool:
    """True if the root contract declares a microservices/serverless architecture."""
    root = v2_tree.get("ROOT-000") or next(
        (c for c in v2_tree.values() if c.get("level", -1) == 0), None
    )
    if not root:
        return False
    for c in root.get("inherited_constraints") or []:
        if any(k in str(c).lower() for k in ("microservice", "serverless", "micro-service")):
            return True
    return "microservice" in str(root.get("description", "")).lower()


def _assign_service_ports(v2_tree: Dict[str, Any]) -> Dict[str, int]:
    """
    Assign a unique host port to each atomic service.
    Frontend services (nextjs, react, vue) get port 3000.
    Backend services start at 3001 in alphabetical order.
    Returns {contract_id: port}.
    """
    atomic = sorted(
        [cid for cid, c in v2_tree.items() if c.get("is_atomic", False)],
    )
    port_map: Dict[str, int] = {}
    frontend_port = 3000
    backend_port = 3001
    frontend_skills = {"skill_nextjs", "skill_react", "skill_vue", "skill_svelte", "skill_angular"}

    for cid in atomic:
        c = v2_tree[cid]
        skills = set(
            (c.get("dynamic_persona") or {}).get("required_skills") or []
        )
        if skills & frontend_skills:
            port_map[cid] = frontend_port
            frontend_port += 1  # allow multiple frontends: 3000, 3001 … but bump backend start
            backend_port = max(backend_port, frontend_port)
        else:
            port_map[cid] = backend_port
            backend_port += 1

    return port_map


def generate_legacy_artifacts(v2_tree: Dict[str, Any], project_skills: list, workspace_dir: str):
    """
    Adapter to generate V1 artifacts (blueprint.json, topology.json) from V2 data.
    Ensures compatibility with DockerSandbox, BootAgent, and the UI.
    """
    workspace = Path(workspace_dir)

    # --- Detect microservices architecture ---
    is_microservices = _is_microservices_tree(v2_tree)

    # --- Generate blueprint.json ---
    # Extraer skills de TODOS los contratos del árbol (project_skills puede estar vacío)
    all_skills: list[str] = [str(s) for s in (project_skills or [])]
    for contract_data in v2_tree.values():
        persona   = contract_data.get("dynamic_persona") or {}
        required  = persona.get("required_skills") or []
        all_skills.extend(str(s) for s in required)

    skills_str = " ".join(all_skills).lower()

    if is_microservices:
        # Microservices: BootAgent uses docker-compose, not individual stack commands
        backend_stack = "Microservices (docker-compose)"
        run_cmd       = "docker-compose up --build"
        install_cmd   = ""
        port_map      = _assign_service_ports(v2_tree)
    else:
        port_map = {}
        backend_stack = "Python"
        run_cmd   = "python source/main.py"
        install_cmd = "pip install -r requirements.txt"

        # Compiled native apps — must be checked FIRST before any web stack
        # run_cmd/install_cmd left empty: BootAgent detects cmake/cargo from source files
        if "skill_cpp_cmake" in skills_str or "cpp_cmake" in skills_str:
            backend_stack = "C++ (CMake)"
            run_cmd = ""
            install_cmd = ""
        elif "skill_rust" in skills_str:
            backend_stack = "Rust"
            run_cmd = "cargo run"
            install_cmd = "cargo build --release"
        # Orden importante: nextjs/nestjs antes de typescript genérico
        elif "nextjs" in skills_str or "skill_nextjs" in skills_str:
            backend_stack = "Next.js"
            run_cmd     = "npm run dev"
            install_cmd = "npm install --legacy-peer-deps"
        elif "nestjs" in skills_str or "skill_nestjs" in skills_str:
            backend_stack = "NestJS (TypeScript)"
            run_cmd     = "npm run start:dev"
            install_cmd = "npm install --legacy-peer-deps"
        elif "typescript" in skills_str or "nodejs" in skills_str or "skill_nodejs" in skills_str:
            backend_stack = "Node.js (TypeScript)"
            run_cmd     = "npm start"
            install_cmd = "npm install --legacy-peer-deps"
        elif "golang" in skills_str or "skill_go" in skills_str:
            backend_stack = "Go"
            run_cmd     = "go run source/main.go"
            install_cmd = "go mod tidy"

    blueprint = {
        "tipo_proyecto": "V2 Microservices Application" if is_microservices else "V2 Compiled Application",
        "is_microservices": is_microservices,
        "stack_sugerido": {
            "backend": backend_stack,
            "frontend": "Determined by skills",
            "database": "Determined by skills"
        },
        "comando_ejecucion": run_cmd,
        "comando_instalacion": install_cmd,
        "v2_skills": project_skills,
        "service_ports": port_map,  # {contract_id: port} — used by BootAgent and UI
    }

    (workspace / "blueprint.json").write_text(json.dumps(blueprint, indent=2), encoding="utf-8")

    # --- Generate topology.json ---
    # Extract atomic nodes to simulate V1 modules
    legacy_modules = []
    for cid, contract in v2_tree.items():
        if contract.get("is_atomic", False):
            legacy_modules.append({
                "id": cid,
                "nombre": contract.get("title", cid),
                "descripcion": contract.get("description", ""),
                "archivos_principales": [f"{cid.lower()}/src/main" if is_microservices else f"{cid}.source"],
                "depende_de_ids": contract.get("dependencies", []),
                "port": port_map.get(cid),
            })

    topology = {"modulos": legacy_modules}
    (workspace / "topology.json").write_text(json.dumps(topology, indent=2), encoding="utf-8")
    # architecture.json includes `stack` dict so BootAgent knows how to install/run the project
    architecture = {
        "stack": {
            "backend": backend_stack,
            "frontend": backend_stack
        },
        "is_microservices": is_microservices,
        **topology
    }
    (workspace / "architecture.json").write_text(json.dumps(architecture, indent=2), encoding="utf-8")

