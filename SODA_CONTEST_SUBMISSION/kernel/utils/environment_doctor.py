import sys
import subprocess
import importlib.metadata
from pathlib import Path
from typing import List, Callable, Optional

class EnvironmentDoctor:
    """
    IMP-039: Auto-healing dependency manager.
    Ensures SODA environment is always healthy by auto-installing missing requirements.
    """
    def __init__(self, requirements_path: Path, notify_fn: Optional[Callable] = None):
        self.requirements_path = requirements_path
        self.notify = notify_fn

    def _log(self, msg: str, event_type: str = "LOG"):
        if self.notify:
            self.notify(msg, event_type)
        else:
            print(f"[EnvironmentDoctor] {msg}")

    def check_and_fix(self) -> bool:
        """Checks for missing dependencies and attempts to install them."""
        # 1. Chequeo de Docker (Pre-flight)
        self.check_docker()

        # 2. Chequeo de dependencias Python
        if not self.requirements_path.exists():
            self._log("requirements.txt no encontrado. Saltando chequeo.", "WARNING")
            return True

        self._log("Escaneando salud del entorno Python...", "LOG")
        
        try:
            with open(self.requirements_path, "r", encoding="utf-8") as f:
                requirements = [
                    line.strip().split(">=")[0].split("==")[0]
                    for line in f 
                    if line.strip() and not line.startswith("#")
                ]
        except Exception as e:
            self._log(f"Error al leer requirements: {e}", "ERROR")
            return False

        missing = []
        installed_pkgs = {dist.metadata["Name"].lower().replace("-", "_") for dist in importlib.metadata.distributions()}
        
        for req in requirements:
            # Clean requirement name
            clean_req = req.lower().replace("-", "_")
            if clean_req not in installed_pkgs and req.lower() not in installed_pkgs:
                missing.append(req)

        if not missing:
            self._log("Entorno saludable. Todas las dependencias están presentes.", "SUCCESS")
            return True

        self._log(f"Detectadas {len(missing)} dependencias faltantes: {', '.join(missing)}", "WARNING")
        self._log("Iniciando auto-instalación de emergencia...", "LOG")

        try:
            # Ejecutar pip install en el mismo venv/python que corre SODA
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", *missing],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self._log("Entorno reparado exitosamente.", "SUCCESS")
                return True
            else:
                self._log(f"Fallo al instalar dependencias: {result.stderr}", "ERROR")
                return False
        except Exception as e:
            self._log(f"Error crítico en EnvironmentDoctor: {e}", "ERROR")
            return False

    def check_docker(self) -> bool:
        """Verifica si el motor de Docker está corriendo."""
        self._log("Verificando estado de Docker Engine...", "LOG")
        try:
            # Usar npipe para Windows por defecto
            import docker
            client = docker.DockerClient(base_url="npipe:////./pipe/docker_engine")
            client.ping()
            self._log("Docker Engine detectado y operativo.", "SUCCESS")
            return True
        except ImportError:
            self._log("Librería 'docker' (SDK) no disponible.", "WARNING")
            return False
        except Exception:
            self._log("Docker Engine no responde. SODA requiere Docker para validación segura.", "WARNING")
            return False
