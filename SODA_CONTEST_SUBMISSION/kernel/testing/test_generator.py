"""
TestGenerator — generates contract-based unit/integration tests for each module post-DEV.

Uses master_contract typed interfaces to guarantee at least one test per public method.
Falls back to source-code heuristics when no contract is available.

Supports:
  Python  → pytest
  Node/TS → Jest / Vitest
  Go      → go test
  Java    → JUnit 5
  C#      → xUnit
  Rust    → built-in #[test]
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable


@dataclass
class GeneratedTest:
    filepath: str        # relative path (e.g. tests/test_auth.py)
    content: str
    module_name: str
    framework: str       # pytest | jest | go_test | junit | xunit | rust_test

    def to_dict(self) -> dict:
        return {
            "filepath": self.filepath,
            "module_name": self.module_name,
            "framework": self.framework,
            "lines": len(self.content.splitlines()),
        }


@dataclass
class TestGenerationReport:
    generated: list[GeneratedTest] = field(default_factory=list)
    skipped_modules: list[str] = field(default_factory=list)
    framework: str = ""
    total_test_files: int = 0

    def to_dict(self) -> dict:
        return {
            "framework": self.framework,
            "total_test_files": self.total_test_files,
            "generated_modules": [t.module_name for t in self.generated],
            "skipped_modules": self.skipped_modules,
        }


# ─────────────────────────────── framework detection ──

def _detect_framework(architecture: dict, source_dir: Path) -> str:
    all_files = [
        f for m in architecture.get("modulos", [])
        for f in m.get("archivos_principales", [])
    ]
    exts = {Path(f).suffix.lower() for f in all_files}
    names = {Path(f).name for f in all_files}

    if ".py" in exts or "requirements.txt" in names or "pyproject.toml" in names:
        return "pytest"
    if ".go" in exts or "go.mod" in names:
        return "go_test"
    if ".java" in exts or "pom.xml" in names:
        return "junit"
    if ".cs" in exts:
        return "xunit"
    if ".rs" in exts or "Cargo.toml" in names:
        return "rust_test"
    if ".tsx" in exts or ".jsx" in exts or ".ts" in exts:
        return "jest"
    if ".js" in exts or "package.json" in names:
        return "jest"

    # Fallback: scan disk
    if source_dir.exists():
        if any(source_dir.rglob("*.py")):
            return "pytest"
        if any(source_dir.rglob("*.go")):
            return "go_test"
        if any(source_dir.rglob("*.ts")) or any(source_dir.rglob("*.tsx")):
            return "jest"

    return "pytest"  # safe default


# ─────────────────────────────── test file path helpers ──

def _test_path_for(module_name: str, framework: str, source_files: list[str]) -> str:
    safe = module_name.lower().replace(" ", "_").replace("-", "_")
    if framework == "pytest":
        return f"tests/test_{safe}.py"
    if framework == "jest":
        first = source_files[0] if source_files else ""
        base = Path(first).parent if first else Path("src")
        return f"{base}/__tests__/{safe}.test.ts"
    if framework == "go_test":
        first = source_files[0] if source_files else "main.go"
        pkg_dir = str(Path(first).parent)
        return f"{pkg_dir}/{safe}_test.go"
    if framework == "junit":
        return f"src/test/java/{safe.capitalize()}Test.java"
    if framework == "xunit":
        return f"Tests/{safe.capitalize()}Tests.cs"
    if framework == "rust_test":
        return f"src/{safe}_tests.rs"
    return f"tests/test_{safe}.py"


# ─────────────────────────────── contract helpers ──

def _build_contract_block(typed_module: dict) -> str:
    """Serialize the typed module's interfaces into a compact XML-ish block for the prompt."""
    lines: list[str] = []
    mod_id = typed_module.get("id") or typed_module.get("nombre", "?")
    lines.append(f"Módulo: {mod_id}")

    interfaces = typed_module.get("interfaces", [])
    if interfaces:
        lines.append("Interfaces obligatorias (DEBES testear cada una):")
        for iface in interfaces:
            name = iface.get("name", "")
            params = iface.get("parameters", {})
            returns = iface.get("returns", "")
            description = iface.get("description", "")
            params_str = ", ".join(f"{k}: {v}" for k, v in params.items()) if isinstance(params, dict) else str(params)
            sig = f"  {name}({params_str}) -> {returns}"
            if description:
                sig += f"  # {description}"
            lines.append(sig)

    data_types = typed_module.get("data_types_used_inline", [])
    if data_types:
        lines.append("Tipos de datos relacionados:")
        for dt in data_types:
            if not isinstance(dt, dict):
                continue
            fields = dt.get("fields", {})
            lines.append(f"  {dt.get('name', '?')}: {{{', '.join(f'{k}: {v}' for k, v in fields.items())}}}")

    return "\n".join(lines)


