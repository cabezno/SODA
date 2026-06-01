import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class CallRecord:
    role: str
    provider: str
    duration_s: float
    token_estimate: int
    success: bool


@dataclass
class HealthStatus:
    level: int          # 0=ok, 1=observe, 2=warn, 3=critical
    reason: str
    suggestion: str
    suggest_refound: bool = False


class ContextHealthMonitor:
    """Passive monitor — wrap model calls via record(), check health via status()."""

    TOKEN_WARN_THRESHOLD = 80_000   # ~80% of typical 100k limit
    TOKEN_REFOUND_THRESHOLD = 60_000  # sustained growth past here triggers refound suggestion
    SLOW_CALL_S = 30                # single call taking >30s is notable (Qwen normal: 15-25s)
    ERROR_RATE_WARN = 0.5           # >50% error rate — avoids false positives from Qwen×3 escalation bursts
    ROLLING_WINDOW = 15             # wider window smooths short escalation sequences
    # Sustained growth: if last N checkpoints all show growth, suggest refound
    GROWTH_CHECK_WINDOW = 5
    GROWTH_STEP_TOKENS = 3_000      # minimum tokens added per checkpoint to count as "growing"

    def __init__(self, notify_fn: Optional[Callable] = None):
        self._records: list[CallRecord] = []
        self._total_tokens = 0
        self._notify = notify_fn or (lambda msg, t, d: None)
        self._token_snapshots: list[int] = []  # periodic snapshots to detect sustained growth
        self._refound_suggested = False

    def record(self, role: str, provider: str, duration_s: float, response: str, success: bool):
        tokens = len(response) // 4  # rough estimate: 4 chars ≈ 1 token
        self._total_tokens += tokens
        rec = CallRecord(role, provider, duration_s, tokens, success)
        self._records.append(rec)
        # Take a snapshot every 10 calls for growth detection
        if len(self._records) % 10 == 0:
            self._token_snapshots.append(self._total_tokens)
        self._check(rec)

    def _is_context_growing_sustained(self) -> bool:
        """Return True if the last N snapshots all show monotonic growth above threshold."""
        snaps = self._token_snapshots[-self.GROWTH_CHECK_WINDOW:]
        if len(snaps) < self.GROWTH_CHECK_WINDOW:
            return False
        return all(
            snaps[i + 1] - snaps[i] >= self.GROWTH_STEP_TOKENS
            for i in range(len(snaps) - 1)
        )

    def _check(self, rec: CallRecord):
        status = self.status()
        if status.level >= 2:
            self._notify(
                f"[ContextHealth L{status.level}] {status.reason}",
                "HEALTH_WARN",
                {"level": status.level, "reason": status.reason, "suggestion": status.suggestion},
            )
        # Fire refoundation suggestion once when sustained growth is detected
        if status.suggest_refound and not self._refound_suggested:
            self._refound_suggested = True
            self._notify(
                "El contexto del proyecto creció de forma sostenida. Se recomienda refundar el proyecto para reiniciar con contexto comprimido.",
                "REFOUND_SUGGESTED",
                {
                    "total_tokens": self._total_tokens,
                    "reason": "sustained_context_growth",
                    "action": "Podés usar el botón 'Refundar' en la UI o ejecutar refound() en el proyecto.",
                },
            )

    def status(self) -> HealthStatus:
        # Sustained growth check (highest priority signal)
        if (
            self._total_tokens > self.TOKEN_REFOUND_THRESHOLD
            and self._is_context_growing_sustained()
        ):
            return HealthStatus(
                level=2,
                reason=f"Contexto creciendo sostenidamente (~{self._total_tokens:,} tokens estimados)",
                suggestion="Refundar el proyecto liberará contexto y mantendrá el trabajo realizado.",
                suggest_refound=True,
            )

        if self._total_tokens > self.TOKEN_WARN_THRESHOLD:
            return HealthStatus(
                level=2,
                reason=f"Alto uso de tokens en esta sesión (~{self._total_tokens:,} estimados) — solo informativo",
                suggestion="El pipeline continúa normalmente; los errores reales de cuota los maneja el reintento automático",
            )

        window = self._records[-self.ROLLING_WINDOW:]
        if len(window) >= 3:
            error_rate = sum(1 for r in window if not r.success) / len(window)
            if error_rate >= self.ERROR_RATE_WARN:
                return HealthStatus(
                    level=2,
                    reason=f"Error rate {error_rate:.0%} in last {len(window)} calls",
                    suggestion="Escalation to cloud models may be needed",
                )

        slow = [r for r in self._records[-5:] if r.duration_s > self.SLOW_CALL_S]
        if len(slow) >= 2:
            avg = sum(r.duration_s for r in slow) / len(slow)
            return HealthStatus(
                level=1,
                reason=f"Model responses slowing down (avg {avg:.0f}s on recent calls)",
                suggestion="Monitor — may indicate API throttling",
            )

        return HealthStatus(level=0, reason="healthy", suggestion="")

    def summary(self) -> dict:
        s = self.status()
        return {
            "total_calls": len(self._records),
            "total_tokens_estimate": self._total_tokens,
            "error_count": sum(1 for r in self._records if not r.success),
            "health_level": s.level,
            "health_reason": s.reason,
            "suggest_refound": s.suggest_refound,
        }
