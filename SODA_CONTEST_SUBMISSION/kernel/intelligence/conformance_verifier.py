"""ConformanceVerifier — uses Gemini Haiku to check and fix generated files against contracts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from kernel.monitoring.performance_tracker import PerformanceTracker

_HAIKU_MODEL = "gemini-3-flash-preview"
_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "gemini" / "conformance_verifier.md"
_MAX_CONTENT_CHARS = 8_000
_CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".cs", ".rb", ".php"}


class ConformanceVerifier:
    """Verifies each generated module against its contract and fixes non-conformances with Haiku.

    Reads generated source files, sends them to Haiku alongside the module contract,
    and overwrites any file Haiku determines needs correction.
    """

    def __init__(self, gemini_driver, tracker: Optional["PerformanceTracker"] = None, notify_fn=None) -> None:
        self.driver = gemini_driver
        self.tracker = tracker
        self._notify = notify_fn or (lambda msg, t, d: None)
        self._system_prompt: Optional[str] = None  # loaded lazily on first use

    def _load_prompt(self) -> str:
        if self._system_prompt is None:
            if not _PROMPT_PATH.exists():
                raise FileNotFoundError(
                    f"ConformanceVerifier: prompt no encontrado en {_PROMPT_PATH}. "
                    "Verificá que prompts/gemini/conformance_verifier.md exista."
                )
            self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        return self._system_prompt

    @staticmethod
    def _missing_python_signatures(content: str, interfaces: list[dict]) -> list[str]:
        """AST-based check: return interface names not defined in the Python source (PASO 1)."""
        import ast
        if not interfaces:
            return []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []
        defined: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.add(node.name)
        required = {iface.get("name", "") for iface in interfaces if iface.get("name")}
        return sorted(required - defined)

    async def verify_project(
        self,
        architecture: dict,
        source_dir: Path,
        master_contract: Optional[dict] = None,
        topology: Optional[dict] = None,
    ) -> dict:
        """Verify all modules against their generated files.

        Uses topology.json (archivos_principales) and master_contract.json (typed interfaces)
        as ground truth when available, falling back to legacy architecture.json fields.

        Returns a summary dict with counts of checked, fixed, and skipped modules.
        """
        # PASO 1: prefer topology modules (v2 IDs + archivos_principales) over legacy arch
        modules = (topology or {}).get("modulos") or architecture.get("modulos", [])
        if not modules:
            print("  [VERIFY] No hay módulos para verificar.")
            return {"checked": 0, "fixed": 0, "skipped": 0}

        # Build master_contract lookup by module ID for typed interfaces
        _contract_by_id: dict[str, dict] = {}
        if master_contract:
            for m in master_contract.get("modules", []):
                if isinstance(m, dict) and m.get("id"):
                    _contract_by_id[m["id"]] = m

        print(f"\n[FASE 4.V] Conformance Verify — {len(modules)} módulo(s) con Gemini Haiku...")
        checked = fixed = skipped = 0

        for module in modules:
            mod_id = module.get("id") or module.get("nombre", "?")
            typed_mod = _contract_by_id.get(mod_id)
            result = await self._verify_module(module, source_dir, typed_mod)

            if result["skipped"]:
                skipped += 1
                print(f"  [VERIFY] {mod_id}: saltado (sin archivo)")
            elif result["fixed"]:
                fixed += 1
                print(f"  [VERIFY] {mod_id}: corregido ✓")
            else:
                checked += 1
                print(f"  [VERIFY] {mod_id}: conforme ✓")

        total = checked + fixed + skipped
        print(
            f"  [VERIFY] Resultado: {checked} conformes, {fixed} corregidos, {skipped} saltados "
            f"de {total} módulos."
        )
        return {"checked": checked, "fixed": fixed, "skipped": skipped}

    async def _verify_module(self, module: dict, source_dir: Path, typed_mod: Optional[dict] = None) -> dict:
        mod_id = module.get("id") or module.get("nombre", "unknown")
        # PASO 2: use archivos_principales (topology v2) with fallback to archivos (legacy)
        archivos = module.get("archivos_principales", []) or module.get("archivos", [])

        if not archivos:
            archivos = self._find_files_by_name(mod_id, source_dir)

        if not archivos:
            if self.tracker:
                self.tracker.record_conformance(fixed=False, skipped=True)
            return {"module": mod_id, "fixed": False, "skipped": True}

        files_processed = 0
        any_fixed = False
        for filepath in archivos:
            fixed = await self._verify_file(module, filepath, source_dir, typed_mod)
            if fixed is None:  # file not found
                continue
            files_processed += 1
            if fixed:
                any_fixed = True

        if files_processed == 0:
            if self.tracker:
                self.tracker.record_conformance(fixed=False, skipped=True)
            return {"module": mod_id, "fixed": False, "skipped": True}

        if self.tracker:
            self.tracker.record_conformance(fixed=any_fixed, skipped=False)
        return {"module": mod_id, "fixed": any_fixed, "skipped": False}

    async def _verify_file(self, module: dict, filepath: str, source_dir: Path, typed_mod: Optional[dict] = None):
        """Returns True if fixed, False if compliant, None if file not found."""
        full_path = self._resolve_path(filepath, source_dir)
        if full_path is None or not full_path.exists():
            return None

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            self._notify(
                f"ConformanceVerifier: no se pudo leer {filepath}: {e}",
                "HEALTH_WARN",
                {"phase": "conformance_verify", "file": filepath, "error": str(e)},
            )
            return False

        if len(content) > _MAX_CONTENT_CHARS:
            content = content[:_MAX_CONTENT_CHARS] + "\n...[truncado por tamaño]"

        # PASO 1: enrich contract with typed interfaces from master_contract when available
        typed_interfaces = (typed_mod or {}).get("interfaces", []) or module.get("interfaces", [])
        mod_id = module.get("id") or module.get("nombre")
        contract_json = json.dumps(
            {
                "modulo_id":   mod_id,
                "descripcion": (typed_mod or module).get("descripcion", ""),
                "interfaces":  typed_interfaces,
                "archivos_principales": module.get("archivos_principales", []) or module.get("archivos", []),
            },
            indent=2,
            ensure_ascii=False,
        )

        # PASO 1: static AST pre-check for Python — report missing signatures upfront
        missing_sigs: list[str] = []
        if filepath.endswith(".py") and typed_interfaces:
            missing_sigs = self._missing_python_signatures(content, typed_interfaces)

        pre_check_note = ""
        if missing_sigs:
            pre_check_note = (
                f"\n\n⚠️ ANÁLISIS ESTÁTICO: las siguientes interfaces del contrato "
                f"NO están definidas en el archivo: {', '.join(missing_sigs)}. "
                "Debes implementarlas en el código corregido."
            )

        user_message = (
            f"## Contrato del módulo\n```json\n{contract_json}\n```\n\n"
            f"## Archivo generado: {filepath}\n{content}"
            f"{pre_check_note}\n\n"
            "¿El archivo implementa correctamente el contrato? "
            "Si cumple, respondé exactamente `COMPLIANT`. "
            "Si no, respondé con el contenido corregido del archivo."
        )

        response = await self.driver.call(
            system_prompt=self._load_prompt(),
            user_message=user_message,
            model=_HAIKU_MODEL,
            max_tokens=4096,
            temperature=0.1,
            metadata={
                "phase": "conformance_verify",
                "module": module.get("nombre", ""),
                "file": filepath,
            },
        )

        if response.error_code:
            self._notify(
                f"ConformanceVerifier: Haiku error en {filepath} (módulo: {module.get('nombre', '?')}): {response.error_code}",
                "HEALTH_WARN",
                {"phase": "conformance_verify", "file": filepath, "module": module.get("nombre"), "error_code": response.error_code},
            )
            return False

        corrected = response.content.strip()

        if corrected.upper().startswith("COMPLIANT"):
            return False

        # Strip accidental markdown fences
        if corrected.startswith("```"):
            lines = corrected.splitlines()
            start, end = 1, len(lines)
            for i in range(len(lines) - 1, 0, -1):
                if lines[i].strip().startswith("```"):
                    end = i
                    break
            corrected = "\n".join(lines[start:end])

        if not corrected.endswith("\n"):
            corrected += "\n"

        try:
            full_path.write_text(corrected, encoding="utf-8")
        except OSError as e:
            self._notify(
                f"ConformanceVerifier: no se pudo escribir {filepath}: {e}",
                "HEALTH_WARN",
                {"phase": "conformance_verify", "file": filepath, "error": str(e)},
            )
            return False
        return True

    def _resolve_path(self, filepath: str, source_dir: Path) -> Optional[Path]:
        """Resolve a relative filepath to an absolute path within source_dir."""
        candidate = source_dir / filepath
        if candidate.exists():
            return candidate
        # Try just the filename
        fname = Path(filepath).name
        hits = list(source_dir.rglob(fname))
        return hits[0] if hits else None

    def _find_files_by_name(self, module_name: str, source_dir: Path) -> list[str]:
        """Heuristic: find code files whose stem contains a part of the module name."""
        if not source_dir.exists():
            return []
        parts = [p for p in module_name.lower().split("_") if len(p) > 2]
        results: list[str] = []
        for f in source_dir.rglob("*"):
            if f.is_file() and f.suffix in _CODE_EXTENSIONS:
                stem = f.stem.lower()
                if any(part in stem for part in parts):
                    results.append(str(f.relative_to(source_dir)))
        return results[:3]
