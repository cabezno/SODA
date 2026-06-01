import os
import subprocess
from pathlib import Path
from typing import Optional, Callable

class GitSentinel:
    """
    IMP-040: Automated Git state manager for SODA missions.
    Ensures every phase transition is backed by an atomic commit.
    Allows for automatic rollbacks if integrity gates fail.
    """
    def __init__(self, workspace: Path, notify_fn: Optional[Callable] = None):
        self.workspace = workspace
        self.notify = notify_fn

    def _log(self, msg: str, event_type: str = "LOG"):
        if self.notify:
            self.notify(msg, event_type)
        else:
            print(f"[GitSentinel] {msg}")

    def _run_git(self, args: list[str]) -> bool:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.workspace), *args],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            self._log(f"Error ejecutando Git: {e}", "ERROR")
            return False

    def ensure_repo(self):
        """Inicializa un repositorio Git si no existe en el espacio de trabajo."""
        if not (self.workspace / ".git").exists():
            self._log("Inicializando repositorio Git para el proyecto...", "LOG")
            self._run_git(["init"])
            # Configuración mínima local
            self._run_git(["config", "user.name", "SODA Sentinel"])
            self._run_git(["config", "user.email", "sentinel@soda.ai"])

    def commit_phase(self, phase_name: str):
        """Realiza un commit atómico del estado actual de la fase."""
        self.ensure_repo()
        
        # [IMP-040] State Ledger: Inmortalidad de Fase
        self._generate_manifest()
        
        self._run_git(["add", "."])
        # Comprobar si hay algo que commitear
        status = subprocess.run(["git", "-C", str(self.workspace), "status", "--porcelain"], capture_output=True, text=True)
        if not status.stdout.strip():
            return # Sin cambios

        self._log(f"Consolidando estado de la fase: {phase_name}", "SUCCESS")
        self._run_git(["commit", "-m", f"SODA PHASE: {phase_name} completed."])

    def _generate_manifest(self):
        """Genera el State Ledger (.soda_manifest.json) del estado actual."""
        import json
        import hashlib
        from datetime import datetime
        
        manifest = {
            "version": "4.0",
            "timestamp": datetime.now().isoformat(),
            "phase": "UNKNOWN",
            "files": {}
        }
        
        for root, _, files in os.walk(self.workspace):
            if ".git" in root: continue
            for file in files:
                if file == ".soda_manifest.json": continue
                p = Path(root) / file
                rel = p.relative_to(self.workspace)
                
                try:
                    content = p.read_bytes()
                    h = hashlib.md5(content).hexdigest()
                    manifest["files"][str(rel).replace("\\", "/")] = {
                        "size": len(content),
                        "hash": h
                    }
                except Exception: pass
                
        manifest_path = self.workspace / ".soda_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def rollback(self):
        """Revierte el espacio de trabajo al último commit estable."""
        self._log("REVERSIÓN DE EMERGENCIA: Restaurando último estado estable...", "WARNING")
        self._run_git(["reset", "--hard", "HEAD"])
        self._run_git(["clean", "-fd"])
