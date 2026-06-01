import os
import subprocess
import shlex
import shutil
from typing import Protocol, List, Dict, Optional, Set
from pathlib import Path

# Comandos permitidos en el sandbox — todo lo demás es rechazado
SANDBOX_ALLOWLIST: Set[str] = {
    "python", "python3", "pip", "pip3", "npm", "npx", "node",
    "git", "ls", "cat", "echo", "mkdir", "cp", "mv", "rm", "touch",
    "chmod", "pwd", "which", "docker", "docker-compose", "make",
    "gcc", "g++", "rustc", "cargo", "go", "java", "javac",
    "poetry", "uv", "rye", "conda", "mamba",
}

# Metacaracteres de shell prohibidos en comandos
FORBIDDEN_SHELL_CHARS: Set[str] = {"|", ">", "<", "&&", "||", ";", "`", "$(", "${"}

class ExecutionResult(Protocol):
    exit_code: int
    stdout: str
    stderr: str

class SandboxInterface(Protocol):
    def run_command(self, command: str) -> Dict[str, str]: ...
    def write_file(self, path: str, content: str) -> None: ...

class DockerSandbox:
    """
    SODA FUSION Sandbox: Maneja ejecución en Docker con fallback a Local si Docker falla.
    """
    def __init__(self, image: str = "soda-runtime:latest", workspace_dir: str = "./workspace"):
        self.image = image
        self.workspace_path = Path(workspace_dir).absolute()
        self.container = None
        self.use_local = False

        if not os.path.exists(self.workspace_path):
            os.makedirs(self.workspace_path)

        try:
            import docker
            self.client = docker.from_env()
            self.client.ping()
        except Exception:
            print("[SANDBOX] Docker no detectado o no disponible. Usando modo LOCAL (Host).")
            self.client = None
            self.use_local = True

    def start(self):
        if self.use_local:
            print("[SANDBOX] Iniciando Sandbox en modo LOCAL.")
            return self

        try:
            self.container = self.client.containers.run(
                self.image,
                detach=True,
                tty=True,
                volumes={str(self.workspace_path): {'bind': '/app', 'mode': 'rw'}},
                working_dir='/app',
                network_disabled=False
            )
        except Exception as e:
            print(f"[SANDBOX] Error al iniciar contenedor: {e}. Reintentando en modo LOCAL.")
            self.use_local = True
        return self

    def run_command(self, command: str) -> Dict[str, str]:
        # Sanitizar: validar comando contra allowlist y prohibir metacaracteres
        sanitized = self._sanitize_command(command)
        
        if self.use_local:
            try:
                result = subprocess.run(
                    shlex.split(sanitized),
                    shell=False,
                    cwd=str(self.workspace_path),
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                return {
                    "exit_code": result.returncode,
                    "output": result.stdout + result.stderr
                }
            except subprocess.TimeoutExpired as e:
                return {
                    "exit_code": -1,
                    "output": f"Timeout: {str(e)}"
                }
            except ValueError as e:
                return {
                    "exit_code": -1,
                    "output": f"Command rejected: {str(e)}"
                }
            except Exception as e:
                return {
                    "exit_code": -1,
                    "output": f"Error en ejecución local: {str(e)}"
                }

        if not self.container:
            raise RuntimeError("Sandbox no iniciado")

        exec_res = self.container.exec_run(command)
        return {
            "exit_code": exec_res.exit_code,
            "output": exec_res.output.decode('utf-8', errors='replace')
        }

    def _sanitize_command(self, raw: str) -> str:
        """Valida y sanitiza un comando antes de ejecutarlo."""
        raw = raw.strip()
        if not raw:
            raise ValueError("Comando vacío")
        
        # Rechazar metacaracteres de shell
        for char in FORBIDDEN_SHELL_CHARS:
            if char in raw:
                raise ValueError(f"Metacaracter de shell prohibido: '{char}' en: {raw[:100]}")
        
        # Extraer el comando base
        tokens = shlex.split(raw)
        if not tokens:
            raise ValueError("No se pudieron parsear los tokens del comando")
        
        base_cmd = os.path.basename(tokens[0])
        if base_cmd not in SANDBOX_ALLOWLIST:
            raise ValueError(
                f"Comando '{base_cmd}' no está en la lista de permitidos. "
                f"Usá uno de: {', '.join(sorted(SANDBOX_ALLOWLIST)[:20])}..."
            )
        
        return raw

    def write_file(self, relative_path: str, content: str) -> None:
        full_path = self.workspace_path / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    def stop(self):
        if self.use_local:
            return

        if self.container:
            try:
                self.container.stop()
                self.container.remove()
            except Exception: pass