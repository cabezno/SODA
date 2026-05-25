import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ModelLineup:
    name: str
    layer0_wisdom: str
    layer2_architect: str
    layer3_techlead: str
    layer4_coder: str # Mejora: Coder independiente del QA
    layer5_qa: str
    temperature: float = 0.2
    max_tokens: int = 8192
    parallel_agents: int = 2

class FinopsRouter:
    """
    Gestiona el enrutamiento dinámico de modelos de IA y su escalado (Fallback)
    en caso de errores iterativos.
    """
    
    # Jerarquía estricta de escalado por capacidades de CODIFICACIÓN
    ESCALATION_PATH = {
        "qwen2.5-coder:7b": "gemini-3-flash-preview",   # local → cloud si Qwen falla
        "qwen2.5-coder:14b": "gemini-3-flash-preview",
        "gemini-2.5-flash": "gemini-2.5-pro",
        "gemini-2.5-pro": "gemini-3-flash-preview",
        "gemini-3-flash-preview": "gemini-3.1-pro-preview",
        "gemini-3.1-pro-preview": "deepseek-chat",
        "deepseek-chat": "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-20241022": "claude-3-5-sonnet-20241022"
    }

    # Escaleras de Continuidad por Capa (Jerarquía de Fallback entre Proveedores)
    LADDERS = {
        "CRITICAL": [
            "deepseek-chat",
            "gemini-3.1-pro-preview",
            "claude-3-5-sonnet-20241022",
            "gemini-3-flash-preview"
        ],
        "FAST": [
            "gemini-3-flash-preview",
            "gemini-2.5-flash",
            "deepseek-chat"
        ],
        "CODER": [
            "qwen2.5-coder:7b",          # Qwen local primero (gratuito)
            "deepseek-chat",
            "gemini-3.1-pro-preview",
            "claude-3-5-sonnet-20241022"
        ]
    }

    # Alineaciones predefinidas
    LINEUPS = {
        # economy: mínimo costo. Qwen local, 1 agente paralelo, tokens reducidos.
        "economy": ModelLineup(
            name="economy",
            layer0_wisdom="gemini-3-flash-preview",
            layer2_architect="gemini-3-flash-preview",
            layer3_techlead="gemini-3-flash-preview",
            layer4_coder="qwen2.5-coder:7b",
            layer5_qa="gemini-3-flash-preview",
            temperature=0.1,
            max_tokens=4096,
            parallel_agents=1
        ),
        # auto: default inteligente. Qwen para código, Flash para orquestación. 2 agentes.
        "auto": ModelLineup(
            name="auto",
            layer0_wisdom="gemini-3-flash-preview",
            layer2_architect="gemini-3-flash-preview",
            layer3_techlead="gemini-3-flash-preview",
            layer4_coder="qwen2.5-coder:7b",
            layer5_qa="gemini-3-flash-preview",
            temperature=0.2,
            max_tokens=8192,
            parallel_agents=2
        ),
        # balanced: calidad media-alta. Qwen 14b local en lugar de 7b — mejor razonamiento,
        # sin costo de API. El salto a modelos cloud ocurre en premium.
        "balanced": ModelLineup(
            name="balanced",
            layer0_wisdom="gemini-3-flash-preview",
            layer2_architect="gemini-3-flash-preview",
            layer3_techlead="gemini-3-flash-preview",
            layer4_coder="qwen2.5-coder:14b",
            layer5_qa="gemini-3-flash-preview",
            temperature=0.2,
            max_tokens=8192,
            parallel_agents=2
        ),
        "premium": ModelLineup(
            name="premium",
            layer0_wisdom="gemini-3-flash-preview",
            layer2_architect="gemini-3.1-pro-preview",
            layer3_techlead="gemini-3-flash-preview",
            layer4_coder="gemini-3.1-pro-preview",
            layer5_qa="gemini-3.1-pro-preview",
            temperature=0.3,
            max_tokens=32768,
            parallel_agents=3
        ),
        "ultra": ModelLineup(
            name="ultra",
            layer0_wisdom="gemini-3-flash-preview",
            layer2_architect="deepseek-chat", # DeepSeek diseña el árbol
            layer3_techlead="deepseek-chat",  # DeepSeek prepara los tipos técnicos
            layer4_coder="deepseek-chat",     # DeepSeek programa
            layer5_qa="claude-3-5-sonnet-20241022", # Claude solo actúa como el Juez Final
            temperature=0.0,
            max_tokens=8192,
            parallel_agents=4
        )
    }

    @classmethod
    def escalate_model(cls, current_model: str) -> str:
        """Devuelve el siguiente modelo más capaz en la jerarquía tras 3 fallos."""
        return cls.ESCALATION_PATH.get(current_model, "gemini-3.1-pro-preview")

    @classmethod
    def get_lineup(cls, profile_name: str) -> ModelLineup:
        """Obtiene la alineación de modelos base según el perfil."""
        return cls.LINEUPS.get(profile_name.lower(), cls.LINEUPS["balanced"])

    @staticmethod
    def log_phase_error(workspace: Path, phase: str, contract_id: str, error_msg: str, attempt: int, model_used: str):
        """Guarda logs detallados de errores entre fases en el directorio del proyecto."""
        try:
            if not workspace:
                return
            log_dir = Path(workspace) / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "phase_errors.log"
            
            log_entry = {
                "phase": phase,
                "contract_id": contract_id,
                "attempt": attempt,
                "model_used": model_used,
                "error": error_msg
            }
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"Error escribiendo log de fase: {e}")
