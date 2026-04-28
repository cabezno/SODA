"""
Terminal session manager for SODA's embedded terminal.
Each session wraps an asyncio subprocess with bidirectional I/O and an output ring buffer.
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable


_OUTPUT_BUFFER_BYTES = 100_000  # 100 KB ring buffer per session


@dataclass
class TerminalSession:
    session_id: str
    project_id: str
    command: str
    cwd: str
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    proc: object = field(repr=False, default=None)       # asyncio.subprocess.Process
    _buffer: bytearray = field(repr=False, default_factory=bytearray)
    _send_fn: Optional[Callable] = field(repr=False, default=None)  # WebSocket send callable
    alive: bool = True

    def append_output(self, data: bytes) -> None:
        self._buffer.extend(data)
        if len(self._buffer) > _OUTPUT_BUFFER_BYTES:
            # Drop oldest bytes, keep tail
            self._buffer = self._buffer[-_OUTPUT_BUFFER_BYTES:]

    def get_output(self) -> str:
        return self._buffer.decode("utf-8", errors="replace")

    def is_alive(self) -> bool:
        if self.proc is None:
            return False
        return self.proc.returncode is None

    def kill(self) -> None:
        self.alive = False
        if self.proc and self.proc.returncode is None:
            try:
                self.proc.kill()
            except Exception:
                pass

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "command": self.command,
            "cwd": self.cwd,
            "started_at": self.started_at,
            "alive": self.is_alive(),
            "buffer_bytes": len(self._buffer),
        }


# Global registry
_SESSIONS: dict[str, TerminalSession] = {}


class TerminalSessionManager:
    """Create, track, and tear down terminal sessions."""

    @staticmethod
    def create(session_id: str, project_id: str, command: str, cwd: str) -> TerminalSession:
        session = TerminalSession(
            session_id=session_id,
            project_id=project_id,
            command=command,
            cwd=cwd,
        )
        _SESSIONS[session_id] = session
        return session

    @staticmethod
    def get(session_id: str) -> Optional[TerminalSession]:
        return _SESSIONS.get(session_id)

    @staticmethod
    def list_sessions() -> list[dict]:
        return [s.to_dict() for s in _SESSIONS.values()]

    @staticmethod
    def kill(session_id: str) -> bool:
        s = _SESSIONS.get(session_id)
        if s:
            s.kill()
            _SESSIONS.pop(session_id, None)
            return True
        return False

    @staticmethod
    def kill_all() -> None:
        for s in list(_SESSIONS.values()):
            s.kill()
        _SESSIONS.clear()

    @staticmethod
    async def launch(
        session: TerminalSession,
        on_output: Callable[[bytes], None],
        on_exit: Callable[[int], None],
    ) -> bool:
        """Spawn the subprocess and start streaming output. Returns False on launch failure."""
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        # Ensure colors in subprocess output
        env["FORCE_COLOR"] = "1"
        env["TERM"] = "xterm-256color"

        try:
            proc = await asyncio.create_subprocess_shell(
                session.command,
                cwd=session.cwd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
            session.proc = proc

            async def _read_loop():
                try:
                    while True:
                        chunk = await proc.stdout.read(1024)
                        if not chunk:
                            break
                        session.append_output(chunk)
                        on_output(chunk)
                except Exception:
                    pass
                finally:
                    rc = proc.returncode if proc.returncode is not None else await proc.wait()
                    session.alive = False
                    on_exit(rc or 0)

            asyncio.create_task(_read_loop())
            return True
        except Exception as e:
            err = f"\r\n[SODA Terminal] Error al lanzar proceso: {e}\r\n"
            on_output(err.encode())
            on_exit(-1)
            return False

    @staticmethod
    async def send_input(session: TerminalSession, data: str) -> None:
        """Write keystrokes/commands to the subprocess stdin."""
        if session.proc and session.proc.stdin and session.is_alive():
            try:
                session.proc.stdin.write(data.encode("utf-8", errors="replace"))
                await session.proc.stdin.drain()
            except Exception:
                pass
