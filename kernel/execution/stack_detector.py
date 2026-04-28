from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def _load_profiles() -> list[dict]:
    catalog = Path(__file__).parent / "stack_profiles.yaml"
    try:
        data = yaml.safe_load(catalog.read_text(encoding="utf-8"))
        return data.get("profiles", [])
    except Exception:
        return []


class StackDetector:
    """Detects project stack from run/install commands using stack_profiles.yaml catalog."""

    @staticmethod
    def detect(run_command: str, install_command: str = "") -> str:
        r = (run_command or "").lower()
        i = (install_command or "").lower()

        for profile in _load_profiles():
            if any(kw in r for kw in profile.get("run_keywords", [])):
                return profile["id"]
            if any(kw in i for kw in profile.get("install_keywords", [])):
                return profile["id"]

        return "unknown"

    @staticmethod
    def is_http_probe_applicable(stack_id: str) -> bool:
        """Return True if this stack is expected to serve HTTP and can be smoke-probed.

        Stacks with http_probe: false (go, rust, static) are CLI/batch — probing them
        would always fail and produce misleading HEALTH_WARN noise.
        Unknown stacks default to False (don't probe what we can't classify).
        """
        for profile in _load_profiles():
            if profile["id"] == stack_id:
                return bool(profile.get("http_probe", False))
        return False
