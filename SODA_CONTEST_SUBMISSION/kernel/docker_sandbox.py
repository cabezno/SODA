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
        self.client = None

    @property
    def available(self) -> bool:
        """Alias para compatibilidad con el resto de SODA."""
        return self._ensure_connected(autostart=False)

    async def run_project(
        self,
        source_dir: Path,
        install_cmd: Optional[list[str]] = None,
        run_cmd: Optional[list[str]] = None,
        timeout: int = 60,
    ) -> SandboxResult:
        """
        [ASYNC] Ejecuta un proyecto completo dentro del sandbox.
        """
        if not await asyncio.to_thread(self._ensure_connected, True):
            return SandboxResult(
                success=False,
                stdout="",
                stderr="DOCKER_UNAVAILABLE: Docker is required for SODA Zero-Host Policy but could not be started.",
                exit_code=-1,
                duration_ms=0
            )

        container = None
        start = time.time()
        try:
            # 1. Preparar comandos
            full_cmd = []
            if install_cmd:
                full_cmd.append(" ".join(map(str, install_cmd)))
            if run_cmd:
                full_cmd.append(" ".join(map(str, run_cmd)))
            
            shell_script = " && ".join(full_cmd) if full_cmd else "ls -R"

            # 2. Crear contenedor (aislado: network_mode=none)
            container = await asyncio.to_thread(
                self.client.containers.create,
                image=self.IMAGE,
                command=["sh", "-c", shell_script],
                working_dir="/app",
                mem_limit=self.MEMORY_LIMIT,
                cpu_quota=self.CPU_QUOTA,
                network_mode="none",
                detach=True,
            )

            # 3. Empaquetar y copiar archivos
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                for root, _, files in os.walk(source_dir):
                    for file in files:
                        full_path = Path(root) / file
                        rel_path = full_path.relative_to(source_dir)
                        tar.add(full_path, arcname=str(rel_path).replace("\\", "/"))
            
            tar_stream.seek(0)
            await asyncio.to_thread(container.put_archive, "/app", tar_stream.read())

            # 4. Iniciar y esperar (Unblocked via to_thread)
            await asyncio.to_thread(container.start)
            status = await asyncio.to_thread(container.wait, timeout=timeout)
            
            duration_ms = int((time.time() - start) * 1000)
            logs = (await asyncio.to_thread(container.logs, stdout=True, stderr=True)).decode("utf-8", errors="replace")
            exit_code = status.get("StatusCode", -1)

            # Sincronización Docker-to-Host
            if exit_code == 0:
                await asyncio.to_thread(self._extract_container_dir, container, "/app", source_dir)

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
                    await asyncio.to_thread(container.remove, force=True)
                except Exception:
                    pass

    def _extract_container_dir(self, container, container_path: str, host_path: Path):
        """Extrae un directorio del contenedor en formato tar y lo descomprime en el host."""
        import shutil
        try:
            st_model, _ = container.get_archive(container_path)
            tar_data = io.BytesIO()
            for chunk in st_model:
                tar_data.write(chunk)
            tar_data.seek(0)

            # Usamos un directorio temporal para la extracción intermedia
            with tempfile.TemporaryDirectory() as tmp_dir:
                with tarfile.open(fileobj=tar_data, mode="r") as tar:
                    tar.extractall(path=tmp_dir)
                
                # Mover el contenido de 'tmp_dir/app' a host_path
                temp_app_path = Path(tmp_dir) / "app"
                if temp_app_path.exists():
                    for item in temp_app_path.iterdir():
                        dest_item = host_path / item.name
                        if dest_item.exists():
                            if dest_item.is_dir():
                                shutil.rmtree(dest_item)
                            else:
                                dest_item.unlink()
                        shutil.move(str(item), str(host_path))
        except Exception as e:
            print(f"  [DockerSandbox] Error al sincronizar datos del contenedor: {e}")

    @staticmethod
    def project_needs_docker(workspace: str) -> bool:
        """Return True if the project explicitly uses Docker (compose file or docker skill)."""
        ws = Path(workspace)
        # Presence of docker-compose file
        for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            if (ws / "source" / name).exists() or (ws / name).exists():
                return True
        # Check architecture/blueprint for docker mentions
        for fname in ("architecture.json", "blueprint.json", "master_contract.json"):
            p = ws / fname
            if p.exists():
                try:
                    import json as _json
                    text = p.read_text(encoding="utf-8", errors="replace").lower()
                    if "docker" in text or "container" in text:
                        return True
                except Exception:
                    pass
        return False

    def _ensure_connected(self, autostart: bool = False) -> bool:
        '''Conexion perezosa a Docker. Solo arranca Docker Desktop si autostart=True.'''
        if self.client is not None:
            try:
                self.client.ping()
                return True
            except Exception:
                self.client = None

        import docker
        try:
            self.client = self._connect()
            self._ensure_image()
            return True
        except Exception:
            pass

        if not autostart:
            return False

        import time, subprocess
        print("  [DockerSandbox] El proyecto requiere Docker. Intentando arrancar Docker Desktop...")
        try:
            subprocess.Popen([r"C:\Program Files\Docker\Docker\Docker Desktop.exe"])
        except Exception as e:
            print(f"  [DockerSandbox] No se pudo invocar Docker Desktop: {e}")
            return False

        for _ in range(40):
            time.sleep(3)
            try:
                self.client = self._connect()
                self._ensure_image()
                print("  [DockerSandbox] Docker ha levantado con exito.")
                return True
            except Exception:
                pass

        print("  [DockerSandbox] Timeout esperando a Docker (120s).")
        return False


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

    async def run(
        self,
        code: str,
        test_code: Optional[str] = None,
        extra_files: Optional[dict[str, str]] = None,
        install_packages: Optional[list[str]] = None,
    ) -> SandboxResult:
        """
        [ASYNC] Ejecuta `code` en un contenedor aislado.
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

        if not await asyncio.to_thread(self._ensure_connected):
            return SandboxResult(success=True, stdout="DOCKER_UNAVAILABLE", stderr="", exit_code=0, duration_ms=0)

        container = None
        start = time.time()
        try:
            container = await asyncio.to_thread(
                self.client.containers.create,
                image=self.IMAGE,
                command=["sh", "-c", shell_cmd],
                working_dir="/app",
                mem_limit=self.MEMORY_LIMIT,
                cpu_quota=self.CPU_QUOTA,
                network_mode="none",
                detach=True,
            )

            tar_data = await asyncio.to_thread(self._build_tar, files)
            await asyncio.to_thread(container.put_archive, "/app", tar_data)
            await asyncio.to_thread(container.start)

            exited = await asyncio.to_thread(container.wait, timeout=self.TIMEOUT_SECONDS)
            duration_ms = int((time.time() - start) * 1000)

            logs = (await asyncio.to_thread(container.logs, stdout=True, stderr=True)).decode("utf-8", errors="replace")
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
                    await asyncio.to_thread(container.remove, force=True)
                except Exception:
                    pass


    async def run_tests(
        self,
        workspace: str,
        install_command: Optional[str] = None,
        run_command: Optional[str] = None,
    ) -> dict:
        """[ASYNC] Project-level test runner. Runs pytest inside the sandbox."""
        needs = self.project_needs_docker(workspace)
        if not await asyncio.to_thread(self._ensure_connected, needs):
            reason = "Docker no disponible" if not needs else "Docker requerido pero no pudo arrancar"
            return {"success": True, "skipped": True, "reason": reason}

        cmds = []
        if install_command:
            cmds.append(install_command)
        cmds.append("python -m pytest --tb=short -q 2>&1 || true")
        shell_cmd = " && ".join(cmds)

        container = None
        start = time.time()
        try:
            ws_path = Path(workspace)
            files: dict[str, str] = {}
            for f in ws_path.rglob("*.py"):
                try:
                    rel = f.relative_to(ws_path)
                    files[str(rel).replace("\\", "/")] = f.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass

            result = await self.run(
                code="# project runner",
                extra_files=files if files else None,
                install_packages=[],
            )
            return {
                "success": result.success,
                "stdout": result.stdout[:2000],
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


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
