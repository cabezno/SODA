"""Dataclasses for self-repair analysis reports."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class FileIssue:
    file: str
    line: int
    severity: str          # "error" | "warning" | "suggestion"
    description: str
    suggested_fix: str = ""


@dataclass
class FileReport:
    path: str
    stage: str
    status: str            # "ok" | "issues" | "improved" | "error"
    issues: list[FileIssue] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    fixed_code: str = ""   # full corrected file content (if AI provided it)
    impact: str = "low"    # "low" | "medium" | "high"
    applied: bool = False

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


@dataclass
class StageReport:
    stage: str
    files: list[FileReport] = field(default_factory=list)
    summary: str = ""

    @property
    def total_errors(self) -> int:
        return sum(f.error_count for f in self.files)

    @property
    def total_improvements(self) -> int:
        return sum(len(f.improvements) for f in self.files)


@dataclass
class UnifiedReport:
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    backup_path: str = ""
    stages: list[StageReport] = field(default_factory=list)
    unified_assessment: str = ""
    recommended_actions: list[str] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return sum(len(s.files) for s in self.stages)

    @property
    def total_errors(self) -> int:
        return sum(s.total_errors for s in self.stages)

    @property
    def total_improvements(self) -> int:
        return sum(s.total_improvements for s in self.stages)

    @property
    def files_with_fixes(self) -> list[FileReport]:
        return [f for s in self.stages for f in s.files if f.fixed_code]

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "backup_path": self.backup_path,
            "summary": {
                "files_analyzed": self.total_files,
                "errors_found": self.total_errors,
                "improvements_suggested": self.total_improvements,
                "files_with_fixes": len(self.files_with_fixes),
            },
            "stages": [
                {
                    "stage": s.stage,
                    "summary": s.summary,
                    "errors": s.total_errors,
                    "improvements": s.total_improvements,
                    "files": [
                        {
                            "path": f.path,
                            "status": f.status,
                            "impact": f.impact,
                            "applied": f.applied,
                            "errors": f.error_count,
                            "warnings": f.warning_count,
                            "improvements": f.improvements,
                            "issues": [
                                {"line": i.line, "severity": i.severity,
                                 "description": i.description, "fix": i.suggested_fix}
                                for i in f.issues
                            ],
                        }
                        for f in s.files
                    ],
                }
                for s in self.stages
            ],
            "unified_assessment": self.unified_assessment,
            "recommended_actions": self.recommended_actions,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Informe de Autoreparacion SODA",
            f"**Fecha:** {self.timestamp}",
            f"**Backup:** `{self.backup_path}`",
            "",
            "## Resumen Ejecutivo",
            f"- Archivos analizados: **{self.total_files}**",
            f"- Errores encontrados: **{self.total_errors}**",
            f"- Mejoras sugeridas: **{self.total_improvements}**",
            f"- Archivos con codigo corregido: **{len(self.files_with_fixes)}**",
            "",
        ]
        if self.unified_assessment:
            lines += ["## Evaluacion General", self.unified_assessment, ""]

        if self.recommended_actions:
            lines += ["## Acciones Recomendadas"]
            for i, a in enumerate(self.recommended_actions, 1):
                lines.append(f"{i}. {a}")
            lines.append("")

        for stage in self.stages:
            lines += [f"## Etapa: {stage.stage}"]
            if stage.summary:
                lines.append(stage.summary)
            lines.append("")
            for f in stage.files:
                if f.status == "ok" and not f.improvements:
                    continue
                impact_badge = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(f.impact, "⚪")
                lines.append(f"### {impact_badge} `{f.path}` [{f.status}]")
                if f.issues:
                    lines.append("**Problemas:**")
                    for iss in f.issues:
                        lines.append(f"- L{iss.line} `{iss.severity}`: {iss.description}")
                        if iss.suggested_fix:
                            lines.append(f"  → {iss.suggested_fix}")
                if f.improvements:
                    lines.append("**Mejoras:**")
                    for imp in f.improvements:
                        lines.append(f"- {imp}")
                if f.applied:
                    lines.append("✅ *Cambios aplicados*")
                lines.append("")
        return "\n".join(lines)

    def save(self, out_dir: Path) -> tuple[Path, Path]:
        """Write report.json + report.md. Returns (json_path, md_path)."""
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = out_dir / f"selfrepair_{ts}.json"
        md_path = out_dir / f"selfrepair_{ts}.md"
        json_path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(self.to_markdown(), encoding="utf-8")
        return json_path, md_path
