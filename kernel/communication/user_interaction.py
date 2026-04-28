import asyncio
import threading
from typing import Optional, Callable


class UserInteractionGateway:
    """
    Pauses the pipeline and waits for a user answer from any channel (UI or Telegram).
    Thread-safe: the Telegram bot runs in a separate event loop/thread.

    The timeout uses a movable deadline so it can be extended while the user is typing.
    """

    TIMEOUT_SECONDS = 14400  # 4 hours — only /fin ends the session explicitly
    EXTEND_SECONDS  = 14400  # reset to 4 hours on each extend() call
    _POLL_INTERVAL  = 2.0   # how often the wait loop re-checks the deadline

    def __init__(self):
        self._question: Optional[str] = None
        self._answer: Optional[str] = None
        self._event: Optional[asyncio.Event] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._deadline: float = 0.0
        self._lock = threading.Lock()

    async def ask(self, question: str, notify_fn: Callable) -> str:
        """Broadcast question and block pipeline until answered or timed out."""
        loop = asyncio.get_event_loop()
        with self._lock:
            self._question = question
            self._answer = None
            self._loop = loop
            self._event = asyncio.Event()
            self._deadline = loop.time() + self.TIMEOUT_SECONDS

        notify_fn(question, "USER_QUESTION", {"question": question})

        try:
            while True:
                with self._lock:
                    remaining = self._deadline - loop.time()
                if remaining <= 0:
                    notify_fn(
                        "Tiempo de espera agotado — continuando sin respuesta.",
                        "LOG", {}
                    )
                    return ""
                try:
                    await asyncio.wait_for(
                        asyncio.shield(self._event.wait()),
                        timeout=min(remaining, self._POLL_INTERVAL),
                    )
                    return self._answer or ""
                except asyncio.TimeoutError:
                    continue  # re-check deadline (may have been extended)
        finally:
            with self._lock:
                self._question = None
                self._event = None

    def extend(self, extra_seconds: int = None) -> bool:
        """Push the timeout deadline forward. Safe to call from any thread."""
        if extra_seconds is None:
            extra_seconds = self.EXTEND_SECONDS
        with self._lock:
            if self._event is None or self._event.is_set():
                return False
            if self._loop is not None:
                self._deadline = self._loop.time() + extra_seconds
            return True

    def answer(self, text: str) -> bool:
        """Resolve the pending question. Safe to call from any thread."""
        with self._lock:
            if self._event is None or self._event.is_set():
                return False
            self._answer = text
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._event.set)
            else:
                self._event.set()
            return True

    @property
    def is_waiting(self) -> bool:
        with self._lock:
            return self._event is not None and not self._event.is_set()

    @property
    def current_question(self) -> Optional[str]:
        return self._question


# Module-level singleton — shared between server.py, orchestrator, and telegram_gateway
_instance: Optional[UserInteractionGateway] = None


def get_gateway() -> UserInteractionGateway:
    global _instance
    if _instance is None:
        _instance = UserInteractionGateway()
    return _instance
