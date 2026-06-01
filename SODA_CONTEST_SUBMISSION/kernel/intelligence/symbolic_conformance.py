import ast
import json
import re
from typing import Dict, List, Set, Any
from pathlib import Path

class SymbolicConformityReport:
    def __init__(self, module_id: str):
        self.module_id = module_id
        self.missing_interfaces: List[str] = []
        self.extra_interfaces: List[str] = []
        self.parameter_mismatches: List[Dict[str, Any]] = []
        self.is_conformant: bool = True

    def to_dict(self) -> dict:
        return {
            "module_id": self.module_id,
            "is_conformant": self.is_conformant,
            "missing_interfaces": self.missing_interfaces,
            "extra_interfaces": self.extra_interfaces,
            "parameter_mismatches": self.parameter_mismatches
        }

class SymbolicConformanceVerifier:
    """
    Hard-Link Conformance Verifier.
    Matches the generated code against the MasterContract using AST.
    """

    @staticmethod
    def analyze_python_file(content: str) -> Dict[str, Dict[str, List[str]]]:
        """Extracts function names and their parameters from Python code."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return {}

        found = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [arg.arg for arg in node.args.args if arg.arg != 'self']
                found[node.name] = {
                    "params": params,
                    "is_async": isinstance(node, ast.AsyncFunctionDef)
                }
        return found

    @staticmethod
    def verify_module(module_contract: dict, files: Dict[str, str]) -> SymbolicConformityReport:
        """
        Verifies a single module against its contract.
        module_contract: The 'modulo' entry from MasterContract or blueprint.
        files: Mapping of {path: content} for files belonging to this module.
        """
        report = SymbolicConformityReport(module_contract.get("id", "unknown"))
        
        # 1. Gather all defined interfaces in the module's files
        all_defined = {}
        target_files = module_contract.get("archivos", [])
        
        for path, content in files.items():
            # Match if the file path is explicitly in the module's files list
            # or if the module ID is part of the path (heuristic)
            is_module_file = any(tf in path for tf in target_files) or (report.module_id in path.lower())
            
            if is_module_file and path.endswith(".py"):
                all_defined.update(SymbolicConformanceVerifier.analyze_python_file(content))
        
        # 2. Match against contract
        required_interfaces = module_contract.get("interfaces", [])
        if not isinstance(required_interfaces, list):
             return report # Skip if no interfaces defined

        for iface in required_interfaces:
            name = iface.get("name")
            if not name: continue
            
            if name not in all_defined:
                report.missing_interfaces.append(name)
                report.is_conformant = False
                continue
            
            # Check parameters
            contract_params = [p.get("name") for p in iface.get("params", []) if isinstance(p, dict)]
            code_params = all_defined[name]["params"]
            
            if contract_params != code_params:
                report.parameter_mismatches.append({
                    "interface": name,
                    "expected": contract_params,
                    "found": code_params
                })
                report.is_conformant = False

            # Check async synergy
            if iface.get("is_async") and not all_defined[name]["is_async"]:
                 report.parameter_mismatches.append({
                    "interface": name,
                    "error": "Should be async but is sync"
                })
                 report.is_conformant = False

        return report

    @staticmethod
    def find_modules(blueprint: Any) -> List[dict]:
        """Recursively finds all module definitions in a blueprint."""
        modules = []
        if isinstance(blueprint, list):
            for item in blueprint:
                modules.extend(SymbolicConformanceVerifier.find_modules(item))
        elif isinstance(blueprint, dict):
            if "modulos" in blueprint and isinstance(blueprint["modulos"], list):
                return blueprint["modulos"]
            # Check if this dict looks like a module itself
            if "interfaces" in blueprint and ("id" in blueprint or "archivos" in blueprint):
                return [blueprint]
            # Otherwise search values
            for v in blueprint.values():
                modules.extend(SymbolicConformanceVerifier.find_modules(v))
        return modules
