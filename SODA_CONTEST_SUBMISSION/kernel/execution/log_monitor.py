from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


@dataclass
class LogEntry:
    line: str
    severity: str   # "INFO" | "WARN" | "ERROR" | "DEBUG"
    source: str     # file path being monitored
    timestamp: float = field(default_factory=time.monotonic)

    def to_dict(self) -> dict:
        return {
            "line": self.line,
            "severity": self.severity,
            "source": self.source,
            "timestamp": self.timestamp,
        }


_SEVERITY_PATTERNS: list[tuple[str, str]] = [
    # Check ERROR/CRITICAL before WARN before INFO
    ("ERROR",    ("error", "exception", "traceback", "fatal", "critical", "fail")),
    ("WARN",     ("warn", "warning", "deprecated", "caution")),
    ("DEBUG",    ("debug", "trace", "verbose")),
    ("INFO",     ()),  # default
]


def _classify(line: str) -> str:
    lower = line.lower()
    for severity, keywords in _SEVERITY_PATTERNS:
        if keywords and any(k in lower for k in keywords):
            return severity
    return "INFO"


class LogMonitor:
    """
    Tails a log file produced by a running project and streams parsed entries
    to an `on_entry` callback in a background thread.

    Usage:
        monitor = LogMonitor(log_path, on_entry=lambda e: print(e))
        monitor.start()
        ...
        monitor.stop()
    """

    POLL_INTERVAL = 0.5   # seconds between tail polls
    MAX_LINE_LEN  = 500   # truncate very long lines

    def __init__(
        self,
        log_path: Path,
        on_entry: Optional[Callable[[LogEntry], None]] = None,
        max_history: int = 200,
    ):
        self.log_path = Path(log_path)
        self.on_entry = on_entry or (lambda e: None)
        self.max_history = max_history
        self._history: list[LogEntry] = []
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start tailing the log file in a background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._tail_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop tailing."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)

    @property
    def history(self) -> list[LogEntry]:
        with self._lock:
            return list(self._history)

    def last_errors(self, n: int = 10) -> list[LogEntry]:
        with self._lock:
            return [e for e in self._history if e.severity == "ERROR"][-n:]

    def summary(self) -> dict:
        with self._lock:
            counts = {"INFO": 0, "WARN": 0, "ERROR": 0, "DEBUG": 0}
            for e in self._history:
                counts[e.severity] = counts.get(e.severity, 0) + 1
        return {"total": sum(counts.values()), **counts}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _tail_loop(self) -> None:
        offset = 0
        # If file already exists, start from end (don't replay history)
        if self.log_path.exists():
            offset = self.log_path.stat().st_size

        while not self._stop_event.wait(self.POLL_INTERVAL):
            if not self.log_path.exists():
                continue
            try:
                size = self.log_path.stat().st_size
                if size < offset:
                    offset = 0   # file was rotated/truncated
                if size == offset:
                    continue
                with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(offset)
                    new_text = f.read(size - offset)
                    offset = f.tell()
                for raw_line in new_text.splitlines():
                    line = raw_line[: self.MAX_LINE_LEN].rstrip()
                    if not line:
                        continue
                    entry = LogEntry(
                        line=line,
                        severity=_classify(line),
                        source=str(self.log_path),
                    )
                    with self._lock:
                        self._history.append(entry)
                        if len(self._history) > self.max_history:
                            self._history = self._history[-self.max_history :]
                    try:
                        self.on_entry(entry)
                    except Exception:
                        pass
            except Exception:
                pass
