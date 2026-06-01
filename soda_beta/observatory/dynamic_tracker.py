from __future__ import annotations

import json
import logging
import re
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class DynamicTracker:
    """
    SODA Beta Dynamic Runtime & Process Tracker (Capa Dinámica).
    Intercepts API calls, runtime process executions, and telemetry logs,
    and dynamically routes them to specialized training 'sectors' (silos)
    based on real-time classification.
    """

    def __init__(self, sectors_dir: Optional[Path] = None):
        if sectors_dir is None:
            # Resolves to SODA_FUSION_ROOT/soda_beta/observatory/data/sectors/
            self.sectors_dir = Path(__file__).resolve().parent.parent / "observatory" / "data" / "sectors"
        else:
            self.sectors_dir = sectors_dir

        try:
            self.sectors_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[SODA Beta] Dynamic sectors directory initialized at: {self.sectors_dir}")
        except Exception as e:
            logger.error(f"[SODA Beta] Failed to initialize sectors directory: {e}")

        # Core heuristic categories for dynamic routing (The Sector Router)
        self.sector_rules = {
            "vulkan_gpu_systems": r"\b(vulkan|cuda|vram|gpu|graphics|render|shader|comp\b|device_map)\b",
            "api_contract_design": r"\b(fastapi|endpoint|http|request|response|payload|router|route|api|websocket)\b",
            "hardware_telemetry_opt": r"\b(latency|tokens_per_second|nvml|nvidia|cpu_percent|ram_usage|metrics|telemetry)\b",
            "git_and_transactions": r"\b(git|sentinel|commit|rollback|checkout|stage|merge|branch)\b",
            "ast_compilation_checks": r"\b(ast|compile|py_compile|linter|syntax_error|syntax|compile_error|indentation)\b",
            "database_and_persistence": r"\b(sqlite|chromadb|persist|db|upsert|query_similar|pglite|storage|metadata)\b"
        }

    def classify_sector(self, payload: Dict[str, Any]) -> str:
        """
        Dynamically analyzes a runtime payload (code, logs, error, or api contracts)
        and classifies it into a specialized training sector using semantic regex matching.
        """
        # We search inside inputs, outputs, error logs, or file paths
        search_text = ""
        for key in ("input", "output", "error", "filepath", "description"):
            if key in payload:
                search_text += f" {str(payload[key]).lower()}"

        for sector, pattern in self.sector_rules.items():
            if re.search(pattern, search_text):
                return sector

        # Fallback default sector
        return "general_automation"

    def record_runtime_trace(self, event_type: str, action: str, details: Dict[str, Any]) -> str:
        """
        Records a dynamic runtime event (such as an API transaction or process execution)
        and files it under a dynamically created information sector for specialized training.
        """
        try:
            timestamp = datetime.datetime.now().isoformat()
            
            # Formulate training sample
            instruction = f"Analiza y optimiza la ejecución del proceso/API de SODA en la categoría: {event_type}."
            input_data = (
                f"Acción Ejecutada: {action}\n"
                f"Detalles Técnicos del Suceso:\n{json.dumps(details, ensure_ascii=False, indent=2)}"
            )
            
            # Standardize output for model learning (e.g. self-reflective commentary or expected output state)
            output_data = {
                "suceso_validado": True,
                "diagnostico_soda": f"Ejecución de {action} completada exitosamente dentro del flujo del sistema.",
                "fecha_registro": timestamp
            }

            payload = {
                "instruction": instruction,
                "input": input_data,
                "output": json.dumps(output_data, ensure_ascii=False, indent=2),
                "metadata": {
                    "event_type": event_type,
                    "action": action,
                    "timestamp": timestamp
                }
            }

            # 1. Classify to find specialized sector
            sector = self.classify_sector(payload)
            sector_dir = self.sectors_dir / sector
            sector_dir.mkdir(parents=True, exist_ok=True)
            
            sector_file = sector_dir / "traces.jsonl"
            
            # 2. Append to the specialized sector file
            with open(sector_file, mode="a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")

            logger.info(f"[SODA Beta Observatory] Dynamic trace registered under sector: {sector}")
            return sector

        except Exception as e:
            logger.warning(f"[SODA Beta Observatory] Failed to record dynamic runtime trace: {e}")
            return "failed"
