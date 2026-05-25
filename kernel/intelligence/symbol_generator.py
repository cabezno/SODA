import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from kernel.drivers.gemini_driver import GeminiDriver
from kernel.storage.correlation_index import CorrelationIndex

class SymbolGenerator:
    """
    Agente encargado de extraer conceptos de negocio y generar el índice alfanumérico inicial.
    """
    def __init__(self, ai_driver: GeminiDriver, workspace: Path):
        self.ai = ai_driver
        self.index = CorrelationIndex(workspace)

    async def generate_from_description(self, description: str) -> List[Dict[str, Any]]:
        """Analiza la descripción y puebla la base de datos de correlación."""
        system_prompt = (
            "Eres el Generador de Símbolos de SODA V3. Tu objetivo es extraer todas las entidades, "
            "variables y acciones necesarias para el proyecto y asignarles un código alfanumérico único.\n\n"
            "FORMATO DE CÓDIGO:\n"
            "- ENT-XXX para Entidades (ej: Usuario, Producto).\n"
            "- VAR-XXX para Variables/Campos (ej: email, precio).\n"
            "- ACT-XXX para Acciones/Funciones (ej: login, crear_pedido).\n\n"
            "SALIDA: Devuelve un JSON con una lista de objetos: "
            '{"symbols": [{"id": "CODE", "concept": "nombre", "type": "Entity|Variable|Action", "data_type": "string|int|..."}]}'
        )
        
        user_msg = f"REQUERIMIENTOS DEL PROYECTO:\n{description}"
        
        try:
            response = await self.ai.prompt(system_prompt, user_msg)
            # Extraer JSON del bloque
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                return []
            
            data = json.loads(json_match.group(0))
            symbols = data.get("symbols", [])
            
            for sym in symbols:
                self.index.register_symbol(
                    code_id=sym["id"],
                    concept=sym["concept"],
                    data_type=sym.get("data_type", "Any"),
                    metadata={"type": sym["type"]}
                )
            return symbols
        except Exception as e:
            print(f"Error generando símbolos: {e}")
            return []

    def get_index_context(self) -> str:
        """Genera una cadena de texto con el índice para inyectar en los prompts de los agentes."""
        symbols = self.index.get_all()
        if not symbols:
            return ""
        
        lines = ["## ÍNDICE DE CORRELACIÓN ALFANUMÉRICA (MANDATORIO)"]
        lines.append("Utiliza estos códigos en IDs de HTML y nombres de variables Backend para asegurar la sincronización.")
        for s in symbols:
            lines.append(f"- [{s['code_id']}] {s['concept']} ({s['data_type']})")
        return "\n".join(lines)
