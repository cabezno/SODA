"""
Language migration engine for SODA.
Converts an existing codebase from one language to another using AI.

Flow:
  1. Analyze source project (reuses project_analyzer)
  2. Build migration plan (file mapping, equivalences, new stack)
  3. Generate each file in target language
  4. Write migrated project to new workspace
  5. Update run/install commands for new stack
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Optional, Callable

from kernel.intelligence.project_analyzer import collect_project_files


NotifyFn = Callable[[str, str, dict], None]

# Target language → typical run/install commands
_STACK_DEFAULTS: dict[str, dict] = {
    "python":    {"install": "pip install -r requirements.txt", "run": "python main.py",     "ext": ".py"},
    "fastapi":   {"install": "pip install -r requirements.txt", "run": "uvicorn main:app --reload", "ext": ".py"},
    "node":      {"install": "npm install",                     "run": "node index.js",       "ext": ".js"},
    "typescript":{"install": "npm install",                     "run": "npx ts-node src/index.ts", "ext": ".ts"},
    "go":        {"install": "",                                "run": "go run main.go",      "ext": ".go"},
    "rust":      {"install": "cargo build",                     "run": "cargo run",           "ext": ".rs"},
    "java":      {"install": "mvn install",                     "run": "mvn exec:java",       "ext": ".java"},
    "csharp":    {"install": "dotnet restore",                  "run": "dotnet run",          "ext": ".cs"},
    "php":       {"install": "composer install",                "run": "php -S localhost:8080", "ext": ".php"},
    "ruby":      {"install": "bundle install",                  "run": "ruby main.rb",        "ext": ".rb"},
}

SUPPORTED_TARGETS = sorted(_STACK_DEFAULTS.keys())


def _noop(*_):
    pass


async def _ai_migrate_file(
    source_path: str,
    source_content: str,
    source_lang: str,
    target_lang: str,
    project_purpose: str,
    migration_context: str,
) -> str:
    """Migrate a single source file to the target language via AI."""
    prompt = f"""Migrá este archivo de {source_lang} a {target_lang}.

Propósito del proyecto: {project_purpose}
Contexto de migración: {migration_context}

Archivo original ({source_path}):
```{source_lang}
{source_content[:6000]}
```

Reglas:
1. Preservá exactamente la misma lógica y funcionalidad
2. Usá las convenciones y idioms de {target_lang}
3. Usá las librerías estándar o más populares de {target_lang}
4. Añadí imports/requires necesarios
5. Respondé SOLO con el código migrado, sin explicaciones ni markdown

Código en {target_lang}:"""

    try:
        from kernel.drivers.gemini_driver import GeminiDriver
        return await GeminiDriver().prompt(
            f"Sos un experto en migración de código de {source_lang} a {target_lang}. "
            "Respondés SOLO con código, sin explicaciones.",
            prompt,
        )
    except Exception:
        from kernel.drivers.gemini_driver import GeminiDriver
        return await GeminiDriver().prompt(
            f"Experto en migración de {source_lang} a {target_lang}.",
            prompt,
        )


async def _build_migration_plan(
    files: dict[str, str],
    source_lang: str,
    target_lang: str,
    purpose: str,
) -> dict:
    """Ask AI for a file-level migration plan."""
    tree = "\n".join(f"  {k}" for k in sorted(files.keys()))
    prompt = f"""Planificá la migración de este proyecto de {source_lang} a {target_lang}.

Propósito: {purpose}
Archivos fuente:
{tree}

