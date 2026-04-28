from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ServiceSpec:
    name: str
    image: str = ""
    build: str = ""        # relative path to Dockerfile context
    ports: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    command: str = ""
    volumes: list[str] = field(default_factory=list)

    def to_compose_dict(self) -> dict:
        svc: dict = {}
        if self.image:
            svc["image"] = self.image
        elif self.build:
            svc["build"] = self.build
        if self.ports:
            svc["ports"] = self.ports
        if self.env:
            svc["environment"] = self.env
        if self.depends_on:
            svc["depends_on"] = self.depends_on
        if self.command:
            svc["command"] = self.command
        if self.volumes:
            svc["volumes"] = self.volumes
        return svc


@dataclass
class ComposeResult:
    generated: bool
    path: str
    services: list[str]
    error: str = ""

    def to_dict(self) -> dict:
        return {"generated": self.generated, "path": self.path, "services": self.services, "error": self.error}


class ServiceOrchestrator:
    """
    Detects multi-service projects and generates docker-compose.yml.

    Heuristics for "needs compose":
    - architecture has modules with distinct stacks (e.g. python backend + node frontend)
    - blueprint specifies a database service (postgres, mysql, mongodb, redis)
    - more than one run_command separated by '&' or ';'
    """

    DB_IMAGES = {
        "postgres": ("postgres:16-alpine", "5432"),
        "postgresql": ("postgres:16-alpine", "5432"),
        "mysql": ("mysql:8", "3306"),
        "mongodb": ("mongo:7", "27017"),
        "mongo": ("mongo:7", "27017"),
        "redis": ("redis:7-alpine", "6379"),
    }

    def needs_compose(self, blueprint: dict, architecture: dict) -> bool:
        stack = json.dumps(blueprint.get("stack_sugerido", {})).lower()
        for db in self.DB_IMAGES:
            if db in stack:
                return True
        run_cmd = blueprint.get("comando_ejecucion", "")
        if run_cmd and ("&&" in run_cmd or ";" in run_cmd or "&" in run_cmd):
            return True
        return False

    def _detect_db_services(self, blueprint: dict) -> list[ServiceSpec]:
        stack = json.dumps(blueprint.get("stack_sugerido", {})).lower()
        services = []
        for db_key, (image, port) in self.DB_IMAGES.items():
            if db_key in stack:
                env: dict[str, str] = {}
                if "postgres" in db_key:
                    env = {"POSTGRES_USER": "soda", "POSTGRES_PASSWORD": "soda", "POSTGRES_DB": "app"}
                elif "mysql" in db_key:
                    env = {"MYSQL_ROOT_PASSWORD": "soda", "MYSQL_DATABASE": "app"}
                services.append(ServiceSpec(
                    name=db_key,
                    image=image,
                    ports=[f"{port}:{port}"],
                    env=env,
                    volumes=[f"{db_key}_data:/var/lib/{db_key}/data" if "mongo" not in db_key else f"{db_key}_data:/data/db"],
                ))
                break  # only primary DB
        return services

    def _detect_app_services(self, blueprint: dict, source_dir: Path) -> list[ServiceSpec]:
        run_cmd = (blueprint.get("comando_ejecucion") or "").strip()
        install_cmd = (blueprint.get("comando_instalacion") or "").strip()
        services = []

        if not run_cmd:
            return services

        app_svc = ServiceSpec(
            name="app",
            build=".",
            command=run_cmd,
            ports=["8000:8000"],
        )
        services.append(app_svc)
        return services

    def generate_compose(
        self,
        blueprint: dict,
        architecture: dict,
        source_dir: Path,
    ) -> ComposeResult:
        """Generate docker-compose.yml in source_dir if multi-service project."""
        db_services = self._detect_db_services(blueprint)
        app_services = self._detect_app_services(blueprint, source_dir)
        all_services = db_services + app_services

        if not all_services:
            return ComposeResult(generated=False, path="", services=[])

        # Wire app depends_on db services
        db_names = [s.name for s in db_services]
        for svc in app_services:
            svc.depends_on = db_names

        compose: dict = {"version": "3.9", "services": {}}
        volumes_needed: list[str] = []
        for svc in all_services:
            compose["services"][svc.name] = svc.to_compose_dict()
            for vol in svc.volumes:
                vol_name = vol.split(":")[0]
                if vol_name not in volumes_needed:
                    volumes_needed.append(vol_name)

        if volumes_needed:
            compose["volumes"] = {v: {} for v in volumes_needed}

        compose_path = source_dir / "docker-compose.yml"
        try:
            compose_path.parent.mkdir(parents=True, exist_ok=True)
            compose_path.write_text(self._dict_to_yaml(compose), encoding="utf-8")
            return ComposeResult(
                generated=True,
                path=str(compose_path),
                services=list(compose["services"].keys()),
            )
        except Exception as e:
            return ComposeResult(generated=False, path="", services=[], error=str(e))

    @staticmethod
    def _dict_to_yaml(d: dict, indent: int = 0) -> str:
        """Minimal YAML serialiser (avoids PyYAML dependency for simple cases)."""
        lines = []
        pad = "  " * indent
        for k, v in d.items():
            if isinstance(v, dict):
                lines.append(f"{pad}{k}:")
                lines.append(ServiceOrchestrator._dict_to_yaml(v, indent + 1))
            elif isinstance(v, list):
                lines.append(f"{pad}{k}:")
                for item in v:
                    if isinstance(item, dict):
                        sub = ServiceOrchestrator._dict_to_yaml(item, indent + 2)
                        lines.append(f"{'  '*(indent+1)}- {sub.lstrip()}")
                    else:
                        lines.append(f"{'  '*(indent+1)}- {item}")
            else:
                lines.append(f"{pad}{k}: {v}")
        return "\n".join(lines)
