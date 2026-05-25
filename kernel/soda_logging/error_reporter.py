"""Centralized error reporting for SODA pipeline phases.

Provides `PhaseReporter` — a thin wrapper that ensures every caught exception
reaches the UI via `_notify()` with full context: phase, file, error type,
truncated traceback, and any caller-supplied extra data.

Usage:
    reporter = PhaseReporter(notify_fn, phase="development")
    with reporter.catch("generate_file", file=filepath):
        code = await driver.call(...)
"""
from __future__ import annotations

import traceback
from contextlib import contextmanager
from typing import Callable, Optional


class PhaseReporter:
    """Wraps a `_notify()` callable and attaches phase context to every error."""

    def __init__(self, notify_fn: Callable, phase: str) -> None:
        self._notify = notify_fn
        self.phase = phase

    def warn(self, message: str, extra: Optional[dict] = None) -> None:
        self._notify(message, "HEALTH_WARN", {"phase": self.phase, **(extra or {})})

    def log(self, message: str, extra: Optional[dict] = None) -> None:
        self._notify(message, "LOG", {"phase": self.phase, **(extra or {})})

    def error(
        self,
        exc: Exception,
        context: str = "",
        extra: Optional[dict] = None,
        level: str = "HEALTH_WARN",
    ) -> None:
        tb = traceback.format_exc()
        msg = f"[{self.phase}] {context + ': ' if context else ''}{type(exc).__name__}: {exc}"
        self._notify(
            msg,
            level,
            {
                "phase": self.phase,
                "context": context,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "traceback": tb[-2000:],  # last 2000 chars of traceback
                **(extra or {}),
            },
        )

    @contextmanager
    def catch(self, context: str = "", reraise: bool = False, extra: Optional[dict] = None):
        """Context manager: catches exceptions, reports them, optionally re-raises."""
        try:
            yield
        except Exception as exc:
            self.error(exc, context=context, extra=extra)
            if reraise:
                raise


def fmt_response(response: str, max_chars: int = 1000) -> str:
    """Return a response snippet suitable for log payloads."""
    if not response:
        return "(vacío)"
    if len(response) <= max_chars:
        return response
    return response[:max_chars] + f"\n...[+{len(response) - max_chars} chars truncados]"
