from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests


@dataclass
class SmokeResult:
    url: str
    method: str
    status_code: int
    passed: bool
    reason: str
    latency_ms: float = 0.0


@dataclass
class SmokeSuiteResult:
    base_url: str
    total: int
    passed: int
    failed: int
    results: list[SmokeResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and self.total > 0

    def to_dict(self) -> dict:
        return {
            "base_url": self.base_url,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "all_passed": self.all_passed,
            "results": [
                {"url": r.url, "method": r.method, "status_code": r.status_code,
                 "passed": r.passed, "reason": r.reason, "latency_ms": r.latency_ms}
                for r in self.results
            ],
        }


class SmokeTester:
    """
    Generates and executes functional smoke tests against a running project.

    Discovers endpoints from:
    1. architecture.json → module endpoints lists
    2. Source file scanning (FastAPI/Flask/Express route patterns)
    3. Common convention probes (/health, /docs, /api)
    """

    CONVENTION_PATHS = ["/health", "/healthz", "/ping", "/status", "/docs", "/api", "/"]
    MAX_ENDPOINTS = 20

    # --- Endpoint discovery ---

    def discover_from_architecture(self, architecture: dict) -> list[dict]:
        """Extract endpoints from architecture.json module definitions."""
        endpoints = []
        for module in architecture.get("modulos", []):
            for ep in module.get("endpoints", []):
                if isinstance(ep, dict):
                    endpoints.append(ep)
                elif isinstance(ep, str):
                    endpoints.append({"path": ep, "method": "GET"})
        return endpoints

    def discover_from_source(self, source_dir: Path) -> list[dict]:
        """Scan source files for route decorators (FastAPI, Flask, Express)."""
        endpoints = []
        patterns = [
            # FastAPI / Flask
            r'@\w+\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
            # Express.js
            r'router\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
            r'app\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
        ]
        for fpath in source_dir.rglob("*"):
            if not fpath.is_file():
                continue
            if fpath.suffix not in {".py", ".js", ".ts", ".mjs"}:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
                for pat in patterns:
                    for m in re.finditer(pat, text, re.IGNORECASE):
                        method, path = m.group(1).upper(), m.group(2)
                        if not path.startswith("{"):
                            endpoints.append({"path": path, "method": method})
            except Exception:
                pass
        return endpoints

    def build_test_plan(
        self,
        base_url: str,
        architecture: dict,
        source_dir: Optional[Path] = None,
    ) -> list[dict]:
        """Combine discovered endpoints with convention probes, deduplicated."""
        discovered: list[dict] = []

        if architecture:
            discovered.extend(self.discover_from_architecture(architecture))
        if source_dir and source_dir.exists():
            discovered.extend(self.discover_from_source(source_dir))

        # Normalise paths → deduplicate
        seen: set[tuple[str, str]] = set()
        plan: list[dict] = []
        for ep in discovered:
            path = ep.get("path", "/")
            method = ep.get("method", "GET").upper()
            # Skip parameterised paths for smoke tests
            if "{" in path or "<" in path or ":" in path:
                continue
            key = (method, path)
            if key not in seen:
                seen.add(key)
                plan.append({"url": base_url.rstrip("/") + path, "method": method})

        # Add convention probes (GET only, skip if already covered)
        for path in self.CONVENTION_PATHS:
            key = ("GET", path)
            if key not in seen:
                seen.add(key)
                plan.append({"url": base_url.rstrip("/") + path, "method": "GET"})

        return plan[: self.MAX_ENDPOINTS]

    # --- Execution ---

    def _probe(self, url: str, method: str, timeout_s: float = 3.0) -> SmokeResult:
        import time
        t0 = time.monotonic()
        try:
            resp = requests.request(method, url, timeout=timeout_s, allow_redirects=True)
            latency = (time.monotonic() - t0) * 1000
            passed = resp.status_code < 500
            return SmokeResult(
                url=url, method=method, status_code=resp.status_code,
                passed=passed, reason="ok" if passed else f"http_{resp.status_code}",
                latency_ms=round(latency, 1),
            )
        except requests.ConnectionError:
            return SmokeResult(url=url, method=method, status_code=0, passed=False, reason="connection_error")
        except requests.Timeout:
            return SmokeResult(url=url, method=method, status_code=0, passed=False, reason="timeout")
        except Exception as e:
            return SmokeResult(url=url, method=method, status_code=0, passed=False, reason=str(e)[:80])

    def run_suite(
        self,
        base_url: str,
        architecture: dict,
        source_dir: Optional[Path] = None,
        timeout_s: float = 3.0,
    ) -> SmokeSuiteResult:
        """Run the full smoke test suite synchronously."""
        plan = self.build_test_plan(base_url, architecture, source_dir)
        results = [self._probe(ep["url"], ep["method"], timeout_s) for ep in plan]
        passed = sum(1 for r in results if r.passed)
        return SmokeSuiteResult(
            base_url=base_url,
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            results=results,
        )

    async def run_suite_async(
        self,
        base_url: str,
        architecture: dict,
        source_dir: Optional[Path] = None,
        timeout_s: float = 3.0,
    ) -> SmokeSuiteResult:
        """Run smoke suite in a thread pool to avoid blocking the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.run_suite, base_url, architecture, source_dir, timeout_s
        )
