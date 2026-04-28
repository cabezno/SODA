"""AutoFixAgent — runtime error repair using contract-aware prompts."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from kernel.agents.error_sanitizer import sanitize_runtime_error, extract_files_from_error

_MAX_FILE_CHARS = 6_000
_FENCE_RE = re.compile(r'^```[^\n]*\n?', re.MULTILINE)


def _strip_fence(code: str) -> str:
    code = code.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        start = 1
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        code = "\n".join(lines[start:end])
    return code.strip()


def _extract_module_contract(filepath: str, master_contract: Optional[dict]) -> str:
    """Return a compact interface block for the module owning this file."""
    if not master_contract:
        return "No hay contrato maestro disponible para este módulo."
    modules = master_contract.get("modules", [])
    # Match by archivos_principales
    target = None
    for m in modules:
        if not isinstance(m, dict):
            continue
        files = m.get("archivos_principales", [])
        if any(filepath in f or f in filepath for f in files):
            target = m
            break
    if not target:
        return "Módulo no encontrado en master_contract — respetá las firmas existentes."

    lines = [f"Módulo: {target.get('id', target.get('nombre', '?'))}"]
    interfaces = target.get("interfaces", [])
    if interfaces:
        lines.append("Interfaces obligatorias:")
        for iface in interfaces:
            name = iface.get("name", "")
            params = iface.get("parameters", {})
            returns = iface.get("returns", "")
            params_str = ", ".join(f"{k}: {v}" for k, v in params.items())
            lines.append(f"  {name}({params_str}) -> {returns}")
    data_types = master_contract.get("data_types", [])
    used_types = set(target.get("data_types_used", []))
    relevant = [dt for dt in data_types if isinstance(dt, dict) and dt.get("name") in used_types]
    if relevant:
        lines.append("Tipos de datos:")
        for dt in relevant:
            fields = dt.get("fields", {})
            lines.append(f"  {dt['name']}: {{{', '.join(f'{k}: {v}' for k, v in fields.items())}}}")
    return "\n".join(lines)


class AutoFixAgent:
    """Applies targeted, contract-aware fixes to a single file that crashed at runtime."""

    def __init__(self, claude_driver, gemini_driver=None, context_builder=None, notify_fn=None):
        self.claude = claude_driver
        self.gemini = gemini_driver
        self.builder = context_builder
        self._notify = notify_fn or (lambda *a, **kw: None)

    async def fix_file(
        self,
        filepath: str,
        error_message: str,
        source_dir: Path,
        master_contract: Optional[dict] = None,
        workspace_path: Optional[Path] = None,
    ) -> Optional[str]:
        """Repair a single file.

        Returns the corrected source code, or None if the fix failed.
        `error_message` may be raw stderr (will be sanitized) or already-clean text.
        """
        full_path = source_dir / filepath
        if not full_path.exists():
            self._notify(
                f"AutoFixAgent: archivo no encontrado: {filepath}",
                "HEALTH_WARN",
                {"phase": "auto_fix", "file": filepath},
            )
            return None

        current_code = full_path.read_text(encoding="utf-8", errors="replace")
        if len(current_code) > _MAX_FILE_CHARS:
            current_code = current_code[:_MAX_FILE_CHARS] + "\n# ... (truncado por tamaño)"

        # Sanitize if raw stderr was passed
        ws = str(workspace_path or source_dir.parent)
        clean_error = sanitize_runtime_error(error_message, ws)

        contract_block = _extract_module_contract(filepath, master_contract)

        # Build the task using the prompt template format
        task = (
            f"<archivo_con_error filepath=\"{filepath}\">\n{current_code}\n</archivo_con_error>\n\n"
            f"<error_runtime_sanitizado>\n{clean_error}\n</error_runtime_sanitizado>\n\n"
            f"<contrato_obligatorio>\n{contract_block}\n"
            "REGLA ABSOLUTA: Podés cambiar la lógica interna, pero NO modificar las firmas del contrato.\n"
            "</contrato_obligatorio>"
        )

        self._notify(
            f"AutoFixAgent: reparando {filepath}…",
            "AI_WORKING",
            {"phase": "auto_fix", "file": filepath},
        )

        response: Optional[str] = None
        for driver, provider in [(self.claude, "claude"), (self.gemini, "gemini")]:
            if driver is None:
                continue
            try:
                if self.builder:
                    payload = self.builder.build_payload(provider, "auto_fixer", task)
                    if provider == "claude":
                        raw = await driver.prompt(payload["system"], payload["user"])
                    else:
                        result = await driver.call(payload["system"], payload["user"])
                        raw = result.content if hasattr(result, "content") else str(result)
                else:
                    raw = await driver.prompt("", task) if provider == "claude" else (await driver.call("", task)).content
                if hasattr(raw, "content"):
                    raw = raw.content
                fixed = _strip_fence(str(raw or ""))
                if fixed and not fixed.startswith("ERROR:"):
                    response = fixed
                    break
            except Exception as exc:
                self._notify(
                    f"AutoFixAgent: {provider} falló en {filepath}: {exc}",
                    "HEALTH_WARN",
                    {"phase": "auto_fix", "provider": provider, "file": filepath, "error": str(exc)},
                )
                continue

        return response

    async def fix_files_from_errors(
        self,
        errors: list[dict],
        raw_stderr: str,
        source_dir: Path,
        master_contract: Optional[dict] = None,
        workspace_path: Optional[Path] = None,
    ) -> list[str]:
        """Fix multiple files identified in a boot error report.

        `errors` is the `last_errors` list from boot_report.json.
        Returns the list of file paths that were successfully patched.
        """
        ws = workspace_path or source_dir.parent

        # Prefer parsed errors from boot_report; fall back to regex on raw stderr
        file_paths: list[str] = []
        seen: set[str] = set()
        for err in errors:
            fp = err.get("file")
            if fp and fp not in seen:
                seen.add(fp)
                file_paths.append(fp)

        if not file_paths and raw_stderr:
            clean = sanitize_runtime_error(raw_stderr, ws)
            file_paths = extract_files_from_error(clean)

        # Build a single clean error message from all parsed errors
        if errors:
            clean_error = "\n".join(
                f"{e.get('file', '?')}:{e.get('line', '?')}: {e.get('message', '')}"
                for e in errors[:8]
            )
        else:
            clean_error = sanitize_runtime_error(raw_stderr, ws) if raw_stderr else "Error desconocido."

        patched: list[str] = []
        for fpath in file_paths[:4]:  # cap at 4 files per round
            fixed_code = await self.fix_file(
                filepath=fpath,
                error_message=clean_error,
                source_dir=source_dir,
                master_contract=master_contract,
                workspace_path=ws,
            )
            if fixed_code:
                out = source_dir / fpath
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(fixed_code, encoding="utf-8")
                self._notify(
                    f"AutoFixAgent: {fpath} reparado.",
                    "FILE_GENERATED",
                    {"filename": fpath, "code": fixed_code, "validated": False, "phase": "auto_fix"},
                )
                patched.append(fpath)

        return patched
