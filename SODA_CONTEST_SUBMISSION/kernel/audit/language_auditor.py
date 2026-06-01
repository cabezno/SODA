"""
LanguageAuditor: post-generation code audit with language-specific rules.

Flow:
  1. detect_language()  — infer stack from files + architecture
  2. audit_project()    — run all mechanical rules (no AI needed)
  3. If violations found → request_ai_fix() asks Gemini/Gemini for fixes
  4. Returns AuditResult with violations, score, and AI-generated patches

Rules are pure Python functions: (source_dir, architecture) → list[AuditViolation].
Adding a new language = adding entries to LANGUAGE_RULES dict.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


# ─────────────────────────────────────────────────────────────────── models ──

@dataclass
class AuditViolation:
    rule: str
    file: str
    severity: str          # "error" | "warning" | "info"
    message: str
    line: Optional[int] = None
    suggested_fix: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "file": self.file,
            "severity": self.severity,
            "message": self.message,
            "line": self.line,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class AuditResult:
    language: str
    violations: list[AuditViolation] = field(default_factory=list)
    ai_fixes: list[dict] = field(default_factory=list)    # [{file, code, reason}]
    score: float = 100.0                                   # 0-100
    passed: bool = True

    @property
    def errors(self) -> list[AuditViolation]:
        return [v for v in self.violations if v.severity == "error"]

    @property
    def warnings(self) -> list[AuditViolation]:
        return [v for v in self.violations if v.severity == "warning"]

    def summary(self) -> str:
        return (
            f"[{self.language}] score={self.score:.0f}/100 "
            f"errors={len(self.errors)} warnings={len(self.warnings)}"
        )

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "score": self.score,
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "ai_fixes": self.ai_fixes,
        }


# ──────────────────────────────────────────────────────────── rule helpers ──

RuleFn = Callable[[Path, dict], list[AuditViolation]]


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _files_by_ext(source_dir: Path, *exts: str, skip_dirs=None) -> list[Path]:
    skip = skip_dirs or {"venv", "node_modules", ".git", "__pycache__", "build",
                         "dist", ".next", "target", "bin", "obj", ".gradle"}
    result = []
    for p in source_dir.rglob("*"):
        if any(s in p.parts for s in skip):
            continue
        if p.suffix.lower() in exts:
            result.append(p)
    return result


def _missing_file(source_dir: Path, rel: str, rule: str, msg: str) -> list[AuditViolation]:
    if not (source_dir / rel).exists():
        return [AuditViolation(rule=rule, file=rel, severity="error", message=msg)]
    return []


# ──────────────────────────────────────────────────────── language rules ──

def _rules_python(source_dir: Path, arch: dict) -> list[AuditViolation]:
    v: list[AuditViolation] = []

    # Required project files
    has_req = (source_dir / "requirements.txt").exists()
    has_pyproject = (source_dir / "pyproject.toml").exists()
    if not has_req and not has_pyproject:
        v.append(AuditViolation(
            rule="PY001", file="requirements.txt", severity="error",
            message="Falta requirements.txt o pyproject.toml — imposible instalar dependencias.",
            suggested_fix="Crear requirements.txt con las dependencias del proyecto."
        ))

    if not (source_dir / ".env.example").exists():
        v.append(AuditViolation(
            rule="PY002", file=".env.example", severity="warning",
            message="Falta .env.example — el usuario no sabe qué variables configurar."
        ))

    # Python files: check for bare except
    for f in _files_by_ext(source_dir, ".py"):
        content = _read(f)
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        if re.search(r"^\s*except\s*:", content, re.MULTILINE):
            v.append(AuditViolation(
                rule="PY003", file=rel, severity="warning",
                message="'except:' sin tipo captura todas las excepciones incluyendo KeyboardInterrupt. Usá 'except Exception:'."
            ))
        if "print(" in content and not rel.endswith("main.py"):
            pass  # solo informativo, no añadir ruido
        # Missing if __name__ == "__main__" in main entry
        if rel.endswith("main.py") and 'if __name__ == "__main__"' not in content:
            v.append(AuditViolation(
                rule="PY004", file=rel, severity="warning",
                message="main.py sin 'if __name__ == \"__main__\"' — no puede ejecutarse directamente."
            ))

    return v


def _rules_node_ts(source_dir: Path, arch: dict) -> list[AuditViolation]:
    v: list[AuditViolation] = []

    v.extend(_missing_file(source_dir, "package.json", "TS001",
        "Falta package.json — npm install no puede correr."))

    has_ts = any(_files_by_ext(source_dir, ".ts"))
    if has_ts and not (source_dir / "tsconfig.json").exists():
        v.append(AuditViolation(
            rule="TS002", file="tsconfig.json", severity="error",
            message="Proyecto TypeScript sin tsconfig.json — tsc no puede compilar."
        ))

    if not (source_dir / ".env.example").exists():
        v.append(AuditViolation(
            rule="TS003", file=".env.example", severity="warning",
            message="Falta .env.example."
        ))

    # package.json checks
    pkg_path = source_dir / "package.json"
    if pkg_path.exists():
        try:
            pkg = json.loads(_read(pkg_path))
            scripts = pkg.get("scripts", {})
            if "start" not in scripts and "dev" not in scripts:
                v.append(AuditViolation(
                    rule="TS004", file="package.json", severity="error",
                    message="package.json sin script 'start' ni 'dev' — el proyecto no se puede correr con npm."
                ))
            if "build" not in scripts and has_ts:
                v.append(AuditViolation(
                    rule="TS005", file="package.json", severity="error",
                    message="Proyecto TypeScript sin script 'build' en package.json."
                ))
        except Exception:
            v.append(AuditViolation(
                rule="TS006", file="package.json", severity="error",
                message="package.json tiene JSON inválido."
            ))

    # TS files: check for 'any' overuse
    for f in _files_by_ext(source_dir, ".ts", ".tsx"):
        content = _read(f)
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        any_count = len(re.findall(r":\s*any\b", content))
        if any_count > 5:
            v.append(AuditViolation(
                rule="TS007", file=rel, severity="warning",
                message=f"Uso excesivo de 'any' ({any_count} veces) — pierde los beneficios de TypeScript."
            ))

    return v


def _rules_react(source_dir: Path, arch: dict) -> list[AuditViolation]:
    v = _rules_node_ts(source_dir, arch)

    # Vite or CRA
    has_vite = (source_dir / "vite.config.ts").exists() or (source_dir / "vite.config.js").exists()
    has_cra = (source_dir / "react-scripts").exists()
    if not has_vite and not has_cra:
        pkg_path = source_dir / "package.json"
        if pkg_path.exists():
            try:
                pkg = json.loads(_read(pkg_path))
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "vite" not in deps and "react-scripts" not in deps:
                    v.append(AuditViolation(
                        rule="RCT001", file="package.json", severity="warning",
                        message="No se detecta bundler (Vite o CRA) — el proyecto puede no tener dev server."
                    ))
            except Exception:
                pass

    # JSX/TSX files
    for f in _files_by_ext(source_dir, ".jsx", ".tsx"):
        content = _read(f)
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        if "console.log" in content:
            v.append(AuditViolation(
                rule="RCT002", file=rel, severity="info",
                message="console.log en componente React — eliminar antes de producción."
            ))

    return v


def _rules_csharp(source_dir: Path, arch: dict) -> list[AuditViolation]:
    v: list[AuditViolation] = []

    csproj_files = list(source_dir.glob("*.csproj")) + list(source_dir.glob("**/*.csproj"))
    if not csproj_files:
        v.append(AuditViolation(
            rule="CS001", file="<proyecto>.csproj", severity="error",
            message="Falta archivo .csproj — dotnet run no puede ejecutar el proyecto."
        ))

    if not (source_dir / "appsettings.json").exists():
        v.append(AuditViolation(
            rule="CS002", file="appsettings.json", severity="error",
            message="Falta appsettings.json — configuración de la aplicación no disponible."
        ))

    # Check launchSettings.json
    ls_path = source_dir / "Properties" / "launchSettings.json"
    if not ls_path.exists():
        v.append(AuditViolation(
            rule="CS003", file="Properties/launchSettings.json", severity="warning",
            message="Falta launchSettings.json — el perfil de debug no está configurado."
        ))

    return v


def _rules_java_spring(source_dir: Path, arch: dict) -> list[AuditViolation]:
    v: list[AuditViolation] = []

    has_pom = (source_dir / "pom.xml").exists()
    has_gradle = (source_dir / "build.gradle").exists() or (source_dir / "build.gradle.kts").exists()
    if not has_pom and not has_gradle:
        v.append(AuditViolation(
            rule="JV001", file="pom.xml / build.gradle", severity="error",
            message="Falta pom.xml o build.gradle — no se puede compilar el proyecto."
        ))

    # application.properties or application.yml
    main_resources = source_dir / "src" / "main" / "resources"
    has_props = (main_resources / "application.properties").exists()
    has_yml = (main_resources / "application.yml").exists() or (main_resources / "application.yaml").exists()
    if not has_props and not has_yml:
        v.append(AuditViolation(
            rule="JV002", file="src/main/resources/application.properties", severity="error",
            message="Falta application.properties/yml — Spring Boot no puede arrancar sin configuración."
        ))

    # Main application class
    java_files = _files_by_ext(source_dir, ".java", ".kt")
    has_main = any("@SpringBootApplication" in _read(f) for f in java_files)
    if not has_main:
        v.append(AuditViolation(
            rule="JV003", file="src/main/.../Application.java", severity="error",
            message="Falta clase con @SpringBootApplication — Spring Boot no tiene entry point."
        ))

    return v


def _rules_golang(source_dir: Path, arch: dict) -> list[AuditViolation]:
    v: list[AuditViolation] = []

    v.extend(_missing_file(source_dir, "go.mod", "GO001",
        "Falta go.mod — 'go run' y 'go build' no funcionan sin módulo definido."))

    go_files = _files_by_ext(source_dir, ".go")
    has_main = any(
        re.search(r"^func main\(\)", _read(f), re.MULTILINE)
        for f in go_files
    )
    if not has_main:
        v.append(AuditViolation(
            rule="GO002", file="main.go", severity="error",
            message="No se encuentra 'func main()' — el programa no tiene entry point."
        ))

    # Error handling: check for ignored errors
    for f in go_files:
        content = _read(f)
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        if re.search(r"=\s*\w+\.\w+\(.*\)\s*\n(?!\s*if\s+err)", content):
            pass  # too noisy without proper AST parsing

    return v


def _rules_rust(source_dir: Path, arch: dict) -> list[AuditViolation]:
    v: list[AuditViolation] = []

    v.extend(_missing_file(source_dir, "Cargo.toml", "RS001",
        "Falta Cargo.toml — cargo build/run no pueden ejecutarse."))

    rust_files = _files_by_ext(source_dir, ".rs")
    has_main = any(
        re.search(r"^fn main\(\)", _read(f), re.MULTILINE)
        or re.search(r"#\[tokio::main\]", _read(f))
        for f in rust_files
    )
    if not has_main:
        v.append(AuditViolation(
            rule="RS002", file="src/main.rs", severity="error",
            message="No se encuentra 'fn main()' ni '#[tokio::main]' — sin entry point."
        ))

    # unwrap overuse
    for f in rust_files:
        content = _read(f)
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        unwrap_count = content.count(".unwrap()")
        if unwrap_count > 10:
            v.append(AuditViolation(
                rule="RS003", file=rel, severity="warning",
                message=f"Uso excesivo de .unwrap() ({unwrap_count} veces) — puede causar panic en producción. Usá '?' o match."
            ))

    return v


def _rules_php_laravel(source_dir: Path, arch: dict) -> list[AuditViolation]:
    v: list[AuditViolation] = []

    v.extend(_missing_file(source_dir, "composer.json", "PHP001",
        "Falta composer.json — composer install no puede correr."))
    v.extend(_missing_file(source_dir, ".env.example", "PHP002",
        "Falta .env.example — Laravel no puede configurar su entorno."))
    v.extend(_missing_file(source_dir, "artisan", "PHP003",
        "Falta artisan — los comandos php artisan no funcionan."))

    return v


def _rules_flutter(source_dir: Path, arch: dict) -> list[AuditViolation]:
    v: list[AuditViolation] = []

    v.extend(_missing_file(source_dir, "pubspec.yaml", "FL001",
        "Falta pubspec.yaml — 'flutter pub get' y 'flutter run' no funcionan."))
    v.extend(_missing_file(source_dir, "lib/main.dart", "FL002",
        "Falta lib/main.dart — Flutter no tiene entry point."))

    # Check main.dart has runApp
    main_dart = source_dir / "lib" / "main.dart"
    if main_dart.exists():
        content = _read(main_dart)
        if "runApp(" not in content:
            v.append(AuditViolation(
                rule="FL003", file="lib/main.dart", severity="error",
                message="main.dart no llama a runApp() — la app Flutter no arranca."
            ))
        if "void main()" not in content:
            v.append(AuditViolation(
                rule="FL004", file="lib/main.dart", severity="error",
                message="main.dart no tiene 'void main()' — sin entry point."
            ))

    # Android gradle
    android_build = source_dir / "android" / "app" / "build.gradle"
    if not android_build.exists():
        v.append(AuditViolation(
            rule="FL005", file="android/app/build.gradle", severity="error",
            message="Falta android/app/build.gradle — el build Android no puede ejecutarse."
        ))

    return v


def _rules_android(source_dir: Path, arch: dict) -> list[AuditViolation]:
    v: list[AuditViolation] = []

    v.extend(_missing_file(source_dir, "settings.gradle", "AND001",
        "Falta settings.gradle — Gradle no puede configurar el proyecto."))
    v.extend(_missing_file(source_dir, "build.gradle", "AND002",
        "Falta build.gradle raíz — Gradle build no puede correr."))

    app_manifest = source_dir / "app" / "src" / "main" / "AndroidManifest.xml"
    if not app_manifest.exists():
        v.append(AuditViolation(
            rule="AND003", file="app/src/main/AndroidManifest.xml", severity="error",
            message="Falta AndroidManifest.xml — la app Android no puede instalarse."
        ))

    app_build = source_dir / "app" / "build.gradle"
    if not app_build.exists():
        v.append(AuditViolation(
            rule="AND004", file="app/build.gradle", severity="error",
            message="Falta app/build.gradle — el módulo app no puede compilarse."
        ))

    return v


def _rules_cpp(source_dir: Path, arch: dict) -> list[AuditViolation]:
    v: list[AuditViolation] = []

    v.extend(_missing_file(source_dir, "CMakeLists.txt", "CPP001",
        "Falta CMakeLists.txt raíz — cmake no puede configurar el proyecto."))
    v.extend(_missing_file(source_dir, ".vscode/tasks.json", "CPP002",
        "Falta .vscode/tasks.json — Ctrl+Shift+B no tiene tareas de build definidas."))
    v.extend(_missing_file(source_dir, ".vscode/launch.json", "CPP003",
        "Falta .vscode/launch.json — F5 debug no está configurado."))
    v.extend(_missing_file(source_dir, ".vscode/c_cpp_properties.json", "CPP004",
        "Falta .vscode/c_cpp_properties.json — IntelliSense no resuelve headers."))

    # Check CMakeLists has target_link_libraries for Win32 if Win32 API used
    cmake = _read(source_dir / "CMakeLists.txt")
    cpp_files = _files_by_ext(source_dir, ".cpp", ".cxx", ".cc")
    uses_winapi = any("<windows.h>" in _read(f) for f in cpp_files)
    if uses_winapi and "user32" not in cmake:
        v.append(AuditViolation(
            rule="CPP005", file="CMakeLists.txt", severity="error",
            message="Código usa <windows.h> pero CMakeLists.txt no enlaza 'user32' ni 'gdi32'.",
            suggested_fix="Añadir: target_link_libraries(<target> PRIVATE user32 gdi32)"
        ))

    return v


# ─────────────────────────────────────────────── language detection + registry ──

# Map language key → (rule_fn, marker_extensions, marker_files)
LANGUAGE_RULES: dict[str, tuple[RuleFn, set[str], list[str]]] = {
    "python":      (_rules_python,      {".py"},               ["requirements.txt", "pyproject.toml", "manage.py"]),
    "node_ts":     (_rules_node_ts,     {".ts", ".js", ".mjs"}, ["package.json", "tsconfig.json"]),
    "react":       (_rules_react,       {".tsx", ".jsx"},       ["vite.config.ts", "vite.config.js"]),
    "csharp":      (_rules_csharp,      {".cs"},               []),
    "java_spring": (_rules_java_spring, {".java", ".kt"},       ["pom.xml", "build.gradle"]),
    "golang":      (_rules_golang,      {".go"},               ["go.mod"]),
    "rust":        (_rules_rust,        {".rs"},               ["Cargo.toml"]),
    "php_laravel": (_rules_php_laravel, {".php"},              ["artisan", "composer.json"]),
    "flutter":     (_rules_flutter,     {".dart"},             ["pubspec.yaml"]),
    "android":     (_rules_android,     {".kt", ".java"},      ["settings.gradle", "AndroidManifest.xml"]),
    "cpp":         (_rules_cpp,         {".cpp", ".cxx", ".cc", ".c", ".h", ".hpp"}, ["CMakeLists.txt"]),
}


# ──────────────────────────────────────────────────────── main auditor class ──

class LanguageAuditor:
    """
    Audits a generated project against language-specific rules.
    Optionally requests AI-generated fixes for found violations.
    """

    def __init__(self, gemini_driver=None, ollama_driver=None, context_builder=None, notify_fn=None):
        self.gemini = gemini_driver
        self.ollama = ollama_driver
        self.builder = context_builder
        self.notify = notify_fn or (lambda *a, **kw: None)

    def detect_language(self, source_dir: Path, architecture: dict) -> str:
        all_files = [
            f for m in architecture.get("modulos", [])
            for f in m.get("archivos_principales", [])
        ]
        all_exts = {Path(f).suffix.lower() for f in all_files}
        all_names = {Path(f).name for f in all_files}

        # Priority order matters: more specific first
        priority = ["flutter", "android", "react", "cpp", "rust", "golang",
                    "java_spring", "csharp", "php_laravel", "node_ts", "python"]

        for lang in priority:
            _, marker_exts, marker_files = LANGUAGE_RULES[lang]
            if marker_exts & all_exts:
                return lang
            if any(mf in all_names for mf in marker_files):
                return lang

        # Fallback: scan actual source directory
        if source_dir.exists():
            for lang in priority:
                _, marker_exts, _ = LANGUAGE_RULES[lang]
                if any(p.suffix.lower() in marker_exts for p in source_dir.rglob("*")
                       if p.is_file() and ".git" not in str(p)):
                    return lang

        return "unknown"

    def audit_project(self, source_dir: Path, architecture: dict, blueprint: dict) -> AuditResult:
        lang = self.detect_language(source_dir, architecture)
        result = AuditResult(language=lang)

        if lang == "unknown" or lang not in LANGUAGE_RULES:
            self.notify(f"Auditor: lenguaje no reconocido para '{source_dir.name}' — omitiendo auditoría.", "LOG", {})
            return result

        rule_fn, _, _ = LANGUAGE_RULES[lang]
        violations = rule_fn(source_dir, architecture)

        result.violations = violations

        # Score: start 100, -15 per error, -5 per warning
        error_count = sum(1 for v in violations if v.severity == "error")
        warn_count = sum(1 for v in violations if v.severity == "warning")
        result.score = max(0.0, 100.0 - error_count * 15 - warn_count * 5)
        result.passed = error_count == 0

        if violations:
            self.notify(
                f"Auditoría [{lang}]: {len(violations)} problema(s) — score {result.score:.0f}/100",
                "HEALTH_WARN" if not result.passed else "LOG",
                {"audit": result.to_dict()},
            )
            for v in violations:
                level = "❌" if v.severity == "error" else "⚠️"
                print(f"  [{v.rule}] {level} {v.file}: {v.message}")
        else:
            self.notify(f"Auditoría [{lang}]: OK — score 100/100", "LOG", {})
            print(f"  [AUDIT] {lang}: sin problemas detectados.")

        return result

    async def request_ai_fix(
        self,
        result: AuditResult,
        source_dir: Path,
        project_description: str,
        architecture: dict,
    ) -> list[dict]:
        if not result.violations:
            return []
        if not self.gemini and not self.gemini:
            return []

        violations_text = "\n".join(
            f"  [{v.rule}] {v.severity.upper()} en '{v.file}': {v.message}"
            + (f"\n    Sugerencia: {v.suggested_fix}" if v.suggested_fix else "")
            for v in result.violations
            if v.severity in ("error", "warning")
        )

        sources = self._collect_relevant_files(source_dir, result.violations)

        task = (
            f"PROYECTO: {project_description}\n\n"
            f"LENGUAJE/STACK: {result.language}\n\n"
            f"VIOLACIONES DE AUDITORÍA:\n{violations_text}\n\n"
            f"ARCHIVOS RELEVANTES:\n{sources}\n\n"
            f"Generá los archivos corregidos o faltantes para resolver TODAS las violaciones. "
            f"Respondé con un JSON array: "
            f'[{{"file": "ruta/relativa", "code": "contenido completo", "reason": "qué resuelve"}}]'
        )

        for driver, provider in [(self.gemini, "gemini"), (self.ollama, "ollama")]:
            if driver is None:
                continue
            try:
                payload = self.builder.build_payload(provider, "code_fixer", task)
                response = (await driver.call(payload["system"], payload["user"])).content
                fixes = self._parse_fix_response(response)
                if fixes:
                    result.ai_fixes = fixes
                    self.notify(
                        f"Auditor IA [{result.language}]: {len(fixes)} archivo(s) corregido(s).",
                        "LOG", {"fixes": [f["file"] for f in fixes]},
                    )
                    return fixes
            except Exception as e:
                self.notify(f"Auditor IA error: {e}", "LOG", {})
                continue

        return []

    def _collect_relevant_files(self, source_dir: Path, violations: list[AuditViolation]) -> str:
        relevant_files = {v.file for v in violations}
        parts = []
        for rel in list(relevant_files)[:10]:
            p = source_dir / rel
            if p.exists():
                content = p.read_text(encoding="utf-8", errors="ignore")[:3000]
                parts.append(f"### {rel}\n{content}")
        return "\n\n".join(parts) if parts else "(archivos aún no generados)"

    @staticmethod
    def _parse_fix_response(response: str) -> list[dict]:
        for pattern in [
            r"\[.*\]",                          # bare array
            r"```(?:json)?\s*(\[.*?\])\s*```",  # fenced
        ]:
            for m in re.finditer(pattern, response, re.DOTALL):
                try:
                    data = json.loads(m.group(0) if "[" in m.group(0)[:2] else m.group(1))
                    if isinstance(data, list):
                        return [f for f in data if f.get("file") and f.get("code")]
                except Exception:
                    continue
        return []
