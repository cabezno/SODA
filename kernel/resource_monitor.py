import psutil
import subprocess
import json

class ResourceMonitor:
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
        
        # Regulación Automática:
        # 1. Si hay > 11GB libres, podemos usar 14B (Calidad Máxima)
        if vram["free"] > 11000:
            return "qwen2.5-coder:14b", "GPU_HIGH"
        
        # 2. Si hay entre 6GB y 11GB, bajamos a 7B para no colapsar la GPU
        if vram["free"] > 6000:
            return "qwen2.5-coder:7b", "GPU_LOW"
        
        # 3. Si la GPU está saturada pero la CPU está tranquila, usamos Qwen en RAM o escalamos
        if stats["ram_free_gb"] > 16:
            return "qwen2.5-coder:7b", "CPU_OFFLOAD"
            
        # 4. Emergencia / Saturación total: Escalar a Claude (Cloud)
        return "claude-sonnet", "CLOUD_ESCALATION"

if __name__ == "__main__":
    monitor = ResourceMonitor()
    print(json.dumps({
        "vram": monitor.get_vram_info(),
        "system": monitor.get_system_stats(),
        "recommendation": monitor.get_best_model()
    }, indent=2))