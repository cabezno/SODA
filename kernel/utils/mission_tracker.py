import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

class MissionTracker:
    """
    SODA FUSION: Rastreador de Pasos Críticos.
    Registra cada hito de la misión para que, si falla la integridad física,
    podamos saber exactamente en qué paso se perdió el código.
    """
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.trace_path = workspace / "mission_trace.jsonl"
        self.start_time = time.time()
        self.steps = []

    def log_step(self, phase: str, step_name: str, status: str, details: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """Registra un paso con metadatos para análisis forense (prompts, JSONs, etc)."""
        entry = {
            "timestamp": time.time() - self.start_time,
            "phase": phase,
            "step": step_name,
            "status": status,
            "details": details,
            "forensics": metadata or {}
        }
        self.steps.append(entry)
        with open(self.trace_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def get_full_report(self) -> str:
        """Genera un reporte legible del rastro de la misión."""
        report = f"--- REPORTE DE RASTREO (Misión: {self.workspace.name}) ---\n"
        for s in self.steps:
            mark = "✅" if s["status"] == "OK" else "❌" if s["status"] == "FAIL" else "🕒"
            report += f"[{s['timestamp']:.2f}s] {mark} {s['phase']} -> {s['step']}: {s['details'] or ''}\n"
        return report

    def analyze_failure(self) -> str:
        """Analiza dónde se rompió la cadena de producción."""
        if not self.steps:
            return "No se registraron pasos."
        
        last_ok = None
        for s in self.steps:
            if s["status"] == "OK":
                last_ok = s
            elif s["status"] == "FAIL":
                return f"EL FALLO OCURRIÓ AQUÍ: Fase {s['phase']}, Paso {s['step']}. Detalle: {s['details']}"
        
        if last_ok:
            return f"El último paso exitoso fue: {last_ok['step']} ({last_ok['phase']}). El proceso se detuvo después de esto."
        return "Fallo indeterminado."
