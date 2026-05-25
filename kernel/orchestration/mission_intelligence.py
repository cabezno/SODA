from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, List

class MissionCriticality(Enum):
    LOW = 1       # Scripts, simple tools
    MEDIUM = 2    # Web apps, standard APIs
    HIGH = 3      # Systems, Financial, Security-sensitive
    KERNEL = 4    # OS-grade, critical infrastructure

@dataclass
class MissionProfile:
    complexity_score: int  # 1-10
    criticality: MissionCriticality
    domain: str            # web, systems, data, automation
    suggested_lineup: Dict[str, str]
    max_tokens: int
    temperature: float
    required_auditors: List[str]
    use_council: bool = False

class MissionIntelligence:
    """Decide dinámicamente la configuración del motor basándose en el requerimiento."""
    
    @staticmethod
    def analyze_requirement(description: str) -> MissionProfile:
        import re
        desc = description.lower()
        
        # Heurísticas de complejidad usando RegEx con límites de palabra
        is_kernel = bool(re.search(r'\b(kernel|os|sistema operativo|driver|bancario|crypto|blockchain|firmware|misión crítica|critical|consensus|council)\b', desc))
        is_low = bool(re.search(r'\b(script|automatización|simple|pequeño|utilidad|renombrar|borrar)\b', desc))
        
        if is_kernel:
            score = 10
            criticality = MissionCriticality.KERNEL
            domain = "systems"
            lineup = {"architect": "gemini-2.5-pro", "developer": "gemini-2.5-pro", "auditor": "deepseek", "polisher": "gemini-2.5-pro"}
            tokens = 8192
            temp = 0.0
            auditors = ["security", "memory", "logic"]
            use_council = True
        elif is_low:
            score = 2
            criticality = MissionCriticality.LOW
            domain = "automation"
            lineup = {"architect": "gemini-2.5-flash", "developer": "gemini-2.5-flash", "auditor": "gemini-2.5-flash", "polisher": "gemini-2.5-flash"}
            tokens = 2048
            temp = 0.5
            auditors = ["syntax"]
            use_council = False
        else:
            score = 5
            criticality = MissionCriticality.MEDIUM
            domain = "web"
            lineup = {"architect": "gemini-2.5-pro", "developer": "gemini-2.5-flash", "auditor": "deepseek", "polisher": "gemini-2.5-pro"}
            tokens = 4096
            temp = 0.2
            auditors = ["logic", "ux"]
            use_council = score > 7 or "consejo" in desc or "council" in desc

            
        return MissionProfile(
            complexity_score=score,
            criticality=criticality,
            domain=domain,
            suggested_lineup=lineup,
            max_tokens=tokens,
            temperature=temp,
            required_auditors=auditors,
            use_council=use_council
        )
