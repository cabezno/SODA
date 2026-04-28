from __future__ import annotations

import re
import socket
from typing import Optional


class PortRegistry:
    """Persistent in-memory registry of ports allocated to active projects."""

    _DEFAULT_START = 8100
    _DEFAULT_END = 8999

    def __init__(self, start: int = _DEFAULT_START, end: int = _DEFAULT_END):
        self._start = start
        self._end = end
        # project_id -> port
        self._allocated: dict[str, int] = {}

    def _is_port_free(self, port: int) -> bool:
        """Check whether a TCP port is free on localhost."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            try:
                s.connect(("127.0.0.1", port))
                return False  # something is listening
            except (ConnectionRefusedError, TimeoutError, OSError):
                return True

    def allocate(self, project_id: str) -> int:
        """Return an allocated port for project_id, reusing existing if already registered."""
        if project_id in self._allocated:
            return self._allocated[project_id]
        used = set(self._allocated.values())
        for port in range(self._start, self._end + 1):
            if port not in used and self._is_port_free(port):
                self._allocated[project_id] = port
                return port
        raise RuntimeError(f"No free ports in range {self._start}–{self._end}")

    def release(self, project_id: str) -> Optional[int]:
        """Free the port associated with project_id. Returns the released port or None."""
        return self._allocated.pop(project_id, None)

    def is_in_use(self, port: int) -> bool:
        """Return True if port is registered to any project OR currently bound on localhost."""
        return port in self._allocated.values() or not self._is_port_free(port)

    def get_port(self, project_id: str) -> Optional[int]:
        return self._allocated.get(project_id)

    def snapshot(self) -> dict[str, int]:
        return dict(self._allocated)


class PortManager:
    """Extracts probable HTTP URL/port from runtime commands."""

    @staticmethod
    def infer_url(run_command: str, stack: str) -> str:
        cmd = (run_command or "").lower()
        m_url = re.search(r"https?://[\w\.-]+(?::\d+)?", cmd)
        if m_url:
            return m_url.group(0)

        m_port = re.search(r"(?:--port|-p|port\s*=)\s*(\d{2,5})", cmd)
        if m_port:
            return f"http://127.0.0.1:{m_port.group(1)}"

        if stack == "python":
            return "http://127.0.0.1:8000/health"
        if stack == "node":
            return "http://127.0.0.1:3000/"
        return ""
