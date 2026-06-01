"""SystemHealer — staged self-repair orchestrator for SODA.

Flow:
  1. BackupManager.create()          — full snapshot before any change
  2. For each stage (kernel subdir):
       a. Read files (bounded context, max MAX_FILE_LINES per file)
       b. Send to Gemini: analyze errors + improvements + corrected code
       c. Build FileReport / StageReport
  3. UnifiedReport: aggregate all stages, generate assessment
  4. Apply fixes: write corrected files to disk
  5. Save report (JSON + Markdown) to reports/

Notifications go to console + notify_fn (WebSocket → UI).
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Callable, Optional

from kernel.selfrepair.backup_manager import BackupManager
from kernel.selfrepair.repair_report import (
    FileIssue, FileReport, StageReport, UnifiedReport,
)

# Stages: (label, glob_pattern, max_files_per_call)
_STAGES: list[tuple[str, str, int]] = [
    ("drivers",       "kernel/drivers/*.py",          5),
    ("intelligence",  "kernel/intelligence/*.py",     3),
    ("orchestration", "kernel/orchestration/*.py",    3),
    ("orchestrator",  "kernel/orchestrator.py",       1),
    ("communication", "kernel/communication/*.py",    4),
    ("sandbox",       "kernel/sandbox/*.py",          4),
    ("selfrepair",    "kernel/selfrepair/*.py",        4),
    ("execution",     "kernel/execution/*.py",        4),
    ("tts",           "kernel/tts/*.py",              4),
    ("validation",    "kernel/validation/*.py",       4),
    ("integrity",     "kernel/integrity/*.py",        4),
    ("external",      "kernel/external/*.py",         4),
    ("server",        "ui/server.py",                 1),
]

MAX_FILE_LINES = 300     # truncate to keep context bounded
MAX_LINES_PER_CALL = 800 # total lines sent to AI per batch


class SystemHealer:
    """Analyzes SODA's own code, proposes fixes, applies them after backup."""

    def __init__(
        self,
        base_dir: Path,
        gemini_driver=None,
        notify_fn: Optional[Callable] = None,
    ):
        self.base_dir = base_dir
        self.driver = gemini_driver
        self._notify = notify_fn or (lambda msg, ev, data: None)
        self.backup_mgr = BackupManager(base_dir)

    # ── Main entry point ─────────────────────────────────────────────────

    async def run(
        self,
        stages: Optional[list[str]] = None,
        apply_fixes: bool = False,
        label: str = "selfrepair",
    ) -> UnifiedReport:
        """
        Run a full heal cycle.

        stages: list of stage names to include (None = all)
        apply_fixes: if True, write corrected files to disk after backup
        """
        self._emit("=== AutoReparacion SODA iniciada ===", "SELFREPAIR_START")

        # 1. Backup — mandatory before any change
        backup_path = self.backup_mgr.create(label=label)
        self._emit(f"Backup creado: {backup_path.name}", "SELFREPAIR_BACKUP")

        report = UnifiedReport(backup_path=str(backup_path))

        # 2. Analyze stage by stage
        active = self._active_stages(stages)
        for stage_label, pattern, batch_size in active:
            self._emit(f"Analizando etapa: {stage_label}...", "SELFREPAIR_STAGE")
            stage_report = await self._analyze_stage(stage_label, pattern, batch_size)
            report.stages.append(stage_report)
            self._emit(
                f"Etapa {stage_label}: {stage_report.total_errors} errores, "
                f"{stage_report.total_improvements} mejoras",
                "SELFREPAIR_STAGE_DONE",
            )

        # 3. Unified assessment
        self._emit("Generando evaluacion unificada...", "SELFREPAIR_ASSESS")
        report.unified_assessment, report.recommended_actions = await self._unified_assessment(report)

        # 4. Apply fixes (only if requested and backup exists)
        if apply_fixes and report.files_with_fixes:
            self._emit(
                f"Aplicando {len(report.files_with_fixes)} correcciones...",
                "SELFREPAIR_APPLY",
            )
            for file_report in report.files_with_fixes:
                applied = self._apply_fix(file_report)
                file_report.applied = applied
                if applied:
                    self._emit(f"Corregido: {file_report.path}", "SELFREPAIR_APPLY")

        # 5. Save report
        reports_dir = self.base_dir / "reports"
        json_path, md_path = report.save(reports_dir)
        self._emit(
            f"Informe guardado: {json_path.name} | {md_path.name}",
            "SELFREPAIR_DONE",
        )
        self._emit(
            f"=== Fin: {report.total_files} archivos | "
            f"{report.total_errors} errores | "
            f"{report.total_improvements} mejoras ===",
            "SELFREPAIR_DONE",
        )
        return report

    # ── Stage analysis ───────────────────────────────────────────────────

    def _active_stages(self, filter_labels: Optional[list[str]]) -> list[tuple]:
        if not filter_labels:
            return _STAGES
        return [(l, p, b) for l, p, b in _STAGES if l in filter_labels]

    async def _analyze_stage(self, label: str, pattern: str, batch_size: int) -> StageReport:
        files = sorted(self.base_dir.glob(pattern))
        if not files:
            return StageReport(stage=label, summary="Sin archivos para analizar.")

        stage = StageReport(stage=label)
        batches = [files[i:i+batch_size] for i in range(0, len(files), batch_size)]

        for batch in batches:
            file_reports = await self._analyze_batch(label, batch)
            stage.files.extend(file_reports)

        ok = sum(1 for f in stage.files if f.status == "ok")
        issues = sum(1 for f in stage.files if f.status != "ok")
        stage.summary = f"{len(stage.files)} archivo(s) analizados — {ok} OK, {issues} con observaciones."
        return stage

    async def _analyze_batch(self, stage: str, files: list[Path]) -> list[FileReport]:
        if not self.driver:
            return [FileReport(path=str(f.relative_to(self.base_dir)), stage=stage, status="skipped")
                    for f in files]

        snippets: list[dict] = []
        for f in files:
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
                truncated = len(lines) > MAX_FILE_LINES
                content = "\n".join(lines[:MAX_FILE_LINES])
                if truncated:
                    content += f"\n... [truncado en {MAX_FILE_LINES} lineas de {len(lines)}]"
                snippets.append({"path": str(f.relative_to(self.base_dir)), "content": content})
            except Exception as e:
                snippets.append({"path": str(f.relative_to(self.base_dir)), "content": f"ERROR: {e}"})

        prompt = self._build_analysis_prompt(stage, snippets)
        try:
            response = await self.driver.call(
                system_prompt=_SYSTEM_PROMPT,
                user_message=prompt,
                model="gemini-3.1-pro-preview",
                max_tokens=4096,
                temperature=0.2,
                metadata={"phase": "selfrepair", "stage": stage},
            )
            return self._parse_ai_response(response.content, stage, files)
        except Exception as e:
            self._emit(f"Error analizando {stage}: {e}", "SELFREPAIR_ERROR")
            return [FileReport(path=str(f.relative_to(self.base_dir)), stage=stage,
                               status="error", issues=[FileIssue(f.name, 0, "error", str(e))])
                    for f in files]

    def _build_analysis_prompt(self, stage: str, snippets: list[dict]) -> str:
        files_block = "\n\n".join(
            f'### FILE: {s["path"]}\n```python\n{s["content"]}\n```'
            for s in snippets
        )
        return f"""Etapa de análisis: **{stage}**

Analizá los siguientes archivos de SODA (sistema de generación automática de software).

{files_block}

Respondé SOLO con JSON válido siguiendo este schema exacto:
{{
  "files": [
    {{
      "path": "ruta/del/archivo.py",
      "status": "ok|issues|improved",
      "impact": "low|medium|high",
      "issues": [
        {{
          "line": <número>,
          "severity": "error|warning|suggestion",
          "description": "descripción clara del problema",
          "suggested_fix": "cómo corregirlo (una línea)"
        }}
      ],
      "improvements": ["mejora 1", "mejora 2"],
      "fixed_code": "<código Python corregido completo, o vacío si no hay cambios>"
    }}
  ]
}}

Reglas:
- fixed_code: solo si hay errores reales que corregir. Incluí el archivo COMPLETO corregido.
- Para archivos sin problemas: status "ok", arrays vacíos, fixed_code "".
- Sé específico — línea exacta, descripción concisa.
- No inventes problemas. Si el código está correcto, decí "ok".
"""

    def _parse_ai_response(self, content: str, stage: str, files: list[Path]) -> list[FileReport]:
        try:
            data = _extract_json(content)
            reports = []
            path_map = {str(f.relative_to(self.base_dir)).replace("\\", "/"): f for f in files}

            for item in data.get("files", []):
                raw_path = item.get("path", "").replace("\\", "/")
                issues = [
                    FileIssue(
                        file=raw_path,
                        line=iss.get("line", 0),
                        severity=iss.get("severity", "warning"),
                        description=iss.get("description", ""),
                        suggested_fix=iss.get("suggested_fix", ""),
                    )
                    for iss in item.get("issues", [])
                ]
                reports.append(FileReport(
                    path=raw_path,
                    stage=stage,
                    status=item.get("status", "ok"),
                    issues=issues,
                    improvements=item.get("improvements", []),
                    fixed_code=item.get("fixed_code", ""),
                    impact=item.get("impact", "low"),
                ))
            return reports
        except Exception as e:
            self._emit(f"Error parseando respuesta AI ({stage}): {e}", "SELFREPAIR_ERROR")
            return [FileReport(path=str(f.relative_to(self.base_dir)), stage=stage, status="parse_error")
                    for f in files]

    # ── Unified assessment ───────────────────────────────────────────────

    async def _unified_assessment(self, report: UnifiedReport) -> tuple[str, list[str]]:
        if not self.driver:
            return "Driver no disponible para evaluacion unificada.", []

        summary_data = {
            "total_files": report.total_files,
            "total_errors": report.total_errors,
            "total_improvements": report.total_improvements,
            "stages": [
                {
                    "stage": s.stage,
                    "errors": s.total_errors,
                    "improvements": s.total_improvements,
                    "files": [
                        {"path": f.path, "status": f.status, "impact": f.impact,
                         "issues": [i.description for i in f.issues[:3]],
                         "improvements": f.improvements[:3]}
                        for f in s.files if f.status != "ok"
                    ],
                }
                for s in report.stages
            ],
        }

        prompt = f"""Generá una evaluación general de salud del sistema SODA a partir de este resumen de análisis:

```json
{json.dumps(summary_data, indent=2, ensure_ascii=False)}
```

Respondé con JSON:
{{
  "assessment": "párrafo de evaluación general (3-5 oraciones)",
  "recommended_actions": ["acción 1", "acción 2", "..."]
}}

Ordená las acciones por prioridad (críticas primero). Máximo 8 acciones.
"""
        try:
            response = await self.driver.call(
                system_prompt="Sos un experto en análisis de sistemas Python. Respondé solo con JSON válido.",
                user_message=prompt,
                model="gemini-3.1-pro-preview",
                max_tokens=1024,
                temperature=0.3,
                metadata={"phase": "selfrepair", "stage": "unified_assessment"},
            )
            data = _extract_json(response.content)
            return (
                data.get("assessment", ""),
                data.get("recommended_actions", []),
            )
        except Exception as e:
            return f"Error en evaluacion unificada: {e}", []

    # ── Apply fixes ──────────────────────────────────────────────────────

    def _apply_fix(self, file_report: FileReport) -> bool:
        if not file_report.fixed_code or not file_report.fixed_code.strip():
            return False
        try:
            target = self.base_dir / file_report.path
            target.write_text(file_report.fixed_code, encoding="utf-8")
            print(f"  [SelfRepair] Aplicado: {file_report.path}")
            return True
        except Exception as e:
            self._emit(f"Error aplicando fix en {file_report.path}: {e}", "SELFREPAIR_ERROR")
            return False

    def _emit(self, message: str, event_type: str) -> None:
        prefixes = {
            "SELFREPAIR_START":      "[REPAIR] ",
            "SELFREPAIR_BACKUP":     "[REPAIR BACKUP] ",
            "SELFREPAIR_STAGE":      "[REPAIR STAGE] ",
            "SELFREPAIR_STAGE_DONE": "[REPAIR] ",
            "SELFREPAIR_ASSESS":     "[REPAIR] ",
            "SELFREPAIR_APPLY":      "[REPAIR APPLY] ",
            "SELFREPAIR_DONE":       "[REPAIR] ",
            "SELFREPAIR_ERROR":      "[REPAIR ERROR] ",
        }
        print(f"{prefixes.get(event_type, '[REPAIR] ')}{message}")
        self._notify(message, event_type, {"timestamp": __import__("datetime").datetime.now().isoformat()})


# ── Helpers ──────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "Sos un experto en Python y arquitectura de sistemas. "
    "Tu tarea es analizar código Python del sistema SODA y detectar: "
    "errores reales (bugs, excepciones potenciales, imports rotos), "
    "problemas de calidad (código muerto, duplicación, mal manejo de errores), "
    "y oportunidades de mejora concretas. "
    "Respondé SIEMPRE con JSON válido, sin texto adicional."
)


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*\n([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            pass
    return {}
