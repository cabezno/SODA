from pathlib import Path
import re

# 1. Revertir phase_mixin.py (Quitar el bypass de skipped)
path_phase = Path('kernel/orchestration/phase_mixin.py')
content_phase = path_phase.read_text(encoding='utf-8')

# Buscamos el bloque if assessment.level.value != "complex": y lo eliminamos
bad_block = """            if assessment.level.value != "complex":
                self._notify(
                    "Arquitecto v2: omitido (reservado para proyectos complex).",
                    "LOG",
                    {"phase": "master_contract"}
                )
                print("  [ARCH-V2] Skipped (not complex).")
                return"""

content_phase = content_phase.replace(bad_block, "")
path_phase.write_text(content_phase, encoding='utf-8')

# 2. Revertir complexity_classifier.py (Quitar el hotfix de landing page)
path_class = Path('kernel/intelligence/complexity_classifier.py')
content_class = path_class.read_text(encoding='utf-8')

bad_hotfix = """        # SODA Hotfix: Force SIMPLE for static/landing pages to prevent v2 Architect overengineering
        text = self._blueprint_text(blueprint).lower()
        if "landing page" in text or "sin backend" in text or "estática" in text:
            level = ComplexityLevel.SIMPLE"""

content_class = content_class.replace(bad_hotfix, "")
path_class.write_text(content_class, encoding='utf-8')

print("Arquitecto V2 restaurado para que actue en TODOS los proyectos.")