def _lookup_typed_module(module: dict, master_contract: dict) -> dict | None:
    """Find the master_contract module entry matching this architecture module."""
    mc_modules = master_contract.get("modules", [])
    mod_id = module.get("id") or module.get("nombre", "")
    mod_files = set(module.get("archivos_principales", []))

    # 1. Match by id
    for mc_mod in mc_modules:
        if not isinstance(mc_mod, dict):
            continue
        if mc_mod.get("id") == mod_id or mc_mod.get("nombre") == mod_id:
            return mc_mod

    # 2. Match by shared source files
    for mc_mod in mc_modules:
        if not isinstance(mc_mod, dict):
            continue
        mc_files = set(mc_mod.get("archivos_principales", []))
        if mod_files & mc_files:
            return mc_mod

    return None


# ─────────────────────────────── prompt builders ──

FRAMEWORK_SYSTEM_HINTS = {
    "pytest": (
        "Generás tests con pytest. Usá fixtures, assert directo (no unittest), "
        "y mocks con pytest-mock cuando sea necesario. Cubrí happy path y al menos un error path por función pública. "
        "Si el módulo tiene endpoints FastAPI, usá TestClient de starlette."
    ),
    "jest": (
        "Generás tests con Jest/Vitest en TypeScript. Usá describe/it, expect, y vi.mock() o jest.mock() "
        "para dependencias externas. Cubrí happy path y error paths. "
        "Para componentes React usá @testing-library/react."
    ),
    "go_test": (
        "Generás tests en Go con el paquete testing estándar. Usá t.Run para subtests, "
        "testify/assert si está disponible, y table-driven tests donde aplique."
    ),
    "junit": (
        "Generás tests con JUnit 5 (@Test, @BeforeEach, Assertions.*). "
        "Usá Mockito para mocks. Cubrí happy path y excepciones."
    ),
    "xunit": (
        "Generás tests con xUnit en C#. Usá [Fact] y [Theory], Moq para mocks. "
        "Cubrí happy path y casos de error."
    ),
    "rust_test": (
        "Generás tests Rust con #[test] y #[cfg(test)]. "
        "Usá assert_eq!, assert!, y Result<_, _> donde aplique."
    ),
}


def _build_test_prompt(
    module: dict,
    source_code: dict[str, str],
    framework: str,
    blueprint: dict,
    typed_module: dict | None = None,
) -> str:
    stack = blueprint.get("stack_sugerido", {})
    code_sections = "\n\n".join(
        f"### {fp}\n```\n{content[:3000]}\n```"
        for fp, content in source_code.items()
        if content.strip()
    )
    hint = FRAMEWORK_SYSTEM_HINTS.get(framework, "")

    if typed_module and typed_module.get("interfaces"):
        contract_block = _build_contract_block(typed_module)
        return (
            f"MÓDULO: {module.get('id') or module.get('nombre', '')}\n"
            f"RESPONSABILIDAD: {module.get('responsabilidad', '')}\n"
            f"STACK: {json.dumps(stack, ensure_ascii=False)}\n\n"
            f"<contrato_del_modulo>\n{contract_block}\n</contrato_del_modulo>\n\n"
            f"CÓDIGO FUENTE DEL MÓDULO:\n{code_sections}\n\n"
            f"INSTRUCCIONES DE TEST:\n{hint}\n\n"
            f"OBLIGATORIO: Genera al menos un test por cada método listado en <contrato_del_modulo>. "
            f"Usá los nombres exactos de funciones/clases/endpoints del contrato. "
            f"Solo el código del archivo de tests, sin explicaciones ni markdown."
        )

    # Fallback: source-code heuristics (no contract)
    return (
        f"MÓDULO: {module.get('id') or module.get('nombre', '')}\n"
        f"RESPONSABILIDAD: {module.get('responsabilidad', '')}\n"
        f"STACK: {json.dumps(stack, ensure_ascii=False)}\n\n"
        f"CÓDIGO FUENTE DEL MÓDULO:\n{code_sections}\n\n"
        f"INSTRUCCIONES DE TEST:\n{hint}\n\n"
        f"Generá el archivo de tests completo y ejecutable para este módulo. "
        f"Usá los nombres exactos de funciones/clases/endpoints que aparecen en el código fuente. "
        f"Solo el código del archivo de tests, sin explicaciones ni markdown."
    )


# ─────────────────────────────── main class ──

