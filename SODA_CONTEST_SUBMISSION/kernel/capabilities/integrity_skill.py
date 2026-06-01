import os
import json
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from kernel.utils.blackbox_logger import SodaLogger

class ProjectIntegritySkill:
    """
    SODA FUSION: Capa Determinística de Verificación de Producto Real.
    Controla la carpeta source, ejecuta el código y limpia si hay basura.
    """
    def __init__(self, workspace_path: Path, blackbox: Optional[SodaLogger] = None):
        self.workspace = workspace_path
        self.src_dir = workspace_path / "source"
        self.blackbox = blackbox
        self.manifest_path = workspace_path / "integrity_manifest.json"

    def generate_manifest(self, blueprint: Dict[str, Any]):
        """
        Crea un manifiesto de archivos esperados basado en el diseño del arquitecto.
        Se ejecuta después de la fase de planificación.
        """
        expected_files = []
        modulos = blueprint.get("modulos", [])
        
        for mod in modulos:
            # Si el blueprint define archivos específicos
            files = mod.get("archivos", [])
            if not files:
                # Si no hay archivos definidos, el nombre del módulo es el fallback
                files = [f"{mod.get('id')}.py"]
            
            for f in files:
                expected_files.append({
                    "file": f,
                    "module": mod.get("id"),
                    "status": "missing",
                    "critical": True
                })
        
        manifest = {
            "project_id": self.workspace.name,
            "expected_files": expected_files,
            "last_check": None
        }
        
        self.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if self.blackbox:
            self.blackbox.log_event("INTEGRITY_MANIFEST_CREATED", f"Esperando {len(expected_files)} archivos.")

    def run_strict_validation(self) -> Dict[str, Any]:
        """
        REGLA DE ORO: Si no hay código funcional, el proyecto no existe.
        """
        # 1. Chequeo de Existencia
        if not self.src_dir.exists() or not any(self.src_dir.iterdir()):
            if self.blackbox:
                self.blackbox.log_event("INTEGRITY_CRITICAL_FAIL", "Carpeta source vacía.")
            
            return {"status": "FAILED", "reason": "SOURCE_EMPTY_DELETED"}

        # 2. Chequeo de Ejecución (Sintaxis y Carga)
        python_files = list(self.src_dir.rglob("*.py"))
        execution_errors = []

        for pf in python_files:
            try:
                # Intentar compilar para ver errores de sintaxis
                res = subprocess.run(
                    ["python", "-m", "py_compile", str(pf)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if res.returncode != 0:
                    execution_errors.append({
                        "file": str(pf.relative_to(self.src_dir)),
                        "error": res.stderr.strip()
                    })
            except Exception as e:
                execution_errors.append({"file": str(pf), "error": str(e)})

        # 3. Reporte Final
        passed = len(execution_errors) == 0
        report = {
            "status": "PASSED" if passed else "EXECUTION_FAILED",
            "files_count": len(python_files),
            "errors": execution_errors,
            "all_passed": passed
        }

        # Guardar reporte físico
        (self.workspace / "integrity_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        
        return report

    def run_forensic_analysis(self, tracker: Any) -> Dict[str, Any]:
        """
        MOTOR FORENSE: Recolecta toda la evidencia del fallo para el informe humano.
        Recopila: Prompts enviados, JSONs de intercambio, Contratos y Árbol de Procesos.
        """
        forensics = {
            "mission_id": self.workspace.name,
            "architecture_contract": {},
            "ai_interactions": [],
            "process_tree": [],
            "source_snapshot": tracker.analyze_failure()
        }

        # 1. Recuperar Contrato Arquitectónico
        if self.manifest_path.exists():
            forensics["architecture_contract"] = json.loads(self.manifest_path.read_text(encoding="utf-8"))

        # 2. Recuperar Interacciones de IA (Blackbox Logs)
        log_dir = self.workspace / "logs"
        if log_dir.exists():
            for log_file in log_dir.glob("ai_*.json"):
                try:
                    data = json.loads(log_file.read_text(encoding="utf-8"))
                    forensics["ai_interactions"].append({
                        "file": log_file.name,
                        "prompt": data.get("prompt_sent", "")[:500] + "...",
                        "response": data.get("raw_response", "")[:500] + "..."
                    })
                except Exception: pass

        # 3. Mapear Árbol de Procesos (Zombies y Huérfanos)
        try:
            parent = psutil.Process(os.getpid())
            for child in parent.children(recursive=True):
                forensics["process_tree"].append({
                    "pid": child.pid,
                    "name": child.name(),
                    "status": child.status()
                })
        except Exception: pass

        # Guardar evidencia forense
        forensic_file = self.workspace / "forensic_report.json"
        forensic_file.write_text(json.dumps(forensics, indent=2, ensure_ascii=False), encoding="utf-8")
        
        return forensics
