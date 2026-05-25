import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from kernel.drivers.gemini_driver import GeminiDriver
from kernel.storage.correlation_index import CorrelationIndex

class IntegrationSyncer:
    """
    Agente que realiza la auditoría inversa: analiza el Frontend terminado
    y asegura que todas sus llamadas alfanuméricas existan en el Backend.
    """
    def __init__(self, ai_driver: GeminiDriver, workspace: Path):
        self.ai = ai_driver
        self.workspace = workspace
        self.index = CorrelationIndex(workspace)

    async def sync_check(self, frontend_code_map: Dict[str, str], backend_code_map: Dict[str, str]) -> List[str]:
        """
        Escanea el frontend en busca de códigos [VAR-XXX] o [ACT-XXX] 
        y verifica su presencia en el backend.
        """
        symbols = self.index.get_all()
        if not symbols:
            return []

        findings = []
        fe_content = "\n".join(frontend_code_map.values())
        be_content = "\n".join(backend_code_map.values())

        for sym in symbols:
            code = sym['code_id']
            # ¿Se usa en el Frontend?
            in_fe = code in fe_content
            # ¿Existe en el Backend?
            in_be = code in be_content

            if in_fe and not in_be:
                findings.append(f"MISSING_BACKEND: El código {code} ({sym['concept']}) se usa en la UI pero no está implementado en el Backend.")
                self.index.update_ref(code, status='ERROR_SYNC')
            elif in_fe and in_be:
                self.index.mark_synced(code)

        return findings

    async def generate_sync_patch(self, missing_findings: List[str], backend_files: Dict[str, str]) -> Dict[str, str]:
        """Genera el código faltante en el backend para cumplir con la UI."""
        if not missing_findings:
            return {}

        system_prompt = (
            "Eres el Sincronizador de Integración de SODA V3. Tu tarea es recibir una lista de "
            "funciones o variables que el Frontend está exigiendo pero que el Backend aún no tiene.\n\n"
            "REGLA: Debes escribir el código Backend faltante (Python/Node) respetando los códigos alfanuméricos "
            "proporcionados. Devuelve ÚNICAMENTE los archivos modificados con tags <FILE path='...'>."
        )
        
        user_msg = (
            f"ERRORES DE SINCRONIZACIÓN:\n{chr(10).join(missing_findings)}\n\n"
            f"CÓDIGO BACKEND ACTUAL:\n" + "\n".join([f"### {p}\n{c}" for p, c in backend_files.items()])
        )

        try:
            response = await self.ai.prompt(system_prompt, user_msg)
            from kernel.validators.v2.polyglot_validator import PolyglotValidator
            return PolyglotValidator.extract_files(response)
        except Exception:
            return {}
