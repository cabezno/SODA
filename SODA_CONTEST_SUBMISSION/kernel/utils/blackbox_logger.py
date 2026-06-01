"""SodaLogger con Correlación de Contexto (Phase/Node tracking)."""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

class SodaLogger:
    def __init__(self, workspace: Optional[Path] = None):
        self.workspace = workspace
        self.log_dir = workspace / "logs" if workspace else Path("logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Estado de contexto actual
        self.current_phase = "IDLE"
        self.current_node = "GLOBAL"
        
        self.logger = logging.getLogger("SODA_BLACKBOX")
        self.logger.setLevel(logging.DEBUG)
        
        # Siempre intentamos añadir el handler del workspace si no existe para ese path
        log_file = self.log_dir / "system_trace.log"
        handler_exists = any(
            isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_file.resolve()
            for h in self.logger.handlers
        )
        
        if not handler_exists:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | [%(phase)s][%(node)s] | %(message)s'))
            self.logger.addHandler(fh)

    def set_context(self, phase: Optional[str] = None, node: Optional[str] = None):
        """Actualiza el contexto actual para que todos los logs futuros estén correlacionados."""
        if phase: self.current_phase = phase
        if node: self.current_node = node

    def log_event(self, event_type: str, message: str, data: Any = None):
        extra = {'phase': self.current_phase, 'node': self.current_node}
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "phase": self.current_phase,
            "node": self.current_node,
            "type": event_type,
            "message": message,
            "data": data
        }
        
        msg = f"[{event_type}] {message}"
        if event_type == "ERROR": self.logger.error(msg, extra=extra)
        elif event_type == "WARNING": self.logger.warning(msg, extra=extra)
        else: self.logger.info(msg, extra=extra)
            
        if self.workspace:
            events_file = self.log_dir / "event_history.jsonl"
            with open(events_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    def log_ai_communication(self, provider: str, model: str, prompt: str, response: str, metadata: dict = None):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_node = "".join([c if c.isalnum() else "_" for c in self.current_node])
        log_file = self.log_dir / f"ai_{safe_node}_{timestamp}.json"
        
        # Determinar si el contexto llega 'limpio' (CMA - Contexto Mínimo Aislado)
        # En SODA V2, casi todas las fases críticas (Arquitectura, Desarrollo, QA) usan contextos aislados por nodo.
        meta = metadata or {}
        phase_lower = self.current_phase.lower()
        is_clean = any(kw in phase_lower for kw in ["arquitectura", "desarrollo", "génesis", "qa", "auditoría"])
        
        comm_data = {
            "timestamp": datetime.now().isoformat(),
            "phase": self.current_phase,
            "node": self.current_node,
            "provider": provider,
            "model": model,
            "context_window_status": "CLEAN (Isolated)" if is_clean else "ACCUMULATED (Historical)",
            "prompt_sent": prompt,
            "raw_response": response,
            "metadata": meta
        }
        
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(comm_data, f, indent=2, ensure_ascii=False)
