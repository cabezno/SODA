from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class OutputResult:
    format: str
    path: str
    size_bytes: int
    success: bool
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "format": self.format,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "success": self.success,
            "error": self.error,
        }


class OutputGenerator:
    """
    Generates non-code outputs from a completed project:
    - Markdown report (always available)
    - PDF report (requires reportlab or weasyprint)
    - Excel model (requires openpyxl)
    - Presentation outline (Markdown-based, can be converted with marp/pandoc)
    """

    # ------------------------------------------------------------------
    # Markdown report — always available, no dependencies
    # ------------------------------------------------------------------

    def generate_markdown_report(
        self,
        project_id: str,
        blueprint: dict,
        architecture: dict,
        reference_report: dict,
        output_dir: Path,
    ) -> OutputResult:
        """Generate a structured Markdown project report."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"report_{project_id[:12]}.md"

        bp = blueprint or {}
        arch = architecture or {}
        ref = reference_report or {}
        modules = arch.get("modulos", [])

        lines = [
            f"# {bp.get('nombre', 'Project')} — Reporte de Generación",
            f"\n_Generado por SODA el {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n",
            "---\n",
            "## Resumen Ejecutivo\n",
            bp.get("descripcion", "Sin descripción."),
            "\n",
            "## Stack Tecnológico\n",
        ]
        stack = bp.get("stack_sugerido", {})
        if isinstance(stack, dict):
            for k, v in stack.items():
                lines.append(f"- **{k}**: {v}")
        elif stack:
            lines.append(f"- {stack}")

        lines += [
            "\n## Módulos Generados\n",
            f"Total: **{len(modules)} módulos**\n",
        ]
        for m in modules:
            files = m.get("archivos_principales", [])
            lines.append(f"### {m.get('nombre', '?')}")
            lines.append(f"{m.get('responsabilidad', '')}\n")
            if files:
                lines.append("Archivos:")
                for f in files:
                    lines.append(f"  - `{f}`")
            lines.append("")

        if ref:
            lines += [
                "\n## Análisis de Calidad\n",
                f"- Archivos rastreados: **{ref.get('tracked_files', 0)}**",
                f"- Sin goal_id: **{ref.get('missing_goal_id', 0)}**",
                f"- Candidatos rotos: **{ref.get('broken_candidates', 0)}**",
            ]

        run_cmd = bp.get("comando_ejecucion", "")
        install_cmd = bp.get("comando_instalacion", "")
        if run_cmd or install_cmd:
            lines += ["\n## Comandos de Ejecución\n"]
            if install_cmd:
                lines.append(f"**Instalación:**\n```\n{install_cmd}\n```\n")
            if run_cmd:
                lines.append(f"**Ejecución:**\n```\n{run_cmd}\n```\n")

        content = "\n".join(lines)
        try:
            path.write_text(content, encoding="utf-8")
            return OutputResult("markdown", str(path), path.stat().st_size, True)
        except Exception as e:
            return OutputResult("markdown", str(path), 0, False, str(e))

    # ------------------------------------------------------------------
    # PDF report — requires reportlab
    # ------------------------------------------------------------------

    def generate_pdf_report(
        self,
        project_id: str,
        blueprint: dict,
        architecture: dict,
        reference_report: dict,
        output_dir: Path,
    ) -> OutputResult:
        """Generate PDF report. Falls back gracefully if reportlab not installed."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"report_{project_id[:12]}.pdf"

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
        except ImportError:
            # Fallback: generate markdown and note PDF not available
            md = self.generate_markdown_report(project_id, blueprint, architecture, reference_report, output_dir)
            return OutputResult("pdf", str(path), 0, False,
                                "reportlab not installed — markdown report generated instead. Run: pip install reportlab")

        bp = blueprint or {}
        arch = architecture or {}
        modules = arch.get("modulos", [])
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=20, spaceAfter=12)
        h2_style = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=14, spaceBefore=16, spaceAfter=6)
        body_style = styles["BodyText"]

        story.append(Paragraph(f"{bp.get('nombre', 'Project')} — Reporte SODA", title_style))
        story.append(Paragraph(f"Generado el {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
        story.append(Spacer(1, 20))

        story.append(Paragraph("Descripción", h2_style))
        story.append(Paragraph(bp.get("descripcion", "Sin descripción."), body_style))
        story.append(Spacer(1, 12))

        if modules:
            story.append(Paragraph("Módulos Generados", h2_style))
            table_data = [["Módulo", "Responsabilidad", "Archivos"]]
            for m in modules:
                table_data.append([
                    m.get("nombre", ""),
                    textwrap.shorten(m.get("responsabilidad", ""), 60),
                    str(len(m.get("archivos_principales", []))),
                ])
            tbl = Table(table_data, colWidths=[120, 280, 60])
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ]))
            story.append(tbl)

        try:
            doc = SimpleDocTemplate(str(path), pagesize=A4)
            doc.build(story)
            return OutputResult("pdf", str(path), path.stat().st_size, True)
        except Exception as e:
            return OutputResult("pdf", str(path), 0, False, str(e))

    # ------------------------------------------------------------------
    # Excel model — requires openpyxl
    # ------------------------------------------------------------------

    def generate_excel_model(
        self,
        project_id: str,
        blueprint: dict,
        architecture: dict,
        output_dir: Path,
    ) -> OutputResult:
        """Generate Excel workbook with project plan, module list, and cost estimate."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"model_{project_id[:12]}.xlsx"

        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
        except ImportError:
            return OutputResult("excel", str(path), 0, False,
                                "openpyxl not installed — run: pip install openpyxl")

        bp = blueprint or {}
        arch = architecture or {}
        modules = arch.get("modulos", [])

        wb = openpyxl.Workbook()

        # Sheet 1: Summary
        ws = wb.active
        ws.title = "Resumen"
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="1e293b")

        ws["A1"] = "SODA — Reporte de Proyecto"
        ws["A1"].font = Font(bold=True, size=14)
        ws["A2"] = f"Proyecto: {bp.get('nombre', project_id)}"
        ws["A3"] = f"Fecha: {datetime.now().strftime('%Y-%m-%d')}"
        ws["A4"] = f"Total módulos: {len(modules)}"
        ws["A5"] = f"Stack: {json.dumps(bp.get('stack_sugerido', {}), ensure_ascii=False)[:100]}"

        # Sheet 2: Modules
        ws2 = wb.create_sheet("Módulos")
        headers = ["Módulo", "Responsabilidad", "Archivos", "Dependencias", "Endpoints"]
        for col, h in enumerate(headers, 1):
            cell = ws2.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        for row_idx, m in enumerate(modules, 2):
            ws2.cell(row=row_idx, column=1, value=m.get("nombre", ""))
            ws2.cell(row=row_idx, column=2, value=m.get("responsabilidad", ""))
            ws2.cell(row=row_idx, column=3, value=", ".join(m.get("archivos_principales", [])))
            ws2.cell(row=row_idx, column=4, value=", ".join(m.get("dependencias", [])))
            ws2.cell(row=row_idx, column=5, value=str(len(m.get("endpoints", []))))

        # Auto-width
        for ws_sheet in [ws, ws2]:
            for col in ws_sheet.columns:
                max_len = max((len(str(c.value or "")) for c in col), default=10)
                ws_sheet.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

        try:
            wb.save(str(path))
            return OutputResult("excel", str(path), path.stat().st_size, True)
        except Exception as e:
            return OutputResult("excel", str(path), 0, False, str(e))

    # ------------------------------------------------------------------
    # Presentation outline (Markdown-based MARP)
    # ------------------------------------------------------------------

    def generate_presentation(
        self,
        project_id: str,
        blueprint: dict,
        architecture: dict,
        output_dir: Path,
    ) -> OutputResult:
        """Generate a Marp-compatible Markdown presentation."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"presentation_{project_id[:12]}.md"

        bp = blueprint or {}
        arch = architecture or {}
        modules = arch.get("modulos", [])

        slides = [
            "---\nmarp: true\ntheme: default\npaginate: true\n---\n",
            f"# {bp.get('nombre', 'Project')}\n\n{bp.get('descripcion', '')[:200]}\n\n_Generado por SODA_\n",
            "---\n\n## Stack Tecnológico\n",
        ]
        stack = bp.get("stack_sugerido", {})
        if isinstance(stack, dict):
            for k, v in stack.items():
                slides.append(f"- **{k}**: {v}")
        slides.append("\n---\n\n## Arquitectura — Módulos\n")
        for m in modules[:8]:
            slides.append(f"- **{m.get('nombre', '?')}**: {m.get('responsabilidad', '')[:80]}")

        slides += [
            "\n---\n\n## Próximos Pasos\n",
            "- Instalar dependencias",
            "- Ejecutar el proyecto",
            "- Revisar y personalizar",
            "\n---\n\n# ¿Preguntas?\n\n_Generado con SODA_\n",
        ]

        content = "\n".join(slides)
        try:
            path.write_text(content, encoding="utf-8")
            return OutputResult("presentation", str(path), path.stat().st_size, True)
        except Exception as e:
            return OutputResult("presentation", str(path), 0, False, str(e))

    # ------------------------------------------------------------------
    # Convenience: generate all
    # ------------------------------------------------------------------

    def generate_all(
        self,
        project_id: str,
        blueprint: dict,
        architecture: dict,
        reference_report: dict,
        output_dir: Path,
    ) -> list[OutputResult]:
        return [
            self.generate_markdown_report(project_id, blueprint, architecture, reference_report, output_dir),
            self.generate_pdf_report(project_id, blueprint, architecture, reference_report, output_dir),
            self.generate_excel_model(project_id, blueprint, architecture, output_dir),
            self.generate_presentation(project_id, blueprint, architecture, output_dir),
        ]
