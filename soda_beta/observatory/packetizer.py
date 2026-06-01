from __future__ import annotations

import ast
import json
import logging
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class StructuralPacketizer:
    """
    SODA Beta Structural Packetizer (Capa 1).
    Takes physical source code files, extracts their AST-based signatures,
    and formats them as a SODA Structural Tag enriched with logical outlines
    to prevent decompression hallucinations in 1.5B models.
    """

    def __init__(self, workspace: Optional[Path] = None):
        self.workspace = workspace

    @staticmethod
    def _get_logical_outline(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """
        Walks the interior of a function's AST body and extracts an abstract,
        sequential outline of its logical statements and flow of control.
        """
        steps = []
        for inner in ast.walk(func_node):
            if isinstance(inner, ast.For):
                steps.append("Bucle For")
            elif isinstance(inner, ast.While):
                steps.append("Bucle While")
            elif isinstance(inner, ast.If):
                steps.append("Condicional If")
            elif isinstance(inner, ast.Try):
                steps.append("Estructura Try-Except")
            elif isinstance(inner, ast.With):
                steps.append("Contexto With")
            elif isinstance(inner, ast.Raise):
                steps.append("Eleva Excepción")
            elif isinstance(inner, ast.Return):
                # Try to see if it returns a specific name
                ret_val = ""
                if isinstance(inner.value, ast.Name):
                    ret_val = f" {inner.value.id}"
                steps.append(f"Retorna{ret_val}")
            elif isinstance(inner, ast.Call):
                # Extract called function name
                if isinstance(inner.func, ast.Name):
                    steps.append(f"Llama a {inner.func.id}()")
                elif isinstance(inner.func, ast.Attribute):
                    steps.append(f"Llama a {inner.func.attr}()")

        # Deduplicate sequential matches to keep it compact and readable
        clean_steps = []
        for s in steps:
            if not clean_steps or clean_steps[-1] != s:
                clean_steps.append(s)

        if not clean_steps:
            return "Lógica lineal simple"
        return " -> ".join(clean_steps[:8]) # We limit to 8 steps to prevent context bloat

    def extract_ast_signatures(self, code: str, filepath: str) -> Dict[str, Any]:
        """
        Statically parses Python code to extract classes, function signatures, 
        docstrings, logical outlines, and dependencies.
        """
        signatures = {
            "clases": [],
            "funciones": [],
            "imports": [],
            "has_syntax_error": False,
            "error_msg": ""
        }

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            signatures["has_syntax_error"] = True
            signatures["error_msg"] = str(e)
            return signatures

        for node in ast.walk(tree):
            # Extract imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    signatures["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                signatures["imports"].append(f"{node.module}")

            # Extract Classes
            elif isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append({
                            "nombre": item.name,
                            "args": [arg.arg for arg in item.args.args],
                            "is_async": isinstance(item, ast.AsyncFunctionDef),
                            "docstring": ast.get_docstring(item) or "",
                            "esquema_logico": self._get_logical_outline(item)
                        })
                signatures["clases"].append({
                    "nombre": node.name,
                    "docstring": ast.get_docstring(node) or "",
                    "metodos": methods
                })

            # Extract standalone functions
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Ensure it's not nested inside a class
                parent = getattr(node, "parent", None)
                if not parent or not isinstance(parent, ast.ClassDef):
                    signatures["funciones"].append({
                        "nombre": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                        "docstring": ast.get_docstring(node) or "",
                        "esquema_logico": self._get_logical_outline(node)
                    })

        return signatures

    def generate_structural_tag(self, filepath: str, code: str, gist: str = "") -> Dict[str, Any]:
        """
        Generates a unique, high-fidelity Structural Tag for a file,
        including signatures and internal logical flows for stable reconstruction.
        """
        signatures = self.extract_ast_signatures(code, filepath)
        file_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]

        tag = {
            "tag_id": f"soda-tag-{Path(filepath).stem.lower()}-{file_hash}",
            "archivo": filepath,
            "hash_fuente": file_hash,
            "sinopsis": gist or f"Implementación de lógica para {Path(filepath).name}.",
            "imports": list(set(signatures["imports"])),
            "interfaces": {
                "clases": [
                    {
                        "nombre": c["nombre"],
                        "metodos": [
                            f"{'async ' if m['is_async'] else ''}{m['nombre']}({', '.join(m['args'])}) "
                            f"[Fluido: {m['esquema_logico']}]"
                            for m in c["metodos"]
                        ]
                    } for c in signatures["clases"]
                ],
                "funciones_standalones": [
                    f"{'async ' if f['is_async'] else ''}{f['nombre']}({', '.join(f['args'])}): "
                    f"\"{f['docstring'][:100]}\" [Fluido: {f['esquema_logico']}]"
                    for f in signatures["funciones"]
                ]
            }
        }
        return tag
