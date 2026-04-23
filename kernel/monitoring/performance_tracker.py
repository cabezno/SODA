"""PerformanceTracker — records per-AI effectiveness metrics during a SODA pipeline run."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class _FileResult:
    provider: str  # "qwen" | "claude" | "gemini" | "claude_haiku" | "none"
    level: int     # 1-6 (escalation level)
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

        # ── Cloud escalation providers ────────────────────────────────────────
        cloud_labels = [
            ("claude",       "Claude Sonnet — Escalación de código"),
            ("gemini",       "Gemini — Escalación de código"),
            ("claude_haiku", "Claude Haiku — Escalación L6"),
        ]
        for key, label in cloud_labels:
            subset = [f for f in self._files if f.provider == key]
            if subset:
                ok = sum(1 for f in subset if f.validated)
                n  = len(subset)
                print(_sep())
                print(_hdr(label))
                print(_row("Archivos recibidos",         str(n)))
                print(_row("  Generados exitosamente",   f"{ok:>3}  {_pct(ok, n)}"))

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
