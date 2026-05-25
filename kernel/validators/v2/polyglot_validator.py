import ast
import re
import json
from pathlib import Path
from typing import Dict, List, Optional

class PolyglotValidator:
    @staticmethod
    def extract_files(raw_output: str, default_filename: str = "main.py") -> Dict[str, str]:
        """
        Extracts multiple files from IA output using <FILE> tags or markdown blocks.
        Returns a mapping of {filepath: content}.
        """
        files = {}

        # 1. TRIPLE-GUARD: Explicit <FILE> tags (Protocolo Multi-Archivo SODA)
        # Formato esperado: <FILE path="models/user.py"> ... </FILE>
        # Se usa (?:</FILE>|$) para soportar respuestas truncadas por limites de tokens
        file_tags = re.finditer(r'<FILE\s+path=["\'](.*?)["\']\s*>(.*?)(?:</FILE>|$)', raw_output, re.DOTALL | re.IGNORECASE)
        for match in file_tags:
            path = match.group(1).strip()
            content = match.group(2).strip()
            # Si el contenido está envuelto en markdown internamente, lo limpiamos
            if content.startswith("```"):
                content = PolyglotValidator.clean_markdown(content)
            files[path] = content

        if files:
            return files

        # 2. FALLBACK: Markdown blocks (Extractor No-Destructivo)        # Buscamos bloques con nombres de archivo en comentarios inmediatamente antes o dentro del bloque
        blocks = re.findall(r'(?:[#\/]{2,}\s*([\w\.\-\/]+)\n)?\s*```[a-zA-Z0-9\+\-]*\s*\n?(.*?)```', raw_output, re.DOTALL | re.IGNORECASE)
        
        for named_path, content in blocks:
            content = content.strip()
            if not content: continue
            
            # Si el bloque tiene un nombre detectado en el comentario superior
            if named_path and ('.' in named_path or '/' in named_path):
                files[named_path.strip()] = content
            else:
                # Si no tiene nombre, intentamos extraerlo de la primera línea del contenido
                first_line = content.splitlines()[0].strip()
                match = re.search(r'[#\/]{2,}\s*([\w\.\-\/]+\.\w+)', first_line)
                if match:
                    files[match.group(1)] = content
                else:
                    # Si es el único bloque o el más largo, usamos el nombre por defecto
                    if default_filename not in files or len(content) > len(files[default_filename]):
                        files[default_filename] = content

        if not files and raw_output.strip():
            # 3. ULTIMO RECURSO: Heurística de texto plano
            files[default_filename] = PolyglotValidator.clean_markdown(raw_output)

        return files

    @staticmethod
    def clean_markdown(source_code: str) -> str:
        """Extracts code robustly, prioritizing <CODE> tags, then markdown, then heuristics."""
        
        # 0. STRONGEST PRIORITY: Explicit XML Tags
        xml_match = re.search(r'<CODE>(.*?)</CODE>', source_code, re.DOTALL | re.IGNORECASE)
        if xml_match:
            return xml_match.group(1).strip()

        # 1. Try to find markdown blocks.
        blocks = re.findall(r'```[a-zA-Z0-9\+\-]*\s*\n?(.*?)```', source_code, re.DOTALL | re.IGNORECASE)
        if blocks:
            # Use the longest block as the primary code candidate
            code = max(blocks, key=len).strip('\r\n')
        else:
            # Fallback A: Truncated markdown block (starts with ``` but doesn't end with it)
            truncated_match = re.search(r'```[a-zA-Z0-9\+\-]*\s*\n?(.*)', source_code, re.DOTALL | re.IGNORECASE)
            if truncated_match and "```" in source_code[:100]:
                code = truncated_match.group(1).strip()
            else:
                # Heuristic extraction
                lines = source_code.splitlines()
                start_idx = 0
                end_idx = len(lines)
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped and not stripped.endswith(':') and not stripped.startswith(('aqui', 'claro', 'este', 'here', 'sure', 'below', 'tengo', 'entendido')):
                        if re.match(r'^(import|from|class|def|const|let|var|function|<|#|//|/\*|@|using|namespace|package)', stripped):
                            start_idx = i
                            break
                for i in range(len(lines) - 1, -1, -1):
                    stripped = lines[i].strip()
                    if stripped and not stripped.startswith(('espero', 'hope', 'let me', 'cualquier', 'si tienes')):
                        if stripped.endswith(('}', ';', '>', ']', '"', "'")) or re.match(r'^[a-zA-Z0-9_)]', stripped[-1:]):
                            end_idx = i + 1
                            break
                code = "\n".join(lines[start_idx:end_idx]).strip('\r\n') if start_idx < end_idx else source_code.strip()

        # POST-PROCESSING: Hard-strip residual markdown fences and explanation text
        cleaned_lines = []
        in_code_block = True
        for line in code.splitlines():
            stripped = line.strip()
            # If we hit a closing fence that was somehow included in the 'code' variable
            if stripped.startswith("```"):
                in_code_block = False
                continue
            if not in_code_block:
                continue # Skip anything after a closing fence
                
            if stripped == "---": continue
            if stripped.startswith("**") and stripped.endswith("**"):
                continue # Skip bold markdown headers
            
            # Remove numbered list markers if they were accidentally prepended
            match_num = re.match(r'^\s*\d+\.\s+(.*)', line)
            cleaned_lines.append(match_num.group(1) if match_num else line)

        final_code = "\n".join(cleaned_lines).strip()
        
        # Extra safety: if the code ends with a dangling fence or markdown-style text, cut it
        final_code = re.sub(r'```.*$', '', final_code, flags=re.DOTALL).strip()
        
        return final_code

    @staticmethod
    def validate_code(source_code: str, language: str):
        """Valida que el codigo compile o al menos sea estructuralmente íntegro."""
        clean_code = source_code # Asumimos que ya viene limpio de extract_files
        lang_lower = language.lower()

        if lang_lower in ["python", "py"]:
            if re.search(r'^\s*(CREATE TABLE|INSERT INTO|SELECT |UPDATE |DELETE |-- )', clean_code, re.IGNORECASE):
                return clean_code
            try:
                ast.parse(clean_code)
            except SyntaxError as e:
                lines = clean_code.splitlines()
                bad_line = lines[e.lineno - 1] if e.lineno and e.lineno <= len(lines) else ""
                raise ValueError(f"AUDITORIA AST FALLIDA: Error de sintaxis en linea {e.lineno}: {e.msg} \nLinea conflictiva: '{bad_line}'")     
        
        elif lang_lower in ["cpp", "c++", "javascript", "js", "typescript", "ts", "go", "rust", "csharp", "cs", "java"]:
            if not clean_code.strip():
                raise ValueError(f"AUDITORIA FALLIDA: El codigo {language} generado esta vacio.")
            stack = []
            for char in clean_code:
                if char == '{': stack.append('{')
                elif char == '}':
                    if not stack: raise ValueError(f"AUDITORIA FALLIDA ({language}): Llave de cierre '}}' encontrada sin apertura previa.")
                    stack.pop()
            if stack: raise ValueError(f"AUDITORIA FALLIDA ({language}): El codigo parece estar truncado o incompleto (faltan {len(stack)} llaves de cierre).")

        return clean_code

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normaliza un nombre para comparación fuzzy (case-insensitive, sin guiones/puntos)."""
        return name.lower().replace("_", "").replace("-", "").replace(".", "").strip()

    @staticmethod
    def validate_linker(files: Dict[str, str], language: str, paradigm: Optional[str] = None):
        """
        IMP-024/029/035: Validador de Enlace AST (Paradigm Isolation).
        Verifica enlaces globales y prohíbe librerías fuera del paradigma del proyecto.
        """
        all_paths = {p.lower(): p for p in files.keys()}
        normalized_map = {PolyglotValidator._normalize_name(Path(p).stem): p for p in files.keys()}
        
        errors = []
        
        # IMP-035: Definición de librerías prohibidas por paradigma
        BANNED_BY_PARADIGM = {
            "cli": {"flask", "django", "fastapi", "uvicorn", "http", "webbrowser", "selenium", "dash", "streamlit"},
            "library": {"flask", "django", "fastapi", "uvicorn", "http", "tkinter", "pyqt5", "pyside2"},
            "api": {"tkinter", "pyqt5", "pyside2", "pygame", "arcade"}
        }
        
        banned_set = BANNED_BY_PARADIGM.get(paradigm.lower(), set()) if paradigm else set()
        
        for path, content in files.items():
            if not path.endswith('.py'): continue
            
            imports = re.findall(r'import\s+([\w\.]+)', content)
            from_imports = re.findall(r'from\s+([\w\.]+)\s+import', content)
            
            whitelist = {
                "os", "sys", "json", "re", "asyncio", "datetime", "abc", "typing", 
                "pathlib", "shutil", "time", "math", "random", "logging", "collections",
                "fastapi", "pydantic", "sqlalchemy", "flask", "flask_cors", "requests", 
                "httpx", "uvicorn", "setuptools", "pytest", "unittest", "argparse",
                "tempfile", "io", "mimetypes", "glob", "fnmatch", "base64", "hashlib",
                "hmac", "uuid", "sqlite3", "threading", "string", "urllib", "http", "webbrowser"
            }
            
            for imp in set(imports + from_imports):
                base_imp = imp.split('.')[0]
                imp_lower = base_imp.lower()
                
                # IMP-035: Bloqueo de paradigma
                if imp_lower in banned_set:
                    errors.append(f"Paradigm Violation (IMP-035): '{path}' intenta importar '{base_imp}', prohibido en proyectos '{paradigm}'.")
                    continue

                if imp_lower in whitelist: continue
                
                # Busqueda exacta
                potential_files = [f"{imp_lower}.py", f"src/{imp_lower}.py", f"core/{imp_lower}.py", f"lib/{imp_lower}.py"]
                if any(pf in all_paths for pf in potential_files): continue
                
                # Búsqueda FUZZY
                norm_imp = PolyglotValidator._normalize_name(base_imp)
                if norm_imp in normalized_map: continue

                errors.append(f"Linker Error: '{path}' intenta usar el módulo '{imp}', pero no se encuentra su implementación física.")
        
        if errors:
            raise ValueError("FALLO DE ENLACE ARQUITECTÓNICO (Paradigm/Fuzzy Failure):\n" + "\n".join(errors))

    @staticmethod
    def validate_imports(files: Dict[str, str], language: str):
        """
        Verifica la integridad de las importaciones locales dentro de un set de archivos.
        """
        errors = []
        all_paths = {p.lower() for p in files.keys()}
        
        for path, content in files.items():
            # Buscar imports locales (ej: import { X } from './utils')
            if language.lower() in ["typescript", "ts", "js", "javascript"]:
                matches = re.findall(r'from\s+[\'"]\.\/([\w\.\-\/]+)[\'"]', content)
                for m in matches:
                    potential_files = [m.lower(), f"{m.lower()}.ts", f"{m.lower()}.tsx", f"{m.lower()}.js"]
                    if not any(pf in all_paths for pf in potential_files):
                        errors.append(f"Archivo '{path}' intenta importar de './{m}', pero ese archivo no existe en el set generado.")
            
            elif language.lower() in ["python", "py"]:
                matches = re.findall(r'from\s+(\w+)\s+import', content)
                # También buscar imports directos (ej: import pathlib)
                matches += re.findall(r'^import\s+(\w+)', content, re.MULTILINE)
                
                for m in matches:
                    if f"{m.lower()}.py" not in all_paths and m.lower() != "database":
                        # Ignorar librerías estándar y comunes (Whitelist expandida)
                        # Whitelist masiva de librerías estándar y comunes de Python
                        standard_libs = [
                            "os", "sys", "json", "re", "asyncio", "datetime", "abc", "typing", 
                            "pathlib", "shutil", "time", "math", "random", "logging", "collections",
                            "fastapi", "pydantic", "sqlalchemy", "flask", "flask_cors", "requests", 
                            "httpx", "uvicorn", "setuptools", "pytest", "unittest", "argparse",
                            "tempfile", "io", "mimetypes", "glob", "fnmatch", "base64", "hashlib",
                            "hmac", "uuid", "sqlite3", "threading", "multiprocessing", "subprocess",
                            "socket", "select", "struct", "pickle", "copy", "itertools", "functools",
                            "operator", "inspect", "contextlib", "threading", "queue", "bisect",
                            "heapq", "array", "weakref", "types", "errno", "signal", "stat"
                        ]
                        if m.lower() not in standard_libs:
                            errors.append(f"Archivo '{path}' intenta importar el módulo local '{m}', pero no existe '{m}.py' en el set.")
                            
        if errors:
            raise ValueError("FALLO DE INTEGRIDAD DE IMPORTACIONES:\n" + "\n".join(errors))
