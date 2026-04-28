"""PerformanceTracker — records per-AI effectiveness metrics during a SODA pipeline run."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class _FileResult:
    provider: str  # "qwen" | "claude" | "gemini" | "claude_haiku" | "none"
    level: int     # 1-9 (escalation level: 1-3 Qwen, 4-6 Gemini, 7-9 Claude)
    validated: bool


class PerformanceTracker:
    """Collects metrics from all AI providers during a pipeline run and prints a report."""

    def __init__(self) -> None:
        self._files: list[_FileResult] = []
        self._architect_attempts: int = 0
        self._architect_status: Optional[str] = None
        self._architect_model: Optional[str] = None
        self._conformance_compliant: int = 0
        self._conformance_fixed: int = 0
        self._conformance_skipped: int = 0
        self._gemini_phases: list[str] = []

    # ── Code generation ─────────────────────────────────────────────────────

    def record_file_generated(self, provider: str, level: int, validated: bool) -> None:
        """Called by CodeGenerator for each file after the escalation ladder finishes."""
        self._files.append(_FileResult(provider=provider, level=level, validated=validated))

    # ── Architect v2 ────────────────────────────────────────────────────────

    def record_contract_result(
        self,
        status: str,
        attempts: int,
        model: str = "claude-sonnet-4-6",
    ) -> None:
        self._architect_status = status
        self._architect_attempts = attempts
        self._architect_model = model

    # ── Conformance verifier ─────────────────────────────────────────────────

    def record_conformance(self, fixed: bool, skipped: bool = False) -> None:
        """skipped=True when no file was found for the module."""
        if skipped:
            self._conformance_skipped += 1
        elif fixed:
            self._conformance_fixed += 1
        else:
            self._conformance_compliant += 1

    def reset(self) -> None:
        """Clear all accumulated metrics. Call at the start of each pipeline run."""
        self._files.clear()
        self._architect_attempts = 0
        self._architect_status = None
        self._architect_model = None
        self._conformance_compliant = 0
        self._conformance_fixed = 0
        self._conformance_skipped = 0
        self._gemini_phases.clear()

    # ── Phase tracking ───────────────────────────────────────────────────────

    def record_gemini_phase(self, phase: str) -> None:
        self._gemini_phases.append(phase)

    # ── Report ───────────────────────────────────────────────────────────────

    def print_report(self) -> None:
        W = 65
        bar = "═" * W

        def _row(label: str, value: str = "") -> str:
            if value:
                content = f"  {label:<32}: {value}"
            else:
                content = f"  {label}"
            return f"║ {content:<{W - 2}} ║"

        def _hdr(title: str) -> str:
            return f"║  {title:<{W - 3}}║"

        def _sep() -> str:
            return f"╠{bar}╣"

        def _pct(n: int, total: int) -> str:
            return f"({n / total * 100:.1f}%)" if total else "(—)"

        print(f"\n╔{bar}╗")
        title = "SODA — Reporte de Efectividad del Equipo IA"
        print(f"║{title:^{W}}║")

        # ── Qwen ─────────────────────────────────────────────────────────────
        total = len(self._files)
        if total > 0:
            qwen_l1    = sum(1 for f in self._files if f.provider == "qwen" and f.level == 1)
            qwen_l2l3  = sum(1 for f in self._files if f.provider == "qwen" and f.level in (2, 3))
            escalated  = sum(1 for f in self._files if f.provider not in ("qwen", "none"))
            failed_all = sum(1 for f in self._files if not f.validated)

            print(_sep())
            print(_hdr("Qwen 2.5-coder:7b"))
            print(_row("Archivos intentados", str(total)))
            print(_row("  Éxito 1er intento    [L1]",    f"{qwen_l1:>3}  {_pct(qwen_l1,   total)}"))
            print(_row("  Éxito reintentos     [L2-L3]", f"{qwen_l2l3:>3}  {_pct(qwen_l2l3, total)}"))
            print(_row("  Escaló a cloud       [L4+]",   f"{escalated:>3}  {_pct(escalated, total)}"))
            if failed_all:
                print(_row("  Sin validar   [todos fallaron]", f"{failed_all:>3}  {_pct(failed_all, total)}"))

        # ── Gemini escalation (L4-L6, up to 3 attempts per file) ────────────────
        gemini_files = [f for f in self._files if f.provider == "gemini"]
        if gemini_files:
            ok = sum(1 for f in gemini_files if f.validated)
            n  = len(gemini_files)
            # level 4=1st attempt, 5=2nd, 6=3rd
            g1 = sum(1 for f in gemini_files if f.level == 4 and f.validated)
            g2 = sum(1 for f in gemini_files if f.level == 5 and f.validated)
            g3 = sum(1 for f in gemini_files if f.level == 6 and f.validated)
            print(_sep())
            print(_hdr("Gemini — Escalación (L4-L6, máx 3 intentos)"))
            print(_row("Archivos recibidos de Qwen",        str(n)))
            print(_row("  Resuelto en 1er intento [L4]",    f"{g1:>3}  {_pct(g1, n)}"))
            print(_row("  Resuelto en 2do intento [L5]",    f"{g2:>3}  {_pct(g2, n)}"))
            print(_row("  Resuelto en 3er intento [L6]",    f"{g3:>3}  {_pct(g3, n)}"))
            failed_g = n - ok
            if failed_g:
                print(_row("  Escaló a Claude         [L7+]",f"{failed_g:>3}  {_pct(failed_g, n)}"))

        # ── Claude escalation (L7-L9, up to 3 attempts per file) ────────────────
        claude_files = [f for f in self._files if f.provider == "claude"]
        if claude_files:
            ok = sum(1 for f in claude_files if f.validated)
            n  = len(claude_files)
            c1 = sum(1 for f in claude_files if f.level == 7 and f.validated)
            c2 = sum(1 for f in claude_files if f.level == 8 and f.validated)
            c3 = sum(1 for f in claude_files if f.level == 9 and f.validated)
            print(_sep())
            print(_hdr("Claude Sonnet — Escalación (L7-L9, máx 3 intentos)"))
            print(_row("Archivos recibidos de Gemini",       str(n)))
            print(_row("  Resuelto en 1er intento [L7]",    f"{c1:>3}  {_pct(c1, n)}"))
            print(_row("  Resuelto en 2do intento [L8]",    f"{c2:>3}  {_pct(c2, n)}"))
            print(_row("  Resuelto en 3er intento [L9]",    f"{c3:>3}  {_pct(c3, n)}"))
            failed_c = n - ok
            if failed_c:
                print(_row("  Sin validar (9 niveles)", f"{failed_c:>3}  {_pct(failed_c, n)}"))

        # ── Architect v2 ──────────────────────────────────────────────────────
        if self._architect_status is not None:
            model_tag = {
                "claude-haiku-4-5-20251001": "Haiku",
                "claude-sonnet-4-6":         "Sonnet",
                "claude-opus-4-7":           "Opus",
            }.get(self._architect_model or "", "Sonnet")
            status_display = {
                "approved":                    "aprobado ✓",
                "approved_with_warnings":      "aprobado con alertas ⚠",
                "requires_user_intervention":  "requiere intervención ✗",
            }.get(self._architect_status, self._architect_status)
            print(_sep())
            print(_hdr(f"Claude {model_tag} — Arquitecto v2"))
            print(_row("Estado del contrato",          status_display))
            print(_row("Intentos hasta aprobación",    str(self._architect_attempts)))

        # ── Conformance verifier ──────────────────────────────────────────────
        cv_checked = self._conformance_compliant + self._conformance_fixed
        cv_total   = cv_checked + self._conformance_skipped
        if cv_total > 0:
            print(_sep())
            print(_hdr("Claude Haiku — Verificador de Conformidad"))
            print(_row("Módulos procesados", str(cv_total)))
            if cv_checked > 0:
                print(_row(
                    "  Conformes (sin cambios)",
                    f"{self._conformance_compliant:>3}  {_pct(self._conformance_compliant, cv_checked)}",
                ))
                print(_row(
                    "  Corregidos por Haiku",
                    f"{self._conformance_fixed:>3}  {_pct(self._conformance_fixed, cv_checked)}",
                ))
            if self._conformance_skipped:
                print(_row("  Saltados (sin archivo)", str(self._conformance_skipped)))

        # ── Gemini phases ─────────────────────────────────────────────────────
        if self._gemini_phases:
            phase_labels = {
                "capabilities": "CAP — skills y perfil",
                "wisdom":       "WISDOM — ambigüedades",
                "requirements": "REQ — blueprint",
                "architecture": "ARCH — arquitectura",
                "evolution":    "EVOLUTION — aprendizajes",
            }
            print(_sep())
            print(_hdr("Gemini — Fases ejecutadas"))
            for ph in self._gemini_phases:
                print(_row(f"  {phase_labels.get(ph, ph)}", "✓"))

        print(f"╚{bar}╝\n")
