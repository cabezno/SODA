import asyncio
import json
import logging
from pathlib import Path
from shm_bus.manager import SharedMemoryBus
import numpy as np

# Simulación de orquestación de agentes Paperclip
class PaperclipOrchestrator:
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.bus = SharedMemoryBus(f"{project_name}_bus", 1024 * 1024 * 128) # 128MB

    async def execute_heavy_task(self, task_type: str, payload: np.ndarray):
        shm_name = self.bus.create()
        print(f"  [Control Plane] SHM creada: {shm_name}")
        
        # Inyectar datos en el bus
        self.bus.write_ndarray(payload)
        
        # Contrato de metadatos para el Data Plane
        metadata = {
            "task_id": "task_v001",
            "shm_name": shm_name,
            "payload_size": payload.nbytes,
            "gpu_acceleration": True
        }

        # Aquí Paperclip decidiría si dispara Go o C++
        binary = "./data_plane/cpp_vulkan/build/soda_vulkan_node"
        
        print(f"  [Control Plane] Disparando Data Plane: {binary}")
        process = await asyncio.create_subprocess_exec(
            binary,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate(input=json.dumps(metadata).encode())

        if process.returncode == 0:
            result = json.loads(stdout.decode())
            print(f"  [Control Plane] Tarea completada exitosamente: {result}")
        else:
            print(f"  [Control Plane] Error en Data Plane: {stderr.decode()}")

        self.bus.close()

async def main():
    orch = PaperclipOrchestrator("{{ project_name }}")
    # Generar carga de trabajo sintética (Tensor 4K)
    dummy_data = np.random.rand(4096, 4096).astype(np.float32)
    await orch.execute_heavy_task("VULKAN_COMPUTE", dummy_data)

if __name__ == "__main__":
    asyncio.run(main())
