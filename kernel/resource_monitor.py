import psutil
import subprocess
import json
import time
import requests
from pathlib import Path

class ResourceMonitor:
    """Gobernador de Recursos de SODA: Maneja Hardware y Pureza de Contexto."""

    @staticmethod
    def set_mode(mode: str, ollama_model: str = "qwen2.5-coder:14b"):
        """
        Cambia el estado del hardware segun la necesidad.
        mode: 'AI' (Prioriza Ollama, apaga Docker)
              'SANDBOX' (Prioriza Docker, descarga Ollama)
              'IDLE' (Apaga todo para liberar RAM/VRAM)
        """
        print(f"  [RESOURCE_MANAGER] Switching to mode: {mode}")
        
        if mode == "AI":
            # 1. Apagar Docker para liberar RAM de WSL2
            ResourceMonitor.stop_docker()
            # Ollama se cargara solo al recibir la primera peticion.
            
        elif mode == "SANDBOX":
            # 1. Liberar VRAM de Ollama
            ResourceMonitor.unload_ollama(ollama_model)
            # 2. Encender Docker
            ResourceMonitor.start_docker()

        elif mode == "IDLE":
            ResourceMonitor.stop_docker()
            ResourceMonitor.unload_ollama(ollama_model)

    @staticmethod
    def stop_docker():
        """Cierra Docker Desktop de forma ordenada en Windows."""
        try:
            cli = r"C:\Program Files\Docker\Docker\DockerCli.exe"
            if Path(cli).exists():
                subprocess.run([cli, "-Quit"], shell=True, capture_output=True, timeout=15)
                print("  [RESOURCE_MANAGER] Docker Desktop close signal sent.")
        except Exception as e:
            print(f"  [RESOURCE_MANAGER] Error closing Docker: {e}")

    @staticmethod
    def start_docker():
        """Inicia Docker Desktop silenciosamente."""
        try:
            exe = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"
            if Path(exe).exists():
                subprocess.Popen([exe], shell=True)
                print("  [RESOURCE_MANAGER] Docker Desktop starting...")
        except Exception as e:
            print(f"  [RESOURCE_MANAGER] Error starting Docker: {e}")

    @staticmethod
    def unload_ollama(model: str):
        """Descarga el modelo de la VRAM enviando keep_alive: 0."""
        try:
            # Intentamos con la API de generate para forzar el unload
            requests.post("http://localhost:11434/api/generate", 
                          json={"model": model, "keep_alive": 0}, timeout=2)
            print(f"  [RESOURCE_MANAGER] Model {model} unloaded from VRAM.")
        except:
            pass

    @staticmethod
    def get_vram_info():
        """Obtiene la VRAM libre en MB usando nvidia-smi."""
        try:
            res = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.free,memory.total", "--format=csv,nounits,noheader"],
                encoding='utf-8'
            )
            free, total = map(int, res.strip().split(','))
            return {"free": free, "total": total}
        except:
            return {"free": 0, "total": 0}

    @staticmethod
    def get_system_stats():
        """Obtiene CPU y RAM."""
        return {
            "cpu_usage": psutil.cpu_percent(),
            "ram_free_gb": psutil.virtual_memory().available / (1024**3)
        }

    def get_best_model(self):
        """Heurística de auto-regulación de SODA."""
        vram = self.get_vram_info()
        stats = self.get_system_stats()
        
        if vram["free"] > 11000:
            return "qwen2.5-coder:14b", "GPU_HIGH"
        if vram["free"] > 6000:
            return "qwen2.5-coder:7b", "GPU_LOW"
        if stats["ram_free_gb"] > 16:
            return "qwen2.5-coder:7b", "CPU_OFFLOAD"
        return "claude-sonnet", "CLOUD_ESCALATION"

if __name__ == "__main__":
    # Test
    monitor = ResourceMonitor()
    print(f"VRAM: {monitor.get_vram_info()}")
    # monitor.set_mode("IDLE")