Respondé SOLO con JSON:
{{
  "files_to_migrate": [
    {{"source": "ruta/original.ext", "target": "ruta/nuevo.ext", "action": "migrate|skip|delete", "reason": "por qué"}}
  ],
  "new_files": [
    {{"path": "ruta/nuevo.ext", "description": "qué hace este archivo nuevo que no existe en el original"}}
  ],
  "install_command": "comando de instalación para {target_lang}",
  "run_command": "comando de ejecución para {target_lang}",
  "notes": "observaciones importantes sobre la migración"
}}"""

    try:
        from kernel.drivers.gemini_driver import GeminiDriver
        raw = await GeminiDriver().prompt(
            "Sos un experto en migraciones de proyectos entre lenguajes de programación. "
            "Respondés SOLO con JSON válido.",
            prompt,
        )
    except Exception:
        from kernel.drivers.gemini_driver import GeminiDriver
        raw = await GeminiDriver().prompt("Experto en migración de proyectos.", prompt)

    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass

    # Fallback: migrate everything
    ext = _STACK_DEFAULTS.get(target_lang, {}).get("ext", ".py")
    defaults = _STACK_DEFAULTS.get(target_lang, {})
    return {
        "files_to_migrate": [
            {"source": k, "target": Path(k).stem + ext, "action": "migrate", "reason": "auto"}
            for k in files
        ],
        "new_files": [],
        "install_command": defaults.get("install", ""),
        "run_command": defaults.get("run", ""),
        "notes": "",
    }


class LanguageMigrator:
    """Orchestrates full project language migration."""

    def __init__(self, notify_fn: Optional[NotifyFn] = None):
        self._notify: NotifyFn = notify_fn or _noop

    async def migrate(
        self,
        source_dir: Path,
        target_dir: Path,
        target_language: str,
        project_purpose: str = "",
        source_language: str = "",
    ) -> dict:
        """
        Full migration pipeline.
        Returns {success, migrated_files, skipped_files, run_command, install_command, notes}.
        """
        self._notify(f"Iniciando migración a {target_language}…", "LOG", {})

        # 1. Collect source files
        files = collect_project_files(source_dir)
        if not files:
            return {"success": False, "error": "No se encontraron archivos fuente"}

        self._notify(f"Analizando {len(files)} archivos…", "LOG", {})

        # 2. Detect source language if not provided
        if not source_language:
            exts = [Path(f).suffix.lower() for f in files]
            ext_counts: dict[str, int] = {}
            for e in exts:
                ext_counts[e] = ext_counts.get(e, 0) + 1
            dominant = max(ext_counts, key=lambda x: ext_counts[x], default=".py")
            _ext_to_lang = {".py": "python", ".js": "javascript", ".ts": "typescript",
                            ".go": "go", ".rs": "rust", ".java": "java", ".cs": "csharp",
                            ".php": "php", ".rb": "ruby", ".cpp": "cpp"}
            source_language = _ext_to_lang.get(dominant, dominant.lstrip("."))

        self._notify(f"Lenguaje fuente detectado: {source_language} → {target_language}", "LOG", {})

        # 3. Build migration plan
        plan = await _build_migration_plan(files, source_language, target_language, project_purpose)
        self._notify(f"Plan: {len(plan.get('files_to_migrate', []))} archivos a migrar", "LOG", {})

        # 4. Migrate files
        target_dir.mkdir(parents=True, exist_ok=True)
        migrated: list[str] = []
        skipped: list[str] = []
        context_summary = f"Proyecto: {project_purpose} | {source_language}→{target_language}"

        tasks = []
        for entry in plan.get("files_to_migrate", []):
            if entry.get("action") == "skip":
                skipped.append(entry["source"])
                continue
            src_path = entry["source"]
            tgt_path = entry.get("target", src_path)
            src_content = files.get(src_path, "")
            if not src_content.strip():
                skipped.append(src_path)
                continue
            tasks.append((src_path, tgt_path, src_content))

        # Run migrations concurrently (max 4 at a time to avoid rate limits)
        semaphore = asyncio.Semaphore(4)

        async def _migrate_one(src_path: str, tgt_path: str, src_content: str):
            async with semaphore:
                self._notify(f"Migrando: {src_path} → {tgt_path}", "LOG", {})
                try:
                    migrated_code = await _ai_migrate_file(
                        src_path, src_content,
                        source_language, target_language,
                        project_purpose, context_summary,
                    )
                    out_path = target_dir / tgt_path
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(migrated_code, encoding="utf-8")
                    migrated.append(tgt_path)
                    return tgt_path, True
                except Exception as e:
                    self._notify(f"Error migrando {src_path}: {e}", "LOG", {})
                    skipped.append(src_path)
                    return src_path, False

        await asyncio.gather(*[_migrate_one(s, t, c) for s, t, c in tasks])

        # 5. Generate new files requested by plan
        for nf in plan.get("new_files", []):
            nf_path = nf.get("path", "")
            nf_desc = nf.get("description", "")
            if not nf_path:
                continue
            self._notify(f"Generando nuevo archivo: {nf_path}", "LOG", {})
            try:
                gen_prompt = (
                    f"Generá el archivo '{nf_path}' en {target_language} para un proyecto con "
                    f"propósito: {project_purpose}. Descripción: {nf_desc}. "
                    f"Respondé SOLO con el código completo."
                )
                from kernel.drivers.gemini_driver import GeminiDriver
                code = await GeminiDriver().prompt("Generás código limpio y completo.", gen_prompt)
                out = target_dir / nf_path
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(code, encoding="utf-8")
                migrated.append(nf_path)
            except Exception:
                pass

        # 6. Write migration report
        defaults = _STACK_DEFAULTS.get(target_language, {})
        run_cmd = plan.get("run_command") or defaults.get("run", "")
        install_cmd = plan.get("install_command") or defaults.get("install", "")

        report = (
            f"# Migración {source_language} → {target_language}\n\n"
            f"**Propósito:** {project_purpose}\n\n"
            f"**Archivos migrados ({len(migrated)}):**\n"
            + "\n".join(f"- {f}" for f in migrated) + "\n\n"
            + (f"**Archivos omitidos ({len(skipped)}):**\n" + "\n".join(f"- {f}" for f in skipped) + "\n\n" if skipped else "")
            + f"**Instalar:** `{install_cmd}`\n"
            + f"**Ejecutar:** `{run_cmd}`\n\n"
            + f"**Notas:** {plan.get('notes', '')}\n"
        )
        (target_dir / "_migration_report.md").write_text(report, encoding="utf-8")

        self._notify(
            f"Migración completa: {len(migrated)} archivos → {target_dir}",
            "LOG",
            {"migrated": len(migrated), "skipped": len(skipped)},
        )

        return {
            "success": True,
            "migrated_files": migrated,
            "skipped_files": skipped,
            "run_command": run_cmd,
            "install_command": install_cmd,
            "target_dir": str(target_dir),
            "notes": plan.get("notes", ""),
            "report_path": str(target_dir / "_migration_report.md"),
        }
