"""RuntimeManager — Docker-based runtime registry for SODA execution environments."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class RuntimeManager:
    def __init__(self, registry_path: str | Path = "kernel/execution/stack_profiles.yaml"):
        self.registry: dict = {}
        self.client = None
        self._load_registry(registry_path)
        self._init_docker()

    def _load_registry(self, registry_path: str | Path) -> None:
        path = Path(registry_path)
        if not path.exists():
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.registry = data.get("runtimes", data)
        except Exception:
            pass

    def _init_docker(self) -> None:
        try:
            import docker
            self.client = docker.DockerClient()
        except Exception:
            self.client = None

    def is_runtime_ready(self, runtime_name: str) -> bool:
        config = self.get_runtime_config(runtime_name)
        if not config or not self.client:
            return False
        try:
            self.client.images.get(config["image_tag"])
            return True
        except Exception:
            return False

    def get_runtime_config(self, runtime_name: str) -> Optional[dict]:
        return self.registry.get(runtime_name)
