"""
SkillDiscoveryAgent — Fase 2 del plan de evolución SODA.

Analiza el contrato raíz (y sus sub-contratos) antes de la descomposición
y enriquece cada nodo con las skills apropiadas de forma determinística
(sin llamada a IA). Una vez que las skills internas están cargadas,
puede extenderse para buscar en skills/community/ o en un registry externo.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

import yaml


# ── Señales de detección determinísticas ──────────────────────────────────────

_PERSISTENCE_SIGNALS = frozenset({
    # English
    "database", "db", "sqlite", "postgres", "mysql", "mongodb",
    "crud", "persist", "store", "repository", "entity", "record",
    "users", "products", "orders", "inventory", "table", "schema",
    "migration", "orm", "sqlalchemy", "prisma",
    # Spanish
    "base de datos", "guardar", "almacenar", "tabla", "registro",
    "usuarios", "productos", "pedidos", "inventario", "persistir",
    "repositorio", "entidad", "esquema", "migracion", "migración",
})

_INTEGRATION_SIGNALS = frozenset({
    # English
    "external", "api client", "http client", "fetch", "axios", "httpx",
    "webhook", "microservice", "gateway", "adapter", "rest client",
    "third-party", "integration", "service call",
    # Spanish
    "externo", "cliente api", "cliente http", "integración", "integracion",
    "microservicio", "webhook", "pasarela", "adaptador", "servicio externo",
})

_AUTH_SIGNALS = frozenset({
    # English
    "auth", "authentication", "login", "logout", "jwt", "token",
    "session", "oauth", "password", "credential", "bearer",
    # Spanish
    "autenticación", "autenticacion", "inicio de sesión", "inicio de sesion",
    "contraseña", "credencial", "sesión", "sesion", "acceso", "registro de usuario",
})

_FRONTEND_SIGNALS = frozenset({
    # English — only specific web-UI terms, NOT generic "ui" or "interface"
    "react", "vue", "angular", "svelte", "nextjs", "html", "css",
    "frontend", "dashboard", "tailwind",
    "web page", "web ui", "web interface",
    # Spanish — only web-specific terms
    "interfaz web", "pagina web", "página web",
    "diseño visual web", "formulario web", "frontend",
})

_DOCKER_SIGNALS = frozenset({
    # English / Spanish (same terms widely used)
    "docker", "container", "compose", "deployment", "containerize",
    "contenedor", "despliegue", "contenedorizacion",
})

_FASTAPI_SIGNALS = frozenset({
    "fastapi", "uvicorn", "pydantic", "starlette",
    "fast api", "api rest python", "python api", "backend python",
    "python backend", "python server", "python web",
})

_NESTJS_SIGNALS = frozenset({
    "nestjs", "nest.js", "nest js", "@nestjs",
    "nestjs api", "nestjs backend", "nestjs module",
    "nestjs controller", "nestjs service",
})

_SKILL_SIGNAL_MAP: list[tuple[frozenset, str]] = [
    (_PERSISTENCE_SIGNALS, "skill_repository"),
    (_INTEGRATION_SIGNALS, "skill_integration"),
    (_AUTH_SIGNALS,         "skill_jwt_auth"),
    (_FRONTEND_SIGNALS,     "skill_react"),
    (_DOCKER_SIGNALS,       "skill_docker"),
    (_FASTAPI_SIGNALS,      "skill_fastapi"),
    (_NESTJS_SIGNALS,       "skill_nestjs"),
]


class SkillDiscoveryAgent:
    """
    Determina qué skills deben asignarse a cada módulo basándose en
    señales léxicas en el contrato — sin llamadas a IA.

    Uso típico (en SodaRecursiveEngine.decompose_tree):
        agent = SkillDiscoveryAgent()
        enriched = agent.discover(root_contract, contracts_pool)
        # enriched: {contract_id: [skill_names]}
    """

    def __init__(self, skills_dir: Optional[Path] = None):
        self._skills_dir = skills_dir or (
            Path(__file__).resolve().parent.parent.parent / "skills"
        )
        self._available: Optional[frozenset] = None

    # ── Public API ────────────────────────────────────────────────────────────

    # Skills que definen un stack nativo compilado — incompatibles con web frameworks
    _NATIVE_SKILLS = frozenset({"skill_cpp_cmake", "skill_rust"})
    # Skills que NO deben asignarse a módulos de stack nativo
    _WEB_SKILLS = frozenset({
        "skill_react", "skill_vue", "skill_angular", "skill_nextjs", "skill_nestjs",
        "skill_nodejs", "skill_fastapi", "skill_flask", "skill_django",
        "skill_typescript", "skill_html", "skill_css",
    })

    def discover(
        self,
        contracts: Dict[str, object],  # Dict[str, SodaContract]
    ) -> Dict[str, List[str]]:
        """
        Retorna un mapa {contract_id: [skill_names]} con las skills
        detectadas para cada contrato atómico.
        Skills incompatibles con el stack nativo del contrato son filtradas.
        """
        available = self._load_available_skill_names()
        result: Dict[str, List[str]] = {}

        for cid, contract in contracts.items():
            text = self._extract_text(contract)
            detected = self._detect_skills(text, available)

            # Conservar skills ya asignadas por el Arquitecto Génesis
            existing = list(getattr(
                getattr(contract, "dynamic_persona", None),
                "required_skills",
                []
            ) or [])

            # Si el contrato ya tiene skills nativas, bloquear detección de web skills
            existing_set = set(existing)
            if existing_set & self._NATIVE_SKILLS:
                detected = [s for s in detected if s not in self._WEB_SKILLS]

            merged = existing + [s for s in detected if s not in existing_set]
            result[cid] = merged

        return result

    def discover_for_contract(
        self,
        contract: object,
        extra_text: str = "",
    ) -> List[str]:
        """
        Variante de un solo contrato — útil para enriquecer el contrato
        raíz antes de la descomposición.
        """
        available = self._load_available_skill_names()
        text = self._extract_text(contract) + " " + extra_text
        existing = list(getattr(
            getattr(contract, "dynamic_persona", None),
            "required_skills",
            []
        ) or [])
        detected = self._detect_skills(text, available)
        return existing + [s for s in detected if s not in existing]

    # ── Internals ─────────────────────────────────────────────────────────────

    def _load_available_skill_names(self) -> frozenset:
        if self._available is not None:
            return self._available
        names: set[str] = set()
        for p in self._skills_dir.glob("*/*/manifest.yaml"):
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8"))
                if data and "name" in data:
                    names.add(data["name"])
            except Exception:
                pass
        self._available = frozenset(names)
        return self._available

    @staticmethod
    def _extract_text(contract: object) -> str:
        parts: list[str] = []
        for attr in ("title", "description", "contract_id"):
            val = getattr(contract, attr, None)
            if val:
                parts.append(str(val))
        # Inputs / outputs names and types
        iface = getattr(contract, "interface", None)
        if iface:
            for item in list(getattr(iface, "inputs_required", []) or []) + \
                        list(getattr(iface, "outputs_provided", []) or []):
                parts.append(getattr(item, "name", "") + " " + getattr(item, "type", ""))
        return " ".join(parts).lower()

    @staticmethod
    def _detect_skills(text: str, available: frozenset) -> List[str]:
        detected: list[str] = []
        # Tokenise loosely: split on spaces and punctuation
        tokens = set(re.split(r"[\s,.\-_/]+", text))
        for signals, skill_name in _SKILL_SIGNAL_MAP:
            if skill_name not in available:
                continue
            # Match if any signal word appears as substring of the full text
            if any(sig in text for sig in signals):
                detected.append(skill_name)
        return detected
