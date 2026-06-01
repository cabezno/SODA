import asyncio
import time
import logging
from typing import Dict, Any

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False

class HardwareTelemetry:
    """
    Monitor de recursos de hardware (GPU VRAM) para mitigación de fatiga.
    Utiliza pynvml para leer el estado de la GPU en tiempo real.
    """
    def __init__(self):
        self.enabled = NVML_AVAILABLE
        self._initialized = False
        if self.enabled:
            try:
                pynvml.nvmlInit()
                self._initialized = True
            except Exception as e:
                logging.warning(f"No se pudo inicializar NVML: {e}")
                self.enabled = False

    def get_gpu_status(self) -> Dict[str, Any]:
        if not self.enabled or not self._initialized:
            return {"status": "unavailable"}

        try:
            device_count = pynvml.nvmlDeviceGetCount()
            gpus = []
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpus.append({
                    "id": i,
                    "name": pynvml.nvmlDeviceGetName(handle),
                    "vram_total": info.total / (1024**2),
                    "vram_used": info.used / (1024**2),
                    "vram_free": info.free / (1024**2),
                    "vram_percent": (info.used / info.total) * 100,
                    "gpu_utilization": util.gpu
                })
            return {"status": "ok", "gpus": gpus}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def should_throttle(self, threshold: float = 90.0) -> bool:
        """Indica si se debe reducir la carga de trabajo basado en el uso de VRAM."""
        status = self.get_gpu_status()
        if status["status"] != "ok":
            return False
        
        # Si alguna GPU supera el umbral, recomendamos throttle
        return any(gpu["vram_percent"] > threshold for gpu in status["gpus"])

    def __del__(self):
        if self._initialized:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
