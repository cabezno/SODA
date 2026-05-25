import re
import json
from typing import Tuple, List

class PreFlightSemanticAligner:
    """
    IMP-023: Semantic Alignment Gate (Hardened).
    Evita la alucinación arquitectónica deteniendo el pipeline (Hard-Stop)
    si el plan de desarrollo contradice el paradigma de la especificación original.
    """

    # Paradigmas mutuamente excluyentes y sus palabras prohibidas
    PARADIGM_EXCLUSIONS = {
        "cli": {
            "banned_keywords": ["html", "css", "bootstrap", "tailwind", "flask", "django", "fastapi", "express", "react", "vue", "frontend", "browser"],
            "error_message": "Contradicción detectada: El proyecto es una herramienta CLI (Línea de comandos), pero el plan técnico sugiere componentes Web/Frontend."
        },
        "library": {
            "banned_keywords": ["server", "app.listen", "express", "html", "css", "react", "dashboard"],
            "error_message": "Contradicción detectada: El proyecto es una librería/SDK, pero el plan intenta exponer servidores o interfaces de usuario."
        },
        "api": {
            "banned_keywords": ["react", "vue", "frontend", "gui", "desktop", "qt"],
            "error_message": "Contradicción detectada: El proyecto es una API (Backend), pero el plan incluye interfaces de usuario complejas."
        }
    }

    @classmethod
    def verify_alignment(cls, spec_text: str, plan_text: str) -> Tuple[bool, str]:
        """
        Analiza la especificación y el plan para encontrar discrepancias de paradigma.
        Returns: (is_aligned: bool, reason: str)
        """
        spec_lower = spec_text.lower()
        plan_lower = plan_text.lower()

        # 1. Detectar paradigma dominante en la especificación
        detected_paradigm = None
        if any(k in spec_lower for k in ("cli", "command line", "consola", "terminal", "herramienta de linea")):
            detected_paradigm = "cli"
        elif any(k in spec_lower for k in ("library", "sdk", "libreria", "modulo exportable")):
            detected_paradigm = "library"
        elif any(k in spec_lower for k in ("api", "backend", "endpoint", "rest", "servidor")):
            detected_paradigm = "api"

        if not detected_paradigm:
            return True, "Paradigma de especificación flexible. Procediendo."

        # 2. Validar contra lista negra de exclusiones
        exclusion = cls.PARADIGM_EXCLUSIONS.get(detected_paradigm)
        if not exclusion:
            return True, "Sin restricciones para el paradigma detectado."

        found_violations = []
        for kw in exclusion["banned_keywords"]:
            # Búsqueda por palabra completa con límites \b
            if re.search(rf"\b{re.escape(kw)}\b", plan_lower):
                found_violations.append(kw)

        if found_violations:
            msg = f"{exclusion['error_message']} Palabras conflictivas en el plan: {found_violations}"
            return False, msg

        return True, "Alineación semántica Pre-Flight verificada con éxito."
