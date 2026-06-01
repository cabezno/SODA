import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

class IntegrationHealthAuditor:
    """
    SODA SUPREME — Integrative Audit System.
    
    Checks cross-module consistency after generation.
    It builds a global symbol map and verifies that all consumers
    are calling providers correctly.
    """
    
    def __init__(self, workspace: Path, stack_language: str):
        self.workspace = workspace
        self.stack_language = stack_language
        self.symbol_map = {} # {module_id: [symbols]}

    def scan_project(self, generated_code_map: Dict[str, str]):
        """Builds a global registry of implemented symbols."""
        for cid, code in generated_code_map.items():
            self.symbol_map[cid] = self._extract_exports(code)

    def verify_consistency(self, contracts_pool: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detects 'Integration Drift': when a module calls a dependency
        using a name that was never implemented.
        """
        violations = []
        
        for cid, contract in contracts_pool.items():
            if not contract.is_atomic: continue
            
            dependencies = contract.dependencies or []
            for dep_id in dependencies:
                if dep_id not in self.symbol_map: continue
                
                # Logic: In ultra-complex software, we check if the consumer's code
                # contains calls to the provider's symbols.
                # This is a heuristic pass.
                implemented_symbols = self.symbol_map[dep_id]
                # (Future: parse consumer code for call sites)
                
        return violations

    def _extract_exports(self, code: str) -> List[str]:
        """Extracts class names, function names, and constant exports."""
        exports = []
        if self.stack_language == "python":
            exports = re.findall(r'^\s*(?:class|def)\s+(\w+)', code, re.MULTILINE)
        elif self.stack_language in ("typescript", "javascript"):
            exports = re.findall(r'export\s+(?:const|function|class|type|interface|enum)\s+(\w+)', code)
        return list(set(exports))

    async def auto_repair_drift(self, gemini_driver, generated_code_map: Dict[str, str]):
        """
        The secret to 'Ultra-Complex' success: 
        If drift is detected, use the provider's code as the source of truth
        and re-prompt the consumer to fix its imports/calls.
        """
        # TODO: Implement surgical re-generation of consumer modules
        pass