class TestGenerator:
    """
    Generates contract-based test files for each module using the master_contract
    typed interfaces as the source of truth. Falls back to source-code heuristics
    when no contract is available.
    """

    def __init__(self, ollama_driver, context_builder, notify_fn: Optional[Callable] = None):
        self.ollama = ollama_driver
        self.gemini = gemini_driver
        self.builder = builder
        self.notify = notify_fn

    async def generate_for_project(
        self,
        source_dir: Path,
        architecture: dict,
        blueprint: dict,
        module_generated_code: dict[str, dict[str, str]],
        master_contract: dict | None = None,
    ) -> TestGenerationReport:
        """
        Generate tests for all modules that have generated code.
        module_generated_code: {module_name: {filepath: content}}
        master_contract: typed interface contract (master_contract.json) — optional
        """
        framework = _detect_framework(architecture, source_dir)
        report = TestGenerationReport(framework=framework)

        contract_note = " (con contrato tipado)" if master_contract else " (sin contrato — heurístico)"
        self.notify(
            f"TestGenerator: generando tests [{framework}]{contract_note} para {len(module_generated_code)} módulo(s).",
            "PHASE_START",
            {"phase": "test_generation", "framework": framework},
        )

        for module in architecture.get("modulos", []):
            nombre = module.get("nombre", "")
            mod_id = module.get("id") or nombre
            source_files = module.get("archivos_principales", [])

            # Skip infrastructure/build modules — they have no logic to test
            if any(kw in nombre.lower() for kw in ("infraestructura", "build", "config", "dockerfile", "migrations")):
                report.skipped_modules.append(mod_id)
                continue

            source_code = module_generated_code.get(nombre, {}) or module_generated_code.get(mod_id, {})
            if not source_code:
                source_code = {}
                for fp in source_files:
                    fpath = source_dir / fp
                    if fpath.exists():
                        try:
                            source_code[fp] = fpath.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            pass

            if not source_code:
                report.skipped_modules.append(mod_id)
                continue

            typed_module = _lookup_typed_module(module, master_contract) if master_contract else None

            test_path = _test_path_for(mod_id, framework, source_files)
            contract_flag = " [contrato]" if typed_module else ""
            self.notify(f"TestGenerator: generando {test_path}{contract_flag}", "LOG", {"module": mod_id})

            try:
                test_content = await self._generate_test_file(module, source_code, framework, blueprint, typed_module)
            except Exception as e:
                self.notify(f"TestGenerator: error en módulo {mod_id}: {e}", "LOG", {})
                report.skipped_modules.append(mod_id)
                continue

            if not test_content or len(test_content.strip()) < 50:
                report.skipped_modules.append(mod_id)
                continue

            out = source_dir / test_path
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(test_content, encoding="utf-8")

            generated = GeneratedTest(
                filepath=test_path,
                content=test_content,
                module_name=mod_id,
                framework=framework,
            )
            report.generated.append(generated)
            self.notify(
                f"Test generado: {test_path}",
                "FILE_GENERATED",
                {"filename": test_path, "code": test_content, "validated": False, "phase": "test_generation"},
            )

        self._ensure_test_config(source_dir, framework, blueprint)

        report.total_test_files = len(report.generated)
        self.notify(
            f"TestGenerator: {report.total_test_files} archivo(s) de test generados. "
            f"{len(report.skipped_modules)} módulo(s) omitidos.",
            "CHECKPOINT",
            report.to_dict(),
        )
        return report

    async def _generate_test_file(
        self,
        module: dict,
        source_code: dict[str, str],
        framework: str,
        blueprint: dict,
        typed_module: dict | None = None,
    ) -> str:
        prompt = _build_test_prompt(module, source_code, framework, blueprint, typed_module)

        # Use test_engineer prompt template when a contract is available; fall back to code_generator
        template = "test_engineer" if typed_module else "code_generator"
        system = FRAMEWORK_SYSTEM_HINTS.get(framework, "Generás tests de software.")

        # Try Qwen first (fast), escalate to Gemini on failure
        try:
            payload = self.builder.build_payload("ollama", template, prompt)
            raw = await self.ollama.prompt(system, payload["user"])
            if raw and not raw.startswith("ERROR:") and len(raw.strip()) > 100:
                return self._strip_fence(raw)
        except Exception:
            pass

        # Gemini escalation — always use test_engineer template for quality
        payload = self.builder.build_payload("gemini", "test_engineer", prompt)
        raw = await self.gemini.prompt(payload.get("system", system), payload["user"])
        return self._strip_fence(raw or "")

    @staticmethod
    def _strip_fence(code: str) -> str:
        lines = code.strip().splitlines()
        if not lines:
            return code
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)

    def _ensure_test_config(self, source_dir: Path, framework: str, blueprint: dict) -> None:
        """Create minimal test runner config if missing."""
        if framework == "pytest":
            cfg = source_dir / "pytest.ini"
            if not cfg.exists():
                cfg.write_text(
                    "[pytest]\ntestpaths = tests\npython_files = test_*.py\npython_classes = Test*\npython_functions = test_*\n",
                    encoding="utf-8",
                )
        elif framework == "jest":
            pkg = source_dir / "package.json"
            if pkg.exists():
                try:
                    import json as _json
                    data = _json.loads(pkg.read_text(encoding="utf-8"))
                    scripts = data.setdefault("scripts", {})
                    if "test" not in scripts:
                        scripts["test"] = "jest --coverage"
                        devdeps = data.setdefault("devDependencies", {})
                        for pkg_name in ("jest", "@types/jest", "ts-jest"):
                            devdeps.setdefault(pkg_name, "*")
                        pkg.write_text(_json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass
        elif framework == "go_test":
            pass  # go test is built-in, no config needed
