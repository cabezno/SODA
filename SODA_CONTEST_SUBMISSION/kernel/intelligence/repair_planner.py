"""
RepairPlanner — genera un plan de corrección inteligente cuando el proyecto
no arranca tras múltiples intentos del BootAgent.

Problema que resuelve:
    El fixer del BootAgent ataca errores de a uno sin visión global.
    Cuando hay múltiples errores interdependientes (módulo A usa símbolo
    de módulo B que cambió de nombre, más un schema de DB inconsistente,
    más un endpoint mal exportado), el fixer convencional falla en ciclos.

Solución:
    RepairPlanner recibe TODOS los artefactos de diagnóstico disponibles:
    - boot_report.json  → errores de instalación y runtime
    - smoke_results.json → tests que fallan con HTTP status reales
    - db_schema_map.json → schema canónico esperado

    Hace UNA llamada a Claude Sonnet (el modelo más capaz del lineup)
    y genera un repair plan: lista ordenada de archivos + instrucción
    específica por archivo. El plan se guarda como repair_plan.json.

    El BootAgent luego ejecuta el plan en orden, un archivo por vez.

Uso:
    planner = RepairPlanner(claude_driver, notify_fn)
    plan = await planner.plan(workspace_path)
    # Genera workspace/repair_plan.json
    # Retorna lista de {"file": str, "issue": str, "fix_instruction": str}
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, List, Optional


_SYSTEM_PROMPT = """\
You are SODA's Repair Architect. A generated software project is failing to start.
You have access to boot errors, smoke test failures, and the canonical DB schema.

Your job: produce a precise repair plan — an ordered list of files to fix with
specific, actionable instructions for each. Fix root causes, not symptoms.
Order by dependency: fix imported modules before their importers.

Rules:
- Only include files that actually need changes.
- Be specific: "add export keyword to function processOrder on line ~45" NOT "fix the file".
- If a DB schema mismatch is the root cause, say which column is wrong and what it should be.
- If a missing export causes multiple failures, list it first.
- Maximum 10 items in the plan.

Respond ONLY with valid JSON. No markdown, no explanation outside the JSON.

