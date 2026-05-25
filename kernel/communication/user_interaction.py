import asyncio
import threading
import time
import json
from pathlib import Path
from typing import Optional, Callable


class UserInteractionGateway:
    """
    Pauses the pipeline and waits for a user answer from any channel (UI or Telegram).
    Supports Cross-Process synchronization via file-based signaling in the workspace.
    """

    TIMEOUT_SECONDS = 14400  # 4 hours
    EXTEND_SECONDS  = 14400
    _POLL_INTERVAL  = 2.0

    def __init__(self):
        self._question: Optional[str] = None
        self._answer: Optional[str] = None
        self._deadline: float = 0.0
        self._lock = threading.Lock()

    def answer(self, text: Optional[str]) -> bool:
        """Resolve the pending question. Safe to call from any thread."""
        with self._lock:
            if self._question is None or self._answer is not None:
                return False
            self._answer = str(text or "").strip()
            return True

    @property
    def is_waiting(self) -> bool:
        with self._lock:
            return self._question is not None and self._answer is None

    @property
    def current_question(self) -> Optional[str]:
        return self._question

    async def ask(self, question: str, notify_fn: Callable, workspace: Optional[Path] = None) -> str:
        """Broadcast question and block pipeline until answered or timed out."""
        with self._lock:
            self._question = str(question)
            self._answer = None
            self._deadline = time.time() + self.TIMEOUT_SECONDS

        # 1. Registro de señal para otros procesos (UI Bridge)
        if workspace:
            try:
                q_file = workspace / ".pending_question"
                q_file.write_text(json.dumps({
                    "question": str(question),
                    "timestamp": time.time()
                }), encoding="utf-8")
                
                # Asegurar que no haya respuesta vieja
                a_file = workspace / ".pending_answer"
                if a_file.exists(): a_file.unlink()
            except Exception: pass

        # 2. Notificación a canales activos
        notify_fn(str(question), "USER_QUESTION", {"question": str(question)})

        try:
            while True:
                with self._lock:
                    remaining = self._deadline - time.time()
                
                if remaining <= 0:
                    if workspace:
                        q_file = workspace / ".pending_question"
                        if q_file.exists(): q_file.unlink()
                    notify_fn("LOG", "Tiempo de espera agotado — continuando sin respuesta.", {})
                    return ""

                # A. Verificar respuesta en memoria (Mismo proceso)
                with self._lock:
                    if self._answer is not None:
                        if workspace:
                            q_file = workspace / ".pending_question"
                            if q_file.exists(): q_file.unlink()
                        return self._answer

                # B. Verificar respuesta en disco (Proceso externo como UI Server)
                if workspace:
                    a_file = workspace / ".pending_answer"
                    if a_file.exists():
                        try:
                            ans_data = json.loads(a_file.read_text(encoding="utf-8"))
                            ans_text = ans_data.get("answer", "")
                            a_file.unlink() # Limpiar
                            q_file = workspace / ".pending_question"
                            if q_file.exists(): q_file.unlink()
                            return ans_text
                        except Exception: pass

                await asyncio.sleep(self._POLL_INTERVAL)
        finally:
            with self._lock:
                self._question = None
                self._answer = None

    def extend(self, extra_seconds: int = None) -> bool:
        if extra_seconds is None:
            extra_seconds = self.EXTEND_SECONDS
        with self._lock:
            if self._question is None or self._answer is not None:
                return False
            self._deadline = time.time() + extra_seconds
            return True

_instance: Optional[UserInteractionGateway] = None

def get_gateway() -> UserInteractionGateway:
    global _instance
    if _instance is None:
        _instance = UserInteractionGateway()
    return _instance
