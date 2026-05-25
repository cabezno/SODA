import mmap
import posix_ipc
import struct
import numpy as np
from typing import Optional

class SharedMemoryBus:
    """
    Gestor de bus de memoria compartida para SODA.
    Permite el intercambio de tensores y buffers masivos sin copia entre Python y C++.
    """
    def __init__(self, name: str, size_bytes: int):
        self.name = f"/soda_{name}"
        self.size = size_bytes
        self.shm: Optional[posix_ipc.SharedMemory] = None
        self.mm: Optional[mmap.mmap] = None

    def create(self):
        # Eliminar si existe previamente para asegurar limpieza
        try:
            posix_ipc.unlink_shared_memory(self.name)
        except posix_ipc.ExistentialError:
            pass

        self.shm = posix_ipc.SharedMemory(self.name, flags=posix_ipc.O_CREAT, size=self.size)
        self.mm = mmap.mmap(self.shm.fd, self.size)
        return self.name

    def write_ndarray(self, data: np.ndarray, offset: int = 0):
        if not self.mm:
            raise RuntimeError("Bus no inicializado")
        
        view = memoryview(self.mm)
        data_bytes = data.tobytes()
        if offset + len(data_bytes) > self.size:
            raise ValueError("Buffer overflow en Shared Memory")
        
        view[offset:offset+len(data_bytes)] = data_bytes

    def close(self):
        if self.mm:
            self.mm.close()
        if self.shm:
            self.shm.close_fd()
            try:
                posix_ipc.unlink_shared_memory(self.name)
            except:
                pass
