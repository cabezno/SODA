from __future__ import annotations

import json
import logging
import os
import datetime
import queue
import threading
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SODAObservatory:
    """
    SODA Beta Observatory.
    Collects high-fidelity dataset traces in Shadow Mode.
    Uses an in-memory Queue and background Thread to write to disk asynchronously,
    preventing any I/O blocking/latencies in SODA FUSION's main loop.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            # Resolves to SODA_FUSION_ROOT/soda_beta/observatory/data/
            self.base_dir = Path(__file__).resolve().parent.parent / "observatory" / "data"
        else:
            self.base_dir = base_dir

        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[SODA Beta] Observatory active. Storing dataset in: {self.base_dir}")
        except Exception as e:
            logger.error(f"[SODA Beta] Failed to create observatory directories: {e}")

        self.knowledge_file = self.base_dir / "knowledge_traces.jsonl"
        self.repair_file = self.base_dir / "repair_traces.jsonl"

        # Thread-safe in-memory I/O queue and worker
        self._write_queue: queue.Queue[tuple[Path, str]] = queue.Queue()
        self._worker_thread = threading.Thread(target=self._io_worker, daemon=True)
        self._worker_thread.start()

    def _io_worker(self) -> None:
        """Background daemon thread that consumes the queue and writes sequentially to disk."""
        while True:
            try:
                file_path, payload_line = self._write_queue.get()
                try:
                    with open(file_path, mode="a", encoding="utf-8") as f:
                        f.write(payload_line + "\n")
                except Exception as io_err:
                    logger.error(f"[SODA Beta Observatory] Background I/O Error writing to {file_path}: {io_err}")
                finally:
                    self._write_queue.task_done()
            except Exception as thread_err:
                logger.error(f"[SODA Beta Observatory] Critical exception in background I/O thread: {thread_err}")

    def register_success(
        self,
        filepath: str,
        module: dict,
        blueprint: dict,
        architecture: dict,
        code_content: str,
        gbrain_context: Optional[str] = None
    ) -> None:
        """
        Registers a successfully generated code file.
        Enqueues the formatting and payload asynchronously.
        """
        try:
            stack = blueprint.get("stack_sugerido", {})
            module_id = module.get("id") or module.get("nombre", "")
            responsabilidad = module.get("responsabilidad", "")

            instruction = f"Escribe un módulo en {json.dumps(stack, ensure_ascii=False)} que implemente la responsabilidad: {responsabilidad}."
            if gbrain_context:
                instruction += f"\n\nContexto previo recuperado de GBrain:\n{gbrain_context}"

            input_data = (
                f"Archivo a generar: {filepath}\n"
                f"Módulo ID: {module_id}\n"
                f"Dependencias: {json.dumps(module.get('dependencias', []), ensure_ascii=False)}\n"
                f"Contratos: {json.dumps(architecture.get('contratos', []), ensure_ascii=False)}\n"
                f"Endpoints: {json.dumps(module.get('endpoints', []), ensure_ascii=False)}"
            )

            payload = {
                "instruction": instruction,
                "input": input_data,
                "output": code_content,
                "metadata": {
                    "filepath": filepath,
                    "module_id": module_id,
                    "timestamp": datetime.datetime.now().isoformat()
                }
            }

            # Enqueue the write operation instantly
            self._write_queue.put((self.knowledge_file, json.dumps(payload, ensure_ascii=False)))

        except Exception as e:
            logger.warning(f"[SODA Beta Observatory] Error enqueuing success trace: {e}")

    def register_repair(
        self,
        last_failed_code: str,
        last_error_reason: str,
        corrected_code: str,
        filepath: str,
        attempt_num: int
    ) -> None:
        """
        Registers a code-repair action where an error was introduced and then fixed.
        """
        try:
            instruction = "Corrige el siguiente código que tiene un fallo de compilación o error de linter."
            input_data = (
                f"Archivo: {filepath}\n"
                f"Intento de escalación: L{attempt_num}\n\n"
                f"Código Erróneo:\n```\n{last_failed_code}\n```\n\n"
                f"Error de Compilación:\n{last_error_reason}"
            )

            payload = {
                "instruction": instruction,
                "input": input_data,
                "output": corrected_code,
                "metadata": {
                    "filepath": filepath,
                    "attempt": attempt_num,
                    "timestamp": datetime.datetime.now().isoformat()
                }
            }

            # Enqueue the write operation instantly
            self._write_queue.put((self.repair_file, json.dumps(payload, ensure_ascii=False)))

        except Exception as e:
            logger.warning(f"[SODA Beta Observatory] Error enqueuing repair trace: {e}")
