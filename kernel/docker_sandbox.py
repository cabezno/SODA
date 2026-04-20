import docker
import tarfile
import io
import os
import json
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class SandboxResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int


class DockerSandbox:
    """
    Ejecuta código generado en contenedores efímeros aislados.
    Python puro — sin IA.
    """

    IMAGE = "python:3.11-slim"
    MEMORY_LIMIT = "512m"
    CPU_QUOTA = 100_000   # 1 CPU (100% de un core)
    TIMEOUT_SECONDS = 30

    def __init__(self):
        self.client = self._connect()
        self._ensure_image()

    @staticmethod
    def _connect() -> docker.DockerClient:
        # En Windows, Docker Desktop configura un credsStore que el SDK no encuentra en PATH.
        # Solución: apuntar DOCKER_CONFIG a un directorio temporal con config vacío.
        tmp = tempfile.mkdtemp()
        (Path(tmp) / "config.json").write_text(json.dumps({}))
        os.environ["DOCKER_CONFIG"] = tmp
        return docker.DockerClient(base_url="npipe:////./pipe/docker_engine")

    def _ensure_image(self):
        try:
            self.client.images.get(self.IMAGE)
        except docker.errors.ImageNotFound:
            print(f"  [Docker] Descargando imagen {self.IMAGE}...")
            self.client.images.pull(self.IMAGE)

    def _build_tar(self, files: dict[str, str]) -> bytes:
        """Empaqueta {filename: content} en un tar en memoria para copiar al contenedor."""
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for name, content in files.items():
                encoded = content.encode("utf-8")
                info = tarfile.TarInfo(name=name)
                info.size = len(encoded)
                tar.addfile(info, io.BytesIO(encoded))
        buf.seek(0)
        return buf.read()

    def run(
        self,
        code: str,
        test_code: Optional[str] = None,
        extra_files: Optional[dict[str, str]] = None,
        install_packages: Optional[list[str]] = None,
    ) -> SandboxResult:
        """
        Ejecuta `code` en un contenedor aislado.
        Si se provee `test_code`, lo corre como suite de tests después.
        """
        files = {"main.py": code}
        if test_code:
            files["test_main.py"] = test_code
        if extra_files:
            files.update(extra_files)

        # Construir comando de instalación + ejecución
        cmds = []
        if install_packages:
            pkgs = " ".join(install_packages)
            cmds.append(f"pip install -q {pkgs}")

        if test_code:
            cmds.append("python -m pytest test_main.py -v --tb=short 2>&1")
        else:
            cmds.append("python main.py 2>&1")

        shell_cmd = " && ".join(cmds)

        container = None
        start = time.time()
        try:
            container = self.client.containers.create(
                image=self.IMAGE,
                command=["sh", "-c", shell_cmd],
                working_dir="/app",
                mem_limit=self.MEMORY_LIMIT,
                cpu_quota=self.CPU_QUOTA,
                network_mode="none",
                detach=True,
            )

            tar_data = self._build_tar(files)
            container.put_archive("/app", tar_data)
            container.start()

            exited = container.wait(timeout=self.TIMEOUT_SECONDS)
            duration_ms = int((time.time() - start) * 1000)

            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            exit_code = exited.get("StatusCode", -1)

            return SandboxResult(
                success=exit_code == 0,
                stdout=logs,
                stderr="",
                exit_code=exit_code,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return SandboxResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_ms=duration_ms,
            )
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass


def _smoke_test():
    """Test rápido: ejecuta código Python simple en el sandbox."""
    sandbox = DockerSandbox()

    print("=== Smoke test: código simple ===")
    result = sandbox.run(code='print("Sandbox OK — suma:", 2 + 2)')
    print(f"  Exit: {result.exit_code} | {result.duration_ms}ms")
    print(f"  Output: {result.stdout.strip()}")
    assert result.success, f"Falló: {result.stderr}"

    print("\n=== Smoke test: código con error ===")
    result = sandbox.run(code="raise ValueError('error intencional')")
    print(f"  Exit: {result.exit_code} | {result.duration_ms}ms")
    print(f"  Output: {result.stdout.strip()}")
    assert not result.success

    print("\n[✓] DockerSandbox operativo.")


if __name__ == "__main__":
    _smoke_test()
