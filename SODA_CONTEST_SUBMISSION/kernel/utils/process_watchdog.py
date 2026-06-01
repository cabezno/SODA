import os
import psutil
import time
from typing import List, Set, Optional, Any
from pathlib import Path

class ProcessWatchdog:
    """
    SODA FUSION: Guardian de Recursos 2.0.
    """
    def __init__(self, project_id: str, tracker: Optional[Any] = None):
        self.project_id = project_id
        self.tracker = tracker
        self._tracked_pids: Set[int] = set()

    def register(self, pid: int):
        if pid > 0:
            self._tracked_pids.add(pid)
            if self.tracker:
                self.tracker.log_step("RESOURCES", "REGISTER_PID", "OK", f"Trackeando PID {pid}")

    def kill_all(self):
        """
        [IMP-038] ZombieReaper: Mata recursivamente a todos los hijos y procesos registrados.
        """
        if self.tracker:
            self.tracker.log_step("RESOURCES", "KILL_SWITCH", "LOG", "Iniciando siega profunda de procesos (ZombieReaper)...")

        # 1. Registrar hijos actuales de forma recursiva
        try:
            parent = psutil.Process(os.getpid())
            for child in parent.children(recursive=True):
                self._tracked_pids.add(child.pid)
        except Exception: pass

        current_pid = os.getpid()
        killed_count = 0

        # 2. Matar del más joven al más viejo (hijos antes que padres) para evitar procesos huérfanos
        pids = sorted(list(self._tracked_pids), reverse=True)
        for pid in pids:
            if pid == current_pid: continue
            try:
                proc = psutil.Process(pid)
                pname = proc.name()
                proc.kill() # Direct kill para máxima efectividad en automatización
                killed_count += 1
            except Exception: pass

        if self.tracker:
            self.tracker.log_step("RESOURCES", "CLEANUP_DONE", "OK", f"Eliminados {killed_count} procesos residuales.")
        
        self._tracked_pids.clear()
        print(f"🛡️ [WATCHDOG] ZombieReaper: {killed_count} procesos purgados para {self.project_id}.")