Response format:
[
  {
    "file": "relative/path/to/file.ts",
    "issue": "one-line description of the problem",
    "fix_instruction": "precise instruction for the fixer LLM"
  }
]
"""


class RepairPlanner:
    def __init__(
        self,
        ai_driver,
        notify_fn: Optional[Callable[[str, str], None]] = None,
    ):
        """
        ai_driver: preferentemente Claude Sonnet para máxima calidad del plan.
        Si no está disponible, usa el driver que se provea (Gemini, etc.).
        """
        self.driver = ai_driver
        self.notify = notify_fn or (lambda msg, lvl="LOG", *a, **kw: None)

    def _notify(self, msg: str, level: str = "LOG") -> None:
        try:
            self.notify(level, msg)
        except Exception:
            pass

    def _load_boot_errors(self, workspace: Path) -> str:
        """Extract last 3 errors from boot_report.json."""
        path = workspace / "boot_report.json"
        if not path.exists():
            return ""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            attempts = data.get("attempts", [])
            if not attempts:
                return ""
            last = attempts[-1]
            errors = last.get("errors", [])[:5]
            lines = [f"  [{e.get('error_type', 'error')}] {e.get('message', '')}" for e in errors]
            boot_out = (last.get("boot_output") or "")[-800:]
            if boot_out:
                lines.append(f"\nLast boot output (tail):\n{boot_out}")
            return "\n".join(lines)
        except Exception:
            return ""

    def _load_smoke_failures(self, workspace: Path) -> str:
        """Extract failed smoke tests from smoke_results.json."""
        path = workspace / "smoke_results.json"
        if not path.exists():
            return ""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            results = data.get("results", [])
            failed = [r for r in results if not r.get("passed", True)]
            if not failed:
                return ""
            lines = [
                f"  {r['method']} {r['url']} → HTTP {r['status_code']} ({r.get('reason', '')})"
                for r in failed
            ]
            return "\n".join(lines)
        except Exception:
            return ""

    def _load_db_schema(self, workspace: Path) -> str:
        """Load canonical DB schema summary."""
        path = workspace / "db_schema_map.json"
        if not path.exists():
            return ""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            tables = data.get("tables", {})
            if not tables:
                return ""
            lines = []
            for tname, tinfo in list(tables.items())[:6]:  # max 6 tables
                cols = ", ".join(
                    f"{col}: {typ}" for col, typ in list((tinfo.get("columns") or {}).items())[:6]
                )
                lines.append(f"  {tname} ({cols})")
            return "\n".join(lines)
        except Exception:
            return ""

    def _collect_source_snippet(self, workspace: Path, max_files: int = 5) -> str:
        """
        Collect a short snippet from the most recently modified source files
        to give the LLM context about what was actually generated.
        """
        source_dir = workspace / "source"
        if not source_dir.exists():
            return ""

        candidates = sorted(
            [f for f in source_dir.rglob("*") if f.is_file() and f.suffix in
             {".py", ".ts", ".js", ".tsx", ".jsx"}],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )[:max_files]

        snippets = []
        for f in candidates:
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
                rel = str(f.relative_to(workspace))
                # First 30 lines only
                preview = "\n".join(text.splitlines()[:30])
                snippets.append(f"--- {rel} (first 30 lines) ---\n{preview}")
            except Exception:
                pass

        return "\n\n".join(snippets)

    async def plan(self, workspace: Path) -> List[dict]:
        """
        Genera repair_plan.json en el workspace.
        Retorna lista de {"file": str, "issue": str, "fix_instruction": str}.
        Retorna [] si no hay errores o si falla.
        """
        boot_errors = self._load_boot_errors(workspace)
        smoke_failures = self._load_smoke_failures(workspace)
        db_schema = self._load_db_schema(workspace)
        source_snippet = self._collect_source_snippet(workspace)

        if not boot_errors and not smoke_failures:
            self._notify("[RepairPlanner] No hay errores registrados — nada que planificar.", "LOG")
            return []

        self._notify("[RepairPlanner] Generando plan de reparación con Claude Sonnet...", "LOG")

        sections = []
        if boot_errors:
            sections.append(f"BOOT ERRORS:\n{boot_errors}")
        if smoke_failures:
            sections.append(f"SMOKE TEST FAILURES:\n{smoke_failures}")
        if db_schema:
            sections.append(f"CANONICAL DB SCHEMA (expected table structure):\n{db_schema}")
        if source_snippet:
            sections.append(f"GENERATED SOURCE FILES (for context):\n{source_snippet}")

        user_msg = (
            "The following project is failing. Analyze all errors and produce "
            "an ordered repair plan.\n\n" + "\n\n".join(sections)
        )

        try:
            resp = await self.driver.call(
                system_prompt=_SYSTEM_PROMPT,
                user_message=user_msg,
                model=None,
                temperature=0.1,
            )

            raw = resp.content if resp else ""
            raw = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
            raw = re.sub(r'\s*```$', '', raw.strip(), flags=re.MULTILINE)

            m = re.search(r'\[.*\]', raw, re.DOTALL)
            if not m:
                self._notify("[RepairPlanner] No se pudo extraer plan JSON.", "WARNING")
                return []

            plan: List[dict] = json.loads(m.group(0))

            # Validate structure
            valid = []
            for item in plan:
                if isinstance(item, dict) and "file" in item and "fix_instruction" in item:
                    valid.append({
                        "file": str(item["file"]),
                        "issue": str(item.get("issue", "")),
                        "fix_instruction": str(item["fix_instruction"]),
                    })

            if not valid:
                self._notify("[RepairPlanner] Plan vacío o inválido.", "WARNING")
                return []

            plan_path = workspace / "repair_plan.json"
            plan_path.write_text(json.dumps(valid, indent=2, ensure_ascii=False), encoding="utf-8")

            self._notify(
                f"[RepairPlanner] Plan generado: {len(valid)} correcciones — {plan_path.name}",
                "LOG"
            )
            for i, item in enumerate(valid, 1):
                self._notify(f"  [{i}] {item['file']}: {item['issue']}", "LOG")

            return valid

        except Exception as e:
            self._notify(f"[RepairPlanner] Error generando plan: {e}", "WARNING")
            return []


async def apply_repair_plan(
    plan: List[dict],
    workspace: Path,
    ai_driver,
    notify_fn: Optional[Callable] = None,
) -> List[str]:
    """
    Ejecuta el repair plan: por cada item, lee el archivo, llama al AI fixer
    con la instrucción específica, y escribe el resultado.

    Retorna lista de archivos modificados.
    """
    notify = notify_fn or (lambda msg, lvl="LOG", *a, **kw: None)
    patched: List[str] = []

    _FIXER_PROMPT = """\
You are a code fixer. You will receive a source file and a specific fix instruction.
Apply ONLY the described fix. Do NOT rewrite the file or add unrelated changes.
Respond with the complete fixed file content inside <FILE path='...'> tags.
"""

    for item in plan:
        rel_path = item["file"]
        fix_instruction = item["fix_instruction"]

        # Try to find the file in workspace
        candidates = [
            workspace / rel_path,
            workspace / "source" / rel_path,
        ]
        target = next((p for p in candidates if p.exists()), None)
        if not target:
            try:
                notify("LOG", f"  [RepairPlanner] Archivo no encontrado: {rel_path} — saltando.")
            except Exception:
                pass
            continue

        try:
            current_content = target.read_text(encoding="utf-8", errors="ignore")
            user_msg = (
                f"Fix instruction: {fix_instruction}\n\n"
                f"File: {rel_path}\n"
                f"Current content:\n{current_content[:4000]}"
            )
            resp = await ai_driver.call(
                system_prompt=_FIXER_PROMPT,
                user_message=user_msg,
                model=None,
                temperature=0.1,
            )
            if not resp or not resp.content:
                continue

            # Extract file content from <FILE path='...'> tags
            fm = re.search(
                r"<FILE\s+path=['\"][^'\"]*['\"]>(.*?)</FILE>",
                resp.content, re.DOTALL
            )
            if fm:
                new_content = fm.group(1).strip()
                target.write_text(new_content, encoding="utf-8")
                patched.append(rel_path)
                try:
                    notify("LOG", f"  [RepairPlanner] Parcheado: {rel_path}")
                except Exception:
                    pass
        except Exception as e:
            try:
                notify("WARNING", f"  [RepairPlanner] Error parchando {rel_path}: {e}")
            except Exception:
                pass

    return patched
