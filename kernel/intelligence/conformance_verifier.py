"""ConformanceVerifier — uses Claude Haiku to check and fix generated files against contracts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from kernel.monitoring.performance_tracker import PerformanceTracker

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "claude" / "conformance_verifier.md"
_MAX_CONTENT_CHARS = 8_000
_CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".cs", ".rb", ".php"}


class ConformanceVerifier:
    """Verifies each generated module against its contract and fixes non-conformances with Haiku.

    Reads generated source files, sends them to Haiku alongside the module contract,
    and overwrites any file Haiku determines needs correction.
    """

    def __init__(self, claude_driver, tracker: Optional["PerformanceTracker"] = None) -> None:
        self.driver = claude_driver
        self.tracker = tracker
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def verify_project(self, architecture: dict, source_dir: Path) -> dict:
        """Verify all modules in the architecture against their generated files.

        Returns a summary dict with counts of checked, fixed, and skipped modules.
        """
        modules = architecture.get("modulos", [])
        if not modules:
            print("  [VERIFY] No hay módulos en la arquitectura para verificar.")
            return {"checked": 0, "fixed": 0, "skipped": 0}

        print(f"\n[FASE 4.V] Conformance Verify — {len(modules)} módulo(s) con Claude Haiku...")
        checked = fixed = skipped = 0

        for module in modules:
            nombre = module.get("nombre", "?")
            result = await self._verify_module(module, source_dir)

            if result["skipped"]:
                skipped += 1
                print(f"  [VERIFY] {nombre}: saltado (sin archivo)")
            elif result["fixed"]:
                fixed += 1
                print(f"  [VERIFY] {nombre}: corregido ✓")
            else:
                checked += 1
                print(f"  [VERIFY] {nombre}: conforme ✓")

        total = checked + fixed + skipped
        print(
            f"  [VERIFY] Resultado: {checked} conformes, {fixed} corregidos, {skipped} saltados "
            f"de {total} módulos."
        )
        return {"checked": checked, "fixed": fixed, "skipped": skipped}

    async def _verify_module(self, module: dict, source_dir: Path) -> dict:
        nombre = module.get("nombre", "unknown")
        archivos = module.get("archivos", [])

        if not archivos:
            archivos = self._find_files_by_name(nombre, source_dir)

        if not archivos:
            if self.tracker:
                self.tracker.record_conformance(fixed=False, skipped=True)
            return {"module": nombre, "fixed": False, "skipped": True}

        files_processed = 0
        any_fixed = False
        for filepath in archivos:
            fixed = await self._verify_file(module, filepath, source_dir)
            if fixed is None:  # file not found
                continue
            files_processed += 1
            if fixed:
                any_fixed = True

        if files_processed == 0:
            if self.tracker:
                self.tracker.record_conformance(fixed=False, skipped=True)
            return {"module": nombre, "fixed": False, "skipped": True}

        if self.tracker:
            self.tracker.record_conformance(fixed=any_fixed, skipped=False)
        return {"module": nombre, "fixed": any_fixed, "skipped": False}

    async def _verify_file(self, module: dict, filepath: str, source_dir: Path):
        """Returns True if fixed, False if compliant, None if file not found."""
        full_path = self._resolve_path(filepath, source_dir)
        if full_path is None or not full_path.exists():
            return None

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False

        if len(content) > _MAX_CONTENT_CHARS:
            content = content[:_MAX_CONTENT_CHARS] + "\n...[truncado por tamaño]"

        contract_json = json.dumps(
            {
                "nombre":      module.get("nombre"),
                "descripcion": module.get("descripcion", ""),
                "interfaces":  module.get("interfaces", []),
                "archivos":    module.get("archivos", []),
            },
            indent=2,
            ensure_ascii=False,
        )

        user_message = (
            f"## Contrato del módulo\n```json\n{contract_json}\n```\n\n"
            f"## Archivo generado: {filepath}\n{content}\n\n"
            "¿El archivo implementa correctamente el contrato? "
            "Si cumple, respondé exactamente `COMPLIANT`. "
            "Si no, respondé con el contenido corregido del archivo."
        )

        response = await self.driver.call(
            system_prompt=self._system_prompt,
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
        except OSError:
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
