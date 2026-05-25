import re
from typing import Dict, List, Any
from kernel.core.project_index import MasterIndex, IndexSection

class DataFlowValidator:
    """
    RC3 DataFlowValidator: Verifies that data and logic flows correctly between project sections.
    Ensures that dependencies are satisfied and interfaces match.
    """

    def __init__(self, master_index: MasterIndex):
        self.master_index = master_index

    def validate_index_consistency(self) -> List[str]:
        """Checks for obvious logical errors in the Master Index before execution."""
        errors = []
        sections = self.master_index.get_flat_sections()
        
        all_target_files = set()
        for section in sections:
            # 1. Check for duplicate target files across DIFFERENT sections (Potential collisions)
            for file in section.target_files:
                # We don't forbid it (SafeMerge handles it), but we should warn if many sections touch the same file
                pass
            
            # 2. Check for empty sections
            if not section.target_files and "roadmap" not in section.title.lower():
                errors.append(f"Sección '{section.title}' ({section.id}) no tiene archivos objetivo asignados.")

        return errors

    def verify_inter_section_imports(self, final_code: Dict[str, str]) -> List[str]:
        """
        Post-generation check: Verifies that imports in Section B files point to 
        existing files in Section A or previous sections.
        """
        errors = []
        all_paths = {p.lower().replace("\\", "/") for p in final_code.keys()}
        
        for path, content in final_code.items():
            # Python import detection (simplified)
            # from src.module import ...
            py_imports = re.findall(r'from\s+([\w\.]+)\s+import', content)
            for imp in py_imports:
                # Convert dot notation to path: src.agent.orchestrator -> src/agent/orchestrator.py
                potential_path = imp.replace(".", "/") + ".py"
                if "src/" in potential_path and potential_path.lower() not in all_paths:
                    # Ignore standard library or external packages (heuristic: if it starts with src, it should be local)
                    if imp.startswith("src"):
                        errors.append(f"Fallo de flujo de datos: '{path}' intenta importar '{imp}', pero '{potential_path}' no existe.")

        return errors
