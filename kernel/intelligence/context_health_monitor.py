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


class ContextHealthMonitor:
    """Passive monitor — wrap model calls via record(), check health via status()."""

    TOKEN_WARN_THRESHOLD = 80_000   # ~80% of typical 100k limit
    SLOW_CALL_S = 45                # single call taking >45s is notable
    ERROR_RATE_WARN = 0.4           # >40% error rate in last N calls
    ROLLING_WINDOW = 10             # calls to consider for error rate

    def __init__(self, notify_fn: Optional[Callable] = None):
        self._records: list[CallRecord] = []
        self._total_tokens = 0
        self._notify = notify_fn or (lambda msg, t, d: None)

    def record(self, role: str, provider: str, duration_s: float, response: str, success: bool):
        tokens = len(response) // 4  # rough estimate: 4 chars ≈ 1 token
        self._total_tokens += tokens
        rec = CallRecord(role, provider, duration_s, tokens, success)
        self._records.append(rec)
        self._check(rec)

    def _check(self, rec: CallRecord):
        status = self.status()
        if status.level >= 2:
            self._notify(
                f"[ContextHealth L{status.level}] {status.reason}",
                "HEALTH_WARN",
                {"level": status.level, "reason": status.reason, "suggestion": status.suggestion},
            )

    def status(self) -> HealthStatus:
        if self._total_tokens > self.TOKEN_WARN_THRESHOLD:
            return HealthStatus(
                level=3,
                reason=f"Accumulated context ~{self._total_tokens:,} tokens — approaching model limit",
                suggestion="Consider starting a new project or reducing context scope",
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
        }
