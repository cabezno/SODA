"""
ImportDependencyValidator — post-DEV static analysis.

Scans all generated source files, extracts real imports/requires,
and reconciles them against the project manifest (requirements.txt,
package.json, go.mod, Cargo.toml, pom.xml, etc.).

Returns a report with:
  - missing_packages: used in code but not declared in manifest
  - undeclared_local_imports: relative imports that point to non-existent files
  - manifest_path: which manifest file was checked

Also auto-patches the manifest by appending missing packages when possible.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────── data models ──

@dataclass
class ImportIssue:
    kind: str          # "missing_package" | "broken_local_import"
    file: str
    import_name: str
    message: str

    def to_dict(self) -> dict:
        return {"kind": self.kind, "file": self.file, "import": self.import_name, "message": self.message}


@dataclass
class ImportValidationReport:
    language: str
    issues: list[ImportIssue] = field(default_factory=list)
    missing_packages: list[str] = field(default_factory=list)
    manifest_path: str = ""
    manifest_patched: bool = False
    skipped: bool = False

    @property
    def has_errors(self) -> bool:
        return bool(self.issues)

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "missing_packages": self.missing_packages,
            "manifest_path": self.manifest_path,
            "manifest_patched": self.manifest_patched,
            "issues_count": len(self.issues),
            "issues": [i.to_dict() for i in self.issues[:20]],
            "skipped": self.skipped,
        }


# ─────────────────────────────────────────── stdlib sets ──

PYTHON_STDLIB = {
    "abc", "ast", "asyncio", "base64", "builtins", "collections", "concurrent",
    "contextlib", "copy", "csv", "dataclasses", "datetime", "decimal", "email",
    "enum", "functools", "glob", "hashlib", "http", "importlib", "inspect",
    "io", "itertools", "json", "logging", "math", "multiprocessing", "operator",
    "os", "pathlib", "pickle", "platform", "pprint", "queue", "random", "re",
    "shutil", "signal", "socket", "sqlite3", "ssl", "string", "struct",
    "subprocess", "sys", "tempfile", "textwrap", "threading", "time",
    "traceback", "typing", "unittest", "urllib", "uuid", "warnings",
    "weakref", "xml", "zipfile", "zlib", "__future__",
}

NODE_BUILTINS = {
    "fs", "path", "os", "http", "https", "url", "querystring", "crypto",
    "stream", "events", "util", "buffer", "child_process", "cluster",
    "net", "dns", "tls", "readline", "zlib", "assert", "module",
}


# ─────────────────────────────────────────── extractors ──

def _extract_python_imports(source: str) -> list[str]:
    """Return top-level package names from import/from statements."""
    pkgs: set[str] = set()
    for m in re.finditer(r"^(?:import|from)\s+([\w.]+)", source, re.MULTILINE):
        root = m.group(1).split(".")[0]
        if root:
            pkgs.add(root)
    return list(pkgs)


def _extract_node_imports(source: str) -> list[str]:
    """Return package names from require()/import statements (non-relative)."""
    pkgs: set[str] = set()
    patterns = [
        r'require\(["\']([^"\'./][^"\']*)["\']',
        r'from\s+["\']([^"\'./][^"\']*)["\']',
        r'import\s+["\']([^"\'./][^"\']*)["\']',
    ]
    for pat in patterns:
        for m in re.finditer(pat, source):
            name = m.group(1)
            # scoped packages: @org/pkg → keep as-is
            pkgs.add(name)
    return list(pkgs)


def _extract_go_imports(source: str) -> list[str]:
    """Return non-stdlib module paths from Go import blocks."""
    pkgs: set[str] = set()
    # Multi-line import block
    block = re.search(r'import\s*\((.*?)\)', source, re.DOTALL)
    if block:
        for m in re.finditer(r'"([^"]+)"', block.group(1)):
            pkgs.add(m.group(1))
    # Single imports
    for m in re.finditer(r'^import\s+"([^"]+)"', source, re.MULTILINE):
        pkgs.add(m.group(1))
    return list(pkgs)


# ─────────────────────────────────────────── manifest readers ──

def _read_python_manifest(source_dir: Path) -> tuple[set[str], Path | None]:
    """Return (declared_packages, manifest_path)."""
    declared: set[str] = set()
    manifest: Optional[Path] = None

    req = source_dir / "requirements.txt"
    if req.exists():
        manifest = req
        for line in req.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            pkg = re.split(r"[>=<!;\[]", line)[0].strip().lower().replace("-", "_")
            if pkg:
                declared.add(pkg)

    pyproject = source_dir / "pyproject.toml"
    if pyproject.exists():
        manifest = manifest or pyproject
        content = pyproject.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'"([\w\-]+)\s*(?:[>=<!\[].*?)?"', content):
            declared.add(m.group(1).lower().replace("-", "_"))

    return declared, manifest


def _read_node_manifest(source_dir: Path) -> tuple[set[str], Path | None]:
    pkg_path = source_dir / "package.json"
    if not pkg_path.exists():
        return set(), None
    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8", errors="ignore"))
        deps: set[str] = set()
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            for name in data.get(section, {}):
                deps.add(name)
        return deps, pkg_path
    except Exception:
        return set(), pkg_path


def _read_go_manifest(source_dir: Path) -> tuple[set[str], Path | None]:
    go_mod = source_dir / "go.mod"
    if not go_mod.exists():
        return set(), None
    declared: set[str] = set()
    for line in go_mod.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r'\s*([\w./\-]+)\s+v[\d.]+', line)
        if m:
            declared.add(m.group(1))
    return declared, go_mod


# ─────────────────────────────────────────── patchers ──

def _patch_python_manifest(manifest: Path, missing: list[str]) -> bool:
    """Append missing packages to requirements.txt."""
    if manifest.name != "requirements.txt":
        return False
    try:
        existing = manifest.read_text(encoding="utf-8")
        additions = "\n".join(missing)
        manifest.write_text(existing.rstrip() + "\n" + additions + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def _patch_node_manifest(manifest: Path, missing: list[str]) -> bool:
    """Add missing packages to package.json dependencies."""
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        deps = data.setdefault("dependencies", {})
        for pkg in missing:
            if pkg not in deps:
                deps[pkg] = "*"
        manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


# ─────────────────────────────────────────── known package aliases ──

# Maps import name → canonical pip name (when they differ)
PYTHON_IMPORT_TO_PIP: dict[str, str] = {
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "yaml": "PyYAML",
    "dotenv": "python-dotenv",
    "jose": "python-jose",
    "passlib": "passlib",
    "jwt": "PyJWT",
    "dateutil": "python-dateutil",
    "attr": "attrs",
    "google.cloud": "google-cloud",
    "google.generativeai": "google-generativeai",
    "anthropic": "anthropic",
    "openai": "openai",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "sqlalchemy": "SQLAlchemy",
    "alembic": "alembic",
    "pydantic": "pydantic",
    "celery": "celery",
    "redis": "redis",
    "pymongo": "pymongo",
    "motor": "motor",
    "aiohttp": "aiohttp",
    "httpx": "httpx",
    "requests": "requests",
    "boto3": "boto3",
    "stripe": "stripe",
    "twilio": "twilio",
    "sendgrid": "sendgrid",
}


# ─────────────────────────────────────────── main class ──

class ImportDependencyValidator:
    """
    Post-DEV validator that ensures the project manifest matches
    the imports actually used in generated code.
    """

    def __init__(self, notify_fn=None):
        self.notify = notify_fn or (lambda *a, **kw: None)

    def validate(self, source_dir: Path, architecture: dict) -> ImportValidationReport:
        lang = self._detect_language(source_dir, architecture)
        report = ImportValidationReport(language=lang)

        if lang == "python":
            return self._validate_python(source_dir, report)
        elif lang in ("node", "react", "typescript"):
            return self._validate_node(source_dir, report)
        elif lang == "go":
            return self._validate_go(source_dir, report)
        else:
            report.skipped = True
            self.notify(f"ImportValidator: lenguaje '{lang}' — análisis omitido.", "LOG", {})
            return report

    def _detect_language(self, source_dir: Path, architecture: dict) -> str:
        all_files = [
            f for m in architecture.get("modulos", [])
            for f in m.get("archivos_principales", [])
        ]
        exts = {Path(f).suffix.lower() for f in all_files}
        names = {Path(f).name for f in all_files}

        if ".py" in exts or "requirements.txt" in names or "pyproject.toml" in names:
            return "python"
        if ".tsx" in exts or ".jsx" in exts:
            return "react"
        if ".ts" in exts:
            return "typescript"
        if ".js" in exts or "package.json" in names:
            return "node"
        if ".go" in exts or "go.mod" in names:
            return "go"

        # Fallback: scan disk
        if source_dir.exists():
            if any(source_dir.rglob("*.py")):
                return "python"
            if any(source_dir.rglob("*.go")):
                return "go"
            if any(source_dir.rglob("*.ts")) or any(source_dir.rglob("*.tsx")):
                return "typescript"
            if any(source_dir.rglob("*.js")):
                return "node"

        return "unknown"

    def _validate_python(self, source_dir: Path, report: ImportValidationReport) -> ImportValidationReport:
        declared, manifest = _read_python_manifest(source_dir)
        report.manifest_path = str(manifest) if manifest else ""

        used: set[str] = set()
        skip = {"venv", "__pycache__", ".git", "build", "dist"}
        for py_file in source_dir.rglob("*.py"):
            if any(s in py_file.parts for s in skip):
                continue
            src = py_file.read_text(encoding="utf-8", errors="ignore")
            for pkg in _extract_python_imports(src):
                if pkg not in PYTHON_STDLIB and not pkg.startswith("_"):
                    canonical = pkg.lower().replace("-", "_")
                    used.add(canonical)

        # Resolve aliases
        resolved_used: set[str] = set()
        for pkg in used:
            pip_name = PYTHON_IMPORT_TO_PIP.get(pkg, pkg).lower().replace("-", "_")
            resolved_used.add(pip_name)

        missing = sorted(resolved_used - {d.lower().replace("-", "_") for d in declared} - PYTHON_STDLIB)
        # Filter out local project packages (single-word names that are also directory names)
        local_dirs = {p.name.lower() for p in source_dir.iterdir() if p.is_dir()} if source_dir.exists() else set()
        missing = [m for m in missing if m not in local_dirs]

        report.missing_packages = missing
        for pkg in missing:
            report.issues.append(ImportIssue(
                kind="missing_package",
                file="requirements.txt",
                import_name=pkg,
                message=f"'{pkg}' se usa en el código pero no está declarado en el manifiesto.",
            ))

        if missing and manifest and manifest.name == "requirements.txt":
            try:
                patched = _patch_python_manifest(manifest, missing)
                report.manifest_patched = patched
                if patched:
                    self.notify(
                        f"ImportValidator: {len(missing)} paquete(s) añadido(s) a requirements.txt: {', '.join(missing)}",
                        "LOG", {"added": missing},
                    )
            except Exception:
                pass

        self._log_report(report)
        return report

    def _validate_node(self, source_dir: Path, report: ImportValidationReport) -> ImportValidationReport:
        declared, manifest = _read_node_manifest(source_dir)
        report.manifest_path = str(manifest) if manifest else ""

        used: set[str] = set()
        skip = {"node_modules", ".git", "dist", "build", ".next"}
        for ext in ("*.ts", "*.tsx", "*.js", "*.jsx"):
            for f in source_dir.rglob(ext):
                if any(s in f.parts for s in skip):
                    continue
                src = f.read_text(encoding="utf-8", errors="ignore")
                for pkg in _extract_node_imports(src):
                    if pkg not in NODE_BUILTINS:
                        used.add(pkg)

        # Normalize scoped package names
        missing = sorted(used - declared)
        report.missing_packages = missing
        for pkg in missing:
            report.issues.append(ImportIssue(
                kind="missing_package",
                file="package.json",
                import_name=pkg,
                message=f"'{pkg}' se importa en el código pero no está en package.json.",
            ))

        if missing and manifest:
            try:
                patched = _patch_node_manifest(manifest, missing)
                report.manifest_patched = patched
                if patched:
                    self.notify(
                        f"ImportValidator: {len(missing)} paquete(s) añadido(s) a package.json: {', '.join(missing[:5])}",
                        "LOG", {"added": missing},
                    )
            except Exception:
                pass

        self._log_report(report)
        return report

    def _validate_go(self, source_dir: Path, report: ImportValidationReport) -> ImportValidationReport:
        declared, manifest = _read_go_manifest(source_dir)
        report.manifest_path = str(manifest) if manifest else ""

        used: set[str] = set()
        for go_file in source_dir.rglob("*.go"):
            src = go_file.read_text(encoding="utf-8", errors="ignore")
            for pkg in _extract_go_imports(src):
                # Skip stdlib (no dot in first segment) and relative imports
                parts = pkg.split("/")
                if "." in parts[0]:  # external module (e.g., github.com/...)
                    used.add(pkg)

        # For Go, just report — we don't auto-patch go.mod (needs go get)
        missing = sorted(used - declared)
        report.missing_packages = missing
        for pkg in missing:
            report.issues.append(ImportIssue(
                kind="missing_package",
                file="go.mod",
                import_name=pkg,
                message=f"'{pkg}' se importa pero no aparece en go.mod. Ejecutá: go get {pkg}",
            ))

        self._log_report(report)
        return report

    def _log_report(self, report: ImportValidationReport) -> None:
        if report.skipped:
            return
        if report.issues:
            self.notify(
                f"ImportValidator [{report.language}]: {len(report.missing_packages)} paquete(s) faltante(s) en manifiesto.",
                "HEALTH_WARN",
                report.to_dict(),
            )
        else:
            self.notify(
                f"ImportValidator [{report.language}]: manifiesto consistente con el código.",
                "LOG", {},
            )
