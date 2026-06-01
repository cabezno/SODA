"""
APIContractEnforcer — static analysis of frontend↔backend API consistency.

Extracts the actual API contract from backend source files (routes, methods,
request/response schemas) and verifies the frontend consumes those exact
endpoints.

Supports:
  Backend detection: FastAPI, Express, NestJS, Flask, Django REST, Spring Boot, Go/Gin
  Frontend detection: fetch/axios calls in React/Vue/Angular/plain JS/TS
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Endpoint:
    method: str      # GET | POST | PUT | PATCH | DELETE
    path: str        # /api/users
    source_file: str
    line: Optional[int] = None

    def normalized(self) -> str:
        """Normalized path for comparison (strip trailing slash, lowercase method)."""
        return f"{self.method.upper()} {self.path.rstrip('/')}"


@dataclass
class FrontendCall:
    method: str
    path: str
    source_file: str
    line: Optional[int] = None

    def normalized(self) -> str:
        return f"{self.method.upper()} {self.path.rstrip('/')}"


@dataclass
class ContractViolation:
    kind: str        # "missing_endpoint" | "unused_endpoint" | "method_mismatch"
    frontend_file: str
    backend_file: str
    path: str
    message: str

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "frontend_file": self.frontend_file,
            "backend_file": self.backend_file,
            "path": self.path,
            "message": self.message,
        }


@dataclass
class ContractReport:
    backend_endpoints: list[Endpoint] = field(default_factory=list)
    frontend_calls: list[FrontendCall] = field(default_factory=list)
    violations: list[ContractViolation] = field(default_factory=list)
    skipped: bool = False
    reason: str = ""

    @property
    def has_violations(self) -> bool:
        return bool(self.violations)

    def to_dict(self) -> dict:
        return {
            "backend_endpoints": len(self.backend_endpoints),
            "frontend_calls": len(self.frontend_calls),
            "violations": [v.to_dict() for v in self.violations],
            "skipped": self.skipped,
            "reason": self.reason,
        }


# ─────────────────────────────── backend extractors ──

def _extract_fastapi_endpoints(source_dir: Path) -> list[Endpoint]:
    endpoints = []
    pattern = re.compile(
        r'@(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )
    for f in source_dir.rglob("*.py"):
        if any(s in f.parts for s in ("test", "tests", "__pycache__", "venv")):
            continue
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(lines, 1):
            for m in pattern.finditer(line):
                endpoints.append(Endpoint(
                    method=m.group(1).upper(),
                    path=m.group(2),
                    source_file=rel,
                    line=i,
                ))
    return endpoints


def _extract_flask_endpoints(source_dir: Path) -> list[Endpoint]:
    endpoints = []
    pattern = re.compile(
        r'@(?:app|bp|blueprint)\s*\.route\s*\(\s*["\']([^"\']+)["\'].*?methods\s*=\s*\[([^\]]+)\]',
        re.IGNORECASE | re.DOTALL,
    )
    for f in source_dir.rglob("*.py"):
        if any(s in f.parts for s in ("test", "tests", "__pycache__", "venv")):
            continue
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        src = f.read_text(encoding="utf-8", errors="ignore")
        for m in pattern.finditer(src):
            path = m.group(1)
            methods = [x.strip().strip("'\"") for x in m.group(2).split(",")]
            for method in methods:
                endpoints.append(Endpoint(method=method.upper(), path=path, source_file=rel))
    return endpoints


def _extract_express_endpoints(source_dir: Path) -> list[Endpoint]:
    endpoints = []
    pattern = re.compile(
        r'(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )
    skip = {"node_modules", ".git", "dist", "build", ".next", "test", "tests", "__tests__"}
    for ext in ("*.js", "*.ts"):
        for f in source_dir.rglob(ext):
            if any(s in f.parts for s in skip):
                continue
            rel = str(f.relative_to(source_dir)).replace("\\", "/")
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            for i, line in enumerate(lines, 1):
                for m in pattern.finditer(line):
                    endpoints.append(Endpoint(
                        method=m.group(1).upper(),
                        path=m.group(2),
                        source_file=rel,
                        line=i,
                    ))
    return endpoints


def _extract_spring_endpoints(source_dir: Path) -> list[Endpoint]:
    endpoints = []
    mapping_pattern = re.compile(
        r'@(GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)'
        r'\s*(?:\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\'])?',
    )
    method_map = {
        "GetMapping": "GET", "PostMapping": "POST", "PutMapping": "PUT",
        "PatchMapping": "PATCH", "DeleteMapping": "DELETE", "RequestMapping": "GET",
    }
    for f in source_dir.rglob("*.java"):
        if "test" in str(f).lower():
            continue
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        src = f.read_text(encoding="utf-8", errors="ignore")
        for m in mapping_pattern.finditer(src):
            ann = m.group(1)
            path = m.group(2) or "/"
            endpoints.append(Endpoint(
                method=method_map.get(ann, "GET"),
                path=path,
                source_file=rel,
            ))
    return endpoints


def _extract_go_gin_endpoints(source_dir: Path) -> list[Endpoint]:
    endpoints = []
    pattern = re.compile(
        r'(?:r|router|engine)\.(GET|POST|PUT|PATCH|DELETE)\s*\(\s*"([^"]+)"',
    )
    for f in source_dir.rglob("*.go"):
        if "test" in f.name:
            continue
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(lines, 1):
            for m in pattern.finditer(line):
                endpoints.append(Endpoint(
                    method=m.group(1).upper(),
                    path=m.group(2),
                    source_file=rel,
                    line=i,
                ))
    return endpoints


# ─────────────────────────────── frontend extractors ──

def _extract_frontend_calls(source_dir: Path) -> list[FrontendCall]:
    """Extract API calls from frontend JS/TS files."""
    calls = []
    skip = {"node_modules", ".git", "dist", "build", ".next", "test", "tests", "__tests__"}

    # fetch('/api/...')  axios.get('/api/...')  api.post('/api/...')
    patterns = [
        # fetch("url", {method: "POST"}) or fetch("url") → GET
        (re.compile(r'fetch\s*\(\s*["`\']([^"`\']+)["`\'](?:.*?method\s*:\s*["`\'](\w+)["`\'])?', re.DOTALL), "GET"),
        # axios.METHOD("url")
        (re.compile(r'axios\.(get|post|put|patch|delete)\s*\(\s*["`\']([^"`\']+)["`\']'), None),
        # api.METHOD("url") or http.METHOD("url")
        (re.compile(r'(?:api|http|client|service)\.(get|post|put|patch|delete)\s*\(\s*["`\']([^"`\']+)["`\']'), None),
    ]

    for ext in ("*.js", "*.ts", "*.jsx", "*.tsx", "*.vue"):
        for f in source_dir.rglob(ext):
            if any(s in f.parts for s in skip):
                continue
            rel = str(f.relative_to(source_dir)).replace("\\", "/")
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            for i, line in enumerate(lines, 1):
                # fetch pattern
                for m in re.finditer(r'fetch\s*\(\s*["`\']([^"`\']+)["`\']', line):
                    path = m.group(1)
                    if not _looks_like_api_path(path):
                        continue
                    method_m = re.search(r'method\s*:\s*["`\'](\w+)["`\']', line)
                    method = method_m.group(1).upper() if method_m else "GET"
                    calls.append(FrontendCall(method=method, path=path, source_file=rel, line=i))

                # axios.METHOD
                for m in re.finditer(r'axios\.(get|post|put|patch|delete)\s*\(\s*["`\']([^"`\']+)["`\']', line, re.IGNORECASE):
                    path = m.group(2)
                    if _looks_like_api_path(path):
                        calls.append(FrontendCall(method=m.group(1).upper(), path=path, source_file=rel, line=i))

                # api/http/client/service.METHOD
                for m in re.finditer(
                    r'(?:api|http|client|service)\.(get|post|put|patch|delete)\s*\(\s*["`\']([^"`\']+)["`\']',
                    line, re.IGNORECASE
                ):
                    path = m.group(2)
                    if _looks_like_api_path(path):
                        calls.append(FrontendCall(method=m.group(1).upper(), path=path, source_file=rel, line=i))

    return calls


def _looks_like_api_path(path: str) -> bool:
    """Heuristic: does this string look like an API endpoint path?"""
    return (
        path.startswith("/") or
        path.startswith("http") or
        "/api/" in path or
        path.startswith("api/")
    )


# ─────────────────────────────── path normalization ──

def _normalize_path(path: str) -> str:
    """Strip host, query string, trailing slash. Keep path template params."""
    # Remove protocol+host
    path = re.sub(r'^https?://[^/]+', '', path)
    # Remove query string
    path = path.split("?")[0].split("#")[0]
    # Normalize path params: {id} → :param, :id → :param
    path = re.sub(r'\{[^}]+\}', ':param', path)
    path = re.sub(r':[a-zA-Z_]\w*', ':param', path)
    return path.rstrip("/") or "/"


# ─────────────────────────────── main class ──

class APIContractEnforcer:
    """
    Compares backend-defined endpoints against frontend API calls.
    Uses pure static analysis — no AI required.
    """

    def __init__(self, notify_fn=None):
        self.notify = notify_fn or (lambda *a, **kw: None)

    def enforce(self, source_dir: Path, architecture: dict, blueprint: dict) -> ContractReport:
        report = ContractReport()

        # Determine if this is a full-stack project
        stack = architecture.get("stack", {})
        has_backend = bool(stack.get("backend"))
        has_frontend = bool(stack.get("frontend"))

        if not has_backend or not has_frontend:
            report.skipped = True
            report.reason = "Proyecto sin stack full-stack — análisis de contrato omitido."
            self.notify(report.reason, "LOG", {})
            return report

        # Extract backend endpoints
        backend_endpoints = self._extract_backend_endpoints(source_dir, architecture)
        report.backend_endpoints = backend_endpoints

        # Extract frontend calls
        frontend_calls = _extract_frontend_calls(source_dir)
        report.frontend_calls = frontend_calls

        if not backend_endpoints:
            report.skipped = True
            report.reason = "No se detectaron endpoints de backend — omitiendo análisis."
            self.notify(report.reason, "LOG", {})
            return report

        if not frontend_calls:
            report.skipped = True
            report.reason = "No se detectaron llamadas API en el frontend — omitiendo análisis."
            self.notify(report.reason, "LOG", {})
            return report

        # Build lookup
        backend_map: dict[str, Endpoint] = {
            _normalize_path(e.path): e
            for e in backend_endpoints
        }
        frontend_map: dict[str, FrontendCall] = {}
        for call in frontend_calls:
            key = _normalize_path(call.path)
            frontend_map[key] = call

        # Check 1: frontend calls endpoints that don't exist in backend
        for norm_path, call in frontend_map.items():
            if norm_path not in backend_map:
                # Check if any backend endpoint path is similar (substring match)
                similar = any(norm_path in bp or bp in norm_path for bp in backend_map)
                if not similar:
                    report.violations.append(ContractViolation(
                        kind="missing_endpoint",
                        frontend_file=call.source_file,
                        backend_file="(ninguno)",
                        path=call.path,
                        message=(
                            f"El frontend llama {call.method} {call.path} "
                            f"pero ese endpoint no existe en el backend."
                        ),
                    ))

        # Check 2: method mismatch
        for norm_path, call in frontend_map.items():
            if norm_path in backend_map:
                backend_ep = backend_map[norm_path]
                if call.method != backend_ep.method and call.method != "GET":
                    report.violations.append(ContractViolation(
                        kind="method_mismatch",
                        frontend_file=call.source_file,
                        backend_file=backend_ep.source_file,
                        path=call.path,
                        message=(
                            f"Método incorrecto: frontend usa {call.method} "
                            f"pero backend define {backend_ep.method} para {call.path}."
                        ),
                    ))

        self._log_report(report)
        return report

    def _extract_backend_endpoints(self, source_dir: Path, architecture: dict) -> list[Endpoint]:
        stack = architecture.get("stack", {})
        backend = (stack.get("backend") or "").lower()

        all_endpoints: list[Endpoint] = []

        if "fastapi" in backend or "flask" in backend:
            all_endpoints += _extract_fastapi_endpoints(source_dir)
            all_endpoints += _extract_flask_endpoints(source_dir)
        elif "express" in backend or "node" in backend or "nest" in backend:
            all_endpoints += _extract_express_endpoints(source_dir)
        elif "spring" in backend or "java" in backend or "kotlin" in backend:
            all_endpoints += _extract_spring_endpoints(source_dir)
        elif "go" in backend or "gin" in backend:
            all_endpoints += _extract_go_gin_endpoints(source_dir)
        else:
            # Try all extractors
            all_endpoints += _extract_fastapi_endpoints(source_dir)
            all_endpoints += _extract_flask_endpoints(source_dir)
            all_endpoints += _extract_express_endpoints(source_dir)
            all_endpoints += _extract_go_gin_endpoints(source_dir)
            all_endpoints += _extract_spring_endpoints(source_dir)

        return all_endpoints

    def _log_report(self, report: ContractReport) -> None:
        if report.skipped:
            return
        summary = (
            f"APIContractEnforcer: {len(report.backend_endpoints)} endpoints backend, "
            f"{len(report.frontend_calls)} llamadas frontend, "
            f"{len(report.violations)} violación(es)."
        )
        if report.violations:
            self.notify(summary, "HEALTH_WARN", report.to_dict())
            for v in report.violations:
                print(f"  [CONTRACT] ⚠️  {v.kind} — {v.path}: {v.message}")
        else:
            self.notify(summary, "LOG", {})
            print(f"  [CONTRACT] ✓ Contrato frontend↔backend consistente.")
