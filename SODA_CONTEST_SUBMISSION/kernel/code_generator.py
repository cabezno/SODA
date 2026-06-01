import asyncio
import json
import re
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

from kernel.context.context_builder import ContextBuilder
from kernel.docker_sandbox import DockerSandbox
from kernel.goals.goal_tree import build_file_goal_id, build_file_goal_node
from kernel.goals.metadata_injector import MetadataInjector
from kernel.integrity.goal_integrity_validator import GoalIntegrityValidator
from kernel.execution.html_template_injector import get_html_hint
from kernel.execution.log_collector import LogCollector


@dataclass
class GeneratedFile:
    filepath: str
    content: str
    goal_id: str
    validated: bool
    attempts: int


SYNTAX_CHECK = (
    "import py_compile, sys\n"
    "try:\n"
    "    py_compile.compile('target.py', doraise=True)\n"
    "    print('SYNTAX_OK')\n"
    "except py_compile.PyCompileError as e:\n"
    "    print(f'SYNTAX_ERROR: {e}')\n"
    "    sys.exit(1)\n"
)

PYTHON_EXTENSIONS = {".py"}
NON_PYTHON_EXTENSIONS = {
    # Web
    ".html", ".css", ".scss", ".sass", ".less",
    ".js", ".jsx", ".ts", ".tsx", ".vue",
    # JVM
    ".java", ".kt", ".kts", ".gradle",
    # .NET
    ".cs", ".vb", ".fs", ".csproj", ".sln",
    # Go
    ".go",
    # PHP
    ".php",
    # Ruby
    ".rb", ".erb",
    # Rust
    ".rs",
    # Swift / ObjC
    ".swift", ".m", ".h",
    # C / C++
    ".c", ".cpp", ".cc", ".cxx", ".hpp",
    # Data / Config
    ".json", ".yaml", ".yml", ".toml", ".xml",
    ".env", ".ini", ".cfg", ".conf",
    # Docs / Shell
    ".md", ".txt", ".sh", ".bat", ".ps1",
    # Build / Container
    "",  # Dockerfile has no extension
}


def _noop(*a, **kw):
    pass


class CodeGenerator:
    MAX_LOCAL_RETRIES = 3
    # 9-level escalation ladder:
    # L1-L3: Qwen × 3  →  L4-L6: Gemini × 3  →  L7-L9: Claude × 3
    ESCALATION_LEVELS = [
        "qwen",   "qwen",   "qwen",
        "gemini", "gemini", "gemini",
        "claude", "claude", "claude",
    ]

    def __init__(self, ollama_driver, claude_driver, gemini_driver=None):
        self.ollama = ollama_driver
        self.claude = claude_driver
        self.gemini = gemini_driver
        self.builder = ContextBuilder()
        self.sandbox = DockerSandbox()
        self.metadata_injector = MetadataInjector()
        self.validator = GoalIntegrityValidator()
        self.notify: Callable = _noop  # set by orchestrator after init
        self._notify_fn: Callable = _noop  # alias used internally — same ref as notify
        # Learning system — set by orchestrator after init
        self.observer = None   # BehaviorObserver | None
        self.coach = None      # LocalAICoach | None
        self.tracker = None    # PerformanceTracker | None — set by orchestrator after init
        self._log_collector = LogCollector(max_bytes_per_tool=2_000, max_age_minutes=30)
        
        # Load heuristics from external config
        self._heuristics = self._load_heuristics()
        
        # C: Dynamic Model Router — pre-classify files before calling any AI
        from kernel.intelligence.file_complexity_router import FileComplexityRouter
        self._router = FileComplexityRouter()
        # Template injection: paths relative to source_dir that were copied from a template.
        # generate_file skips generation for these — template content wins.
        self.injected_files: set[str] = set()

        # SODA Beta & SODA FUSION Cache: In-session cache for AST extracted interfaces
        self._ast_interface_cache: dict[str, str] = {}

    def _load_heuristics(self) -> dict:
        config_path = Path(__file__).resolve().parent / "config" / "heuristics.json"
        if config_path.exists():
            try:
                return json.loads(config_path.read_text(encoding="utf-8"))
            except Exception as e:
                if self.notify: self.notify(f"Error cargando heuristics.json: {e}", "WARNING")
        return {}

    def _get_cached_python_interface(self, code: str) -> str:
        h = hashlib.sha256(code.encode("utf-8")).hexdigest()
        if h not in self._ast_interface_cache:
            self._ast_interface_cache[h] = self._extract_python_interface(code)
        return self._ast_interface_cache[h]

    def _get_cached_js_ts_interface(self, code: str, filepath: str) -> str:
        h = hashlib.sha256(f"{filepath}:{code}".encode("utf-8")).hexdigest()
        if h not in self._ast_interface_cache:
            self._ast_interface_cache[h] = self._extract_js_ts_interface(code, filepath)
        return self._ast_interface_cache[h]

    @staticmethod
    def _extract_python_interface(code: str) -> str:
        """Extrae la estructura pública (clases y firmas) usando AST de forma recursiva."""
        import ast
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        doc = ast.get_docstring(node)
                        node.body = [ast.Expr(value=ast.Constant(value=doc))] if doc else [ast.Pass()]
                    elif isinstance(node, ast.ClassDef):
                        # Limpiar métodos internos pero mantener la firma de la clase
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                d = ast.get_docstring(item)
                                item.body = [ast.Expr(value=ast.Constant(value=d))] if d else [ast.Pass()]
            return ast.unparse(tree)
        except Exception:
            return code[:1000] + "\n# ... (AST parse failed)"

    def _extract_js_ts_interface(self, code: str, filepath: str) -> str:
        """Extrae la estructura pública (clases, interfaces, funciones) usando Tree-sitter AST."""
        try:
            import tree_sitter_javascript as tsjs
            import tree_sitter_typescript as tsts
            from tree_sitter import Language, Parser
            
            ext = Path(filepath).suffix.lower()
            if ext in {".ts", ".tsx"}:
                LANG = Language(tsts.language())
            else:
                LANG = Language(tsjs.language())
            
            parser = Parser(LANG)
            tree = parser.parse(bytes(code, "utf8"))
            
            # Query for exported or top-level declarations
            # This is a simplified query; real AST traversal is better but this is a good start
            query_scm = """
                (export_statement) @decl
                (class_declaration) @decl
                (function_declaration) @decl
                (interface_declaration) @decl
                (type_alias_declaration) @decl
            """
            query = LANG.query(query_scm)
            captures = query.captures(tree.root_node)
            
            extracted = []
            for node, name in captures:
                # Get the first line of the node (signature)
                line = code.splitlines()[node.start_point[0]]
                extracted.append(line.strip())
            
            if extracted:
                return "\n".join(extracted)
        except Exception:
            pass

        # Fallback to Regex Heuristics
        lines = []
        patterns = self._heuristics.get("js_ts_heuristics", {}).get("public_interface_patterns", [
            r"export\s+(class|interface|type|const|function|async\s+function)\s+\w+",
            r"class\s+\w+",
            r"interface\s+\w+",
            r"function\s+\w+\s*\(.*?\)"
        ])
        for line in code.splitlines():
            if any(re.search(p, line) for p in patterns):
                lines.append(line.strip())
        return "\n".join(lines) if lines else code[:800]

    async def _analyze_error_and_decide(self, filepath: str, last_error: str, attempt_num: int) -> str:
        """Analiza heurísticamente el error y decide si requiere escalado inmediato."""
        err = last_error.lower()
        if any(x in err for x in ("syntaxerror", "indentationerror", "import_error", "modulenotfounderror")):
            return "escalate"
        return "retry"

    def verify_relay_to_disk_integrity(self, source_dir: Path, relay_note: str) -> tuple[bool, list[str]]:
        """
        [IMP-021] Analiza las notas de relevo en busca de rutas de archivos mencionadas,
        asegura que existan físicamente en el disco, no estén vacías y sean sintácticamente válidas.
        """
        if not relay_note:
            return True, []

        # Regex corregida por Gemini 3.5: detecta tanto 'archivo.py' como 'carpeta/sub/archivo.py'
        file_pattern = r'\b([\w\-]+(?:/[\w\-\.]+)*\.[\w]+)\b'
        mentioned_files = set(re.findall(file_pattern, relay_note))

        missing_or_corrupt = []
        critical_exts = {".py", ".js", ".ts", ".html", ".css", ".json", ".sql", ".sh"}

        for file_rel_path in mentioned_files:
            suffix = Path(file_rel_path).suffix.lower()
            if suffix not in critical_exts:
                continue

            full_path = source_dir / file_rel_path

            # 1. Validación de Existencia y Tamaño Mínimo
            if not full_path.exists():
                missing_or_corrupt.append(f"{file_rel_path} (No encontrado en disco)")
                continue

            if full_path.stat().st_size < 10:
                missing_or_corrupt.append(f"{file_rel_path} (Archivo vacío o truncado)")
                continue

            # 2. Validación de Sintaxis AST para Python (Sugerencia Gemini 3.5)
            if suffix == ".py":
                try:
                    code_content = full_path.read_text(encoding="utf-8", errors="replace")
                    import ast
                    ast.parse(code_content)
                except SyntaxError as se:
                    missing_or_corrupt.append(f"{file_rel_path} (Error de Sintaxis AST: {se.msg} en línea {se.lineno})")   
                except Exception as e:
                    missing_or_corrupt.append(f"{file_rel_path} (Fallo de lectura: {str(e)})")

        if missing_or_corrupt:
            return False, missing_or_corrupt
        return True, []

    def _get_compressed_context(self, code: str, filepath: str) -> str:
        ext = Path(filepath).suffix.lower()
        if ext in PYTHON_EXTENSIONS:
            return self._get_cached_python_interface(code)
        if ext in {".js", ".jsx", ".ts", ".tsx"}:
            return self._get_cached_js_ts_interface(code, filepath)
        return code[:800]

    @staticmethod
    def _build_escalation_context(failed_code: str, error_reason: str) -> str:
        """Build XML-structured escalation context for cloud model debugging (PASO 5)."""
        parts: list[str] = []
        if failed_code:
            parts.append(f"<intento_previo_fallido>\n{failed_code[:3000]}\n</intento_previo_fallido>")
        if error_reason:
            parts.append(f"<error_del_compilador>\n{error_reason}\n</error_del_compilador>")
        if parts:
            parts.append(
                "INSTRUCCIÓN: El modelo anterior intentó esta solución pero falló con este error. "
                "Corrige el código y genera la versión final correcta."
            )
        return "\n".join(parts)

    def _build_task(
        self, filepath: str, module: dict, blueprint: dict, architecture: dict,
        user_requirements: str = "",
        dependency_context: Optional[dict] = None,
        design_context: Optional[str] = None,
        source_dir: Optional[Path] = None,
        qwen_attempt: int = 1,
        runtime_errors: str = "",
        mode: str = "full",
        skeleton_code: str = "",
        master_contract: Optional[dict] = None,
        gbrain_context: Optional[str] = None,
    ) -> str:
        stack = blueprint.get("stack_sugerido", {})

        # PASO 1: use v2 ID if available, fall back to legacy nombre
        module_id = module.get("id") or module.get("nombre", "")

        # Typed contract info from master_contract.json (preferred over prose contracts)
        typed_interfaces, typed_data_types = self._extract_typed_contract(
            module_id=module_id,
            master_contract=master_contract,
        )

        # Legacy prose contracts as fallback (only used when master_contract unavailable)
        contracts = architecture.get("contratos", [])
        relevant_prose = [
            c for c in contracts
            if module_id in (c.get("modulo_origen", ""), c.get("modulo_destino", ""))
        ] if not typed_interfaces else []

        is_qwen_retry = qwen_attempt > 1

        # PASO 1: clean task dict — no goal_id/goal_hash, use modulo_id
        task: dict = {
            "archivo_a_generar": filepath,
            "modulo_id": module_id,
            "responsabilidad": module.get("responsabilidad", ""),
            "stack": stack,
        }

        if gbrain_context:
            task["pautas_adicionales_gbrain"] = gbrain_context

        endpoints = module.get("endpoints", [])
        if endpoints:
            task["endpoints"] = endpoints

        if mode == "skeleton":
            task["INSTRUCCION_ESPECIAL"] = "GENERA SOLO EL ESQUELETO DEL CODIGO (imports, firmas de funciones con pass, y tipos). NO ESCRIBAS LOGICA INTERNA."
            task["dependencias_del_modulo"] = module.get("dependencias", [])
            if typed_interfaces:
                task["interfaz_a_implementar"] = typed_interfaces
            else:
                task["contratos_relevantes"] = relevant_prose
            return json.dumps(task, ensure_ascii=False, indent=2)

        if mode == "logic":
            task["INSTRUCCION_ESPECIAL"] = "Rellena la logica interna del siguiente esqueleto de codigo. No alteres las firmas ni los nombres de clases/funciones."
            task["ESQUELETO_BASE"] = skeleton_code

        if mode in ("full", "logic") and not is_qwen_retry:
            task["dependencias_del_modulo"] = module.get("dependencias", [])
            if typed_interfaces:
                task["interfaz_a_implementar"] = typed_interfaces
                if typed_data_types:
                    task["tipos_de_datos"] = typed_data_types
                task["INSTRUCCION"] = "Implementa la interfaz_a_implementar utilizando los tipos_de_datos."
            else:
                task["contratos_relevantes"] = relevant_prose

        if "_copilot_feedback" in module:
            task["copilot_feedback"] = module["_copilot_feedback"]
        if user_requirements:
            task["requisitos_usuario"] = user_requirements

        html_hint = get_html_hint(filepath, blueprint, architecture)
        if html_hint and not is_qwen_retry:
            task["plantilla_ui"] = html_hint.strip()

        if dependency_context and mode in ("full", "logic"):
            # PASO 2: prefer typed interfaces from master_contract over truncated raw code
            dep_interfaces_map: dict = {}
            dep_code: dict = {}
            for dep_id in module.get("dependencias", []):
                dep_typed, _ = self._extract_typed_contract(dep_id, master_contract)
                if dep_typed:
                    dep_interfaces_map[dep_id] = dep_typed
                elif dep_id in dependency_context:
                    files = dependency_context[dep_id]
                    processed_files = {}
                    for fp, content in list(files.items())[:5]:
                        if fp.endswith('.py'):
                            processed_files[fp] = self._get_cached_python_interface(content)
                        else:
                            limit = 800 if is_qwen_retry else 1500
                            processed_files[fp] = content[:limit] + "\n# ... (truncado)" if len(content) > limit else content
                    if processed_files:
                        dep_code[dep_id] = processed_files
            if dep_interfaces_map:
                task["interfaces_de_dependencias"] = dep_interfaces_map
            if dep_code:
                task["codigo_generado_dependencias"] = dep_code

        if runtime_errors:
            task["errores_runtime_nivel_anterior"] = runtime_errors[:1200]

        # PASO 1: parse design_context as native dict when possible
        if design_context and not is_qwen_retry:
            if isinstance(design_context, dict):
                task["especificacion_diseno"] = design_context
            else:
                try:
                    task["especificacion_diseno"] = json.loads(design_context)
                except (json.JSONDecodeError, TypeError):
                    task["especificacion_diseno"] = design_context

        return json.dumps(task, ensure_ascii=False, indent=2)

    @staticmethod
    def _format_task_for_qwen(task_json: str) -> str:
        """Convierte el JSON de tarea a un prompt natural, legible y compacto para Qwen 7B.

        Qwen 7B no razona bien sobre JSON anidado complejo. Este formateador extrae
        solo los campos que el modelo necesita y los presenta como texto directo.
        """
        try:
            t = json.loads(task_json)
        except Exception:
            return task_json  # fallback: usar el JSON crudo

        lines: list[str] = []

        # ── Directiva principal ───────────────────────────────────────────────
        archivo = t.get("archivo_a_generar", "?")
        lines.append(f"GENERA EL ARCHIVO: {archivo}")
        lines.append("")

        # Instrucción especial (skeleton, logic fill, etc.)
        if t.get("INSTRUCCION_ESPECIAL"):
            lines.append(f"INSTRUCCIÓN: {t['INSTRUCCION_ESPECIAL']}")
            lines.append("")

        # ── Contexto del módulo ───────────────────────────────────────────────
        lines.append(f"Módulo: {t.get('modulo_id', t.get('modulo', ''))}")
        lines.append(f"Responsabilidad: {t.get('responsabilidad', '')}")

        stack = t.get("stack", {})
        if stack:
            parts = [f"{k}={v}" for k, v in stack.items() if v]
            if parts:
                lines.append(f"Stack: {', '.join(parts)}")
        lines.append("")

        # ── Endpoints (si los hay) ────────────────────────────────────────────
        endpoints = t.get("endpoints", [])
        if endpoints:
            lines.append("Endpoints que debe exponer este módulo:")
            for ep in endpoints[:12]:
                method = ep.get("method", "")
                path = ep.get("path", ep.get("ruta", ""))
                desc = ep.get("descripcion", ep.get("description", ""))
                lines.append(f"  {method} {path}  — {desc}")
            lines.append("")

        # ── Interfaz a implementar (PASO 1: typed contract) ──────────────────
        interfaz = t.get("interfaz_a_implementar", [])
        if interfaz:
            lines.append("Interfaz que DEBES implementar (firmas exactas):")
            for iface in interfaz[:8]:
                name = iface.get("name", "")
                params = iface.get("parameters", {})
                returns = iface.get("returns", "")
                lines.append(f"  {name}({', '.join(f'{k}: {v}' for k, v in params.items())}) -> {returns}")
            lines.append("")

        tipos = t.get("tipos_de_datos", [])
        if tipos:
            lines.append("Tipos de datos disponibles:")
            for td in tipos[:6]:
                name = td.get("name", "")
                fields = td.get("fields", {})
                lines.append(f"  {name}: {{{', '.join(f'{k}: {v}' for k, v in fields.items())}}}")
            lines.append("")

        # ── Requerimientos del usuario ────────────────────────────────────────
        if t.get("requisitos_usuario"):
            lines.append("Requerimientos del usuario:")
            lines.append(t["requisitos_usuario"][:600])
            lines.append("")

        # ── Interfaces tipadas de dependencias (PASO 2: master_contract) ────────
        dep_interfaces = t.get("interfaces_de_dependencias", {})
        if dep_interfaces:
            lines.append("Interfaces tipadas de módulos dependientes (implementá sobre estas firmas exactas):")
            for mod_name, ifaces in dep_interfaces.items():
                lines.append(f"  # {mod_name}")
                for iface in ifaces[:6]:
                    name = iface.get("name", "")
                    params = iface.get("parameters", {})
                    returns = iface.get("returns", "")
                    lines.append(f"    {name}({', '.join(f'{k}: {v}' for k,v in params.items())}) -> {returns}")
                lines.append("")

        # ── Código de dependencias (fallback: raw code) ───────────────────────
        dep_code = t.get("codigo_generado_dependencias", {})
        if dep_code:
            lines.append("Código de módulos dependientes (usá estos imports y tipos exactos):")
            for mod_name, files in dep_code.items():
                lines.append(f"  # {mod_name}")
                for fp, content in files.items():
                    lines.append(f"  ## {fp}")
                    snippet = content[:700].strip()
                    for sl in snippet.splitlines():
                        lines.append(f"    {sl}")
                    lines.append("")

        # ── Errores previos (reintentos) ──────────────────────────────────────
        if t.get("errores_runtime_nivel_anterior"):
            lines.append("ERRORES DEL INTENTO ANTERIOR (corregir):")
            lines.append(t["errores_runtime_nivel_anterior"][:500])
            lines.append("")

        # ── Esqueleto base (modo logic) ───────────────────────────────────────
        if t.get("ESQUELETO_BASE"):
            lines.append("ESQUELETO BASE (completar la lógica interna):")
            lines.append(t["ESQUELETO_BASE"][:2000])
            lines.append("")

        # ── Diseño UI ─────────────────────────────────────────────────────────
        if t.get("especificacion_diseno"):
            spec = t["especificacion_diseno"]
            if isinstance(spec, dict):
                spec = json.dumps(spec, ensure_ascii=False)
            lines.append("Especificación de diseño:")
            lines.append(str(spec)[:500])
            lines.append("")

        lines.append(f"Generá ÚNICAMENTE el contenido completo del archivo `{archivo}`. Sin markdown, sin explicaciones.")
        return "\n".join(lines)

    def _validate_syntax(self, code: str, filepath: str) -> tuple[bool, str]:
        ext = Path(filepath).suffix.lower()
        if ext in NON_PYTHON_EXTENSIONS:
            return True, "non-python: skip syntax check"
        if not self.sandbox.available:
            return True, "docker unavailable: syntax check skipped"
        result = self.sandbox.run(
            code=SYNTAX_CHECK,
            extra_files={"target.py": code},
        )
        if "DOCKER_UNAVAILABLE" in result.stdout:
            return True, "docker unavailable: syntax check skipped"
        ok = result.success and "SYNTAX_OK" in result.stdout
        return ok, result.stdout.strip()

    @staticmethod
    def _strip_fence(code: str) -> str:
        """Strip opening/closing markdown code fences that AI models wrap responses in."""
        lines = code.strip().splitlines()
        if not lines:
            return code
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)

    def _sanitize_package_json_content(self, content: str) -> str:
        """Fix broken dependency declarations in generated package.json."""
        try:
            pkg = json.loads(content)
        except Exception:
            return content
        changed = False
        
        npm_heuristics = self._heuristics.get("npm_heuristics", {})
        wrong_names = npm_heuristics.get("wrong_package_names", {})
        version_corrections = npm_heuristics.get("version_corrections", {})
        
        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            deps = pkg.get(section)
            if not isinstance(deps, dict):
                continue
            for wrong, correct in wrong_names.items():
                if wrong in deps:
                    deps[correct] = deps.pop(wrong)
                    changed = True
            for name in list(deps.keys()):
                v = deps[name]
                if v in ("undefined", None, ""):
                    deps[name] = "*"
                    changed = True
                elif name in version_corrections:
                    deps[name] = version_corrections[name]
                    changed = True
        if not changed:
            return content
        return json.dumps(pkg, indent=2, ensure_ascii=False) + "\n"

    def _prepare_generated_code(self, response: str, goal_id: str, goal_hash: str, filepath: str) -> str:
        code = self._strip_fence(response or "")
        ext = Path(filepath).suffix.lower()
        if Path(filepath).name == "package.json":
            code = self._sanitize_package_json_content(code)
        elif ext in PYTHON_EXTENSIONS and code and not self._is_driver_error(code) and not code.lstrip().startswith("Error"):
            code = self.metadata_injector.ensure_metadata(code, goal_id, goal_hash, filepath)
        else:
            # Strip any # --- METADATA SODA --- lines the model erroneously added to JS/TS/CSS
            code = self.metadata_injector.strip_misplaced_metadata(code, filepath)
        return code

    @staticmethod
    def _is_driver_error(response: str) -> bool:
        return response.startswith("ERROR:")

    @staticmethod
    def _parse_driver_error(response: str) -> tuple[str, str]:
        """Returns (error_code, human_message) from 'ERROR:CODE: message'."""
        if not response.startswith("ERROR:"):
            return ("UNKNOWN", response)
        rest = response[6:]
        if ":" in rest:
            code, msg = rest.split(":", 1)
            return code.strip(), msg.strip()
        return ("UNKNOWN", rest)

    async def _call_ollama(self, task: str, filepath: str, attempt: int,
                           error_context: Optional[str] = None,
                           skills_context: Optional[str] = None,
                           profile_context: Optional[str] = None) -> str:
        # B — temperatura escalonada: baja en intento 1, sube en reintentos
        temperature = self.QWEN_TEMPERATURES[min(attempt - 1, len(self.QWEN_TEMPERATURES) - 1)]
        self.notify(
            f"Qwen generando {filepath} (intento {attempt}/{self.MAX_LOCAL_RETRIES}, temp={temperature})",
            "AI_WORKING",
            {"ai": "Qwen", "model": self.ollama.model, "file": filepath, "attempt": attempt, "temperature": temperature},
        )
        user = self._format_task_for_qwen(task)
        if error_context:
            user += f"\n\nERROR EN INTENTO PREVIO:\n{error_context}"

        # Inject learned examples from the knowledge base into Qwen's prompt
        few_shot = None
        if self.coach is not None:
            try:
                few_shot = self.coach.build_few_shot_context(task, filepath) or None
            except Exception:
                pass

        payload = self.builder.build_payload(
            "ollama", "code_generator", user,
            skills_context=skills_context,
            profile_context=profile_context,
            few_shot_examples=few_shot,
        )
        response = await self.ollama.call(payload["system"], payload["user"], temperature=temperature)
        if hasattr(response, "content"):
            response = response.content
        if self._is_driver_error(response):
            code, msg = self._parse_driver_error(response)
            self.notify(msg, "AI_ERROR", {"ai": "Qwen", "error_code": code, "file": filepath})
        return response

    async def _call_claude(self, task: str, filepath: str,
                           error_context: Optional[str] = None,
                           skills_context: Optional[str] = None,
                           profile_context: Optional[str] = None) -> str:
        self.notify(
            f"Claude escalando {filepath}",
            "AI_WORKING",
            {"ai": "Claude", "model": "claude-sonnet-4-6", "file": filepath, "attempt": "escalada"},
        )
        user = task
        if error_context:
            user += f"\n\nFALLÓ EL MODELO LOCAL. ERROR:\n{error_context}"
        payload = self.builder.build_payload(
            "claude", "code_generator", user,
            skills_context=skills_context,
            profile_context=profile_context,
        )
        response = await self.claude.prompt(payload["system"], payload["user"])
        if self._is_driver_error(response):
            code, msg = self._parse_driver_error(response)
            self.notify(msg, "AI_ERROR", {"ai": "Claude", "error_code": code, "file": filepath})
        return response

    async def _call_gemini(self, task: str, filepath: str,
                           error_context: Optional[str] = None,
                           skills_context: Optional[str] = None,
                           profile_context: Optional[str] = None) -> str:
        self.notify(
            f"Gemini escalando {filepath}",
            "AI_WORKING",
            {"ai": "Gemini", "file": filepath, "attempt": "escalada-gemini"},
        )
        user = task
        if error_context:
            user += f"\n\nFALLÓ CLAUDE. ERROR:\n{error_context}"
        payload = self.builder.build_payload(
            "gemini", "code_generator", user,
            skills_context=skills_context,
            profile_context=profile_context,
        )
        dr = await self.gemini.call(payload["system"], payload["user"])
        response = dr.content
        if self._is_driver_error(response):
            code, msg = self._parse_driver_error(response)
            self.notify(msg, "AI_ERROR", {"ai": "Gemini", "error_code": code, "file": filepath})
        return response

    async def _call_claude_haiku(self, task: str, filepath: str,
                                  error_context: Optional[str] = None,
                                  skills_context: Optional[str] = None,
                                  profile_context: Optional[str] = None) -> str:
        """Level 6 fallback — Claude Haiku (faster/cheaper than Sonnet for recovery)."""
        self.notify(
            f"Claude Haiku (L6) escalando {filepath}",
            "AI_WORKING",
            {"ai": "Claude Haiku", "model": "claude-haiku-4-5-20251001", "file": filepath, "attempt": "L6"},
        )
        user = task
        if error_context:
            user += f"\n\nFALLARRON TODOS LOS MODELOS ANTERIORES. ERROR:\n{error_context}"
        payload = self.builder.build_payload(
            "claude", "code_generator", user,
            skills_context=skills_context, profile_context=profile_context,
        )
        # Use claude driver with haiku model if it supports model switching, else fall back to default
        if hasattr(self.claude, "prompt_with_model"):
            response = await self.claude.prompt_with_model(
                payload["system"], payload["user"], model="claude-haiku-4-5-20251001"
            )
        else:
            response = await self.claude.prompt(payload["system"], payload["user"])
        if self._is_driver_error(response):
            code, msg = self._parse_driver_error(response)
            self.notify(msg, "AI_ERROR", {"ai": "Claude Haiku", "error_code": code, "file": filepath})
        return response

    async def generate_file(
        self, filepath: str, module: dict, blueprint: dict, architecture: dict,
        user_requirements: str = "",
        dependency_context: Optional[dict] = None,
        skills_context: Optional[str] = None,
        profile_context: Optional[str] = None,
        design_context: Optional[str] = None,
        source_dir: Optional[Path] = None,
        runtime_errors: str = "",
        master_contract: Optional[dict] = None,
    ) -> GeneratedFile:
        # Skip AI generation for static/binary assets
        ext = Path(filepath).suffix.lower()
        if ext in {".svg", ".png", ".jpg", ".jpeg", ".ico", ".webp", ".gif"}:
            stub_content = (
                f"<!-- Placeholder for {filepath} -->\n"
                "<svg width='100' height='100' xmlns='http://www.w3.org/2000/svg'>"
                "<rect width='100' height='100' fill='#cccccc'/></svg>"
            ) if ext == ".svg" else ""
            self.notify(f"By-pass archivo estático: {filepath}", "FILE_GENERATED", {"filepath": filepath})
            return GeneratedFile(filepath=filepath, content=stub_content,
                                 goal_id=module.get("goal_id", "G-ASSET"), validated=True, attempts=0)

        # Skip files already provided by an injected template
        _rel = filepath.replace("\\", "/").lstrip("/")
        if _rel in self.injected_files:
            goal_id = build_file_goal_id(module["nombre"], filepath)
            self.notify(f"Saltando {filepath} — provisto por plantilla", "FILE_SKIPPED",
                        {"filepath": filepath, "source": "template"})
            return GeneratedFile(filepath=filepath, content="", goal_id=goal_id, validated=True, attempts=0)

        # compute goal_id/hash directly
        goal_id = build_file_goal_id(module["nombre"], filepath)
        _gn = build_file_goal_node(module, filepath)
        goal_hash = _gn.hash or _gn.sync_hash()

        # Check if GBrain has relevant notes for this specific file or task
        gbrain_context = ""
        if hasattr(self, "orch") and self.orch and hasattr(self.orch, "gbrain") and self.orch.gbrain.is_available():
            try:
                # Query using the filepath or user requirements or module context
                search_term = f"{filepath} {module.get('descripcion', '') or module.get('responsabilidad', '')}"
                gbrain_context = self.orch.gbrain.get_rag_context(search_term)
            except Exception:
                pass

        _base_task_kwargs = dict(
            filepath=filepath, module=module, blueprint=blueprint, architecture=architecture,
            user_requirements=user_requirements, dependency_context=dependency_context,
            design_context=design_context, source_dir=source_dir,
            runtime_errors=runtime_errors, master_contract=master_contract,
            gbrain_context=gbrain_context,
        )

        # C — incremental rebuild: skip Python files whose goal_hash matches what's on disk.
        if source_dir is not None and ext in PYTHON_EXTENSIONS:
            _existing = source_dir / filepath
            if _existing.exists():
                try:
                    _cached = _existing.read_text(encoding="utf-8", errors="ignore")
                    if f"# goal_hash: {goal_hash}" in _cached:
                        self.notify(f"Saltando {filepath} — sin cambios", "FILE_SKIPPED",
                                    {"filepath": filepath, "goal_hash": goal_hash})
                        return GeneratedFile(filepath, _cached, goal_id, validated=True, attempts=0)
                except Exception:
                    pass

        # 9-level escalation ladder:
        last_error = ""
        last_failed_code = ""
        last_error_reason = ""
        qwen_errors = []
        qwen_attempt = 0
        gemini_attempt = 0
        claude_attempt = 0
        response = ""
        _log_context_injected = False

        for attempt_num in range(1, 10):
            # Decisión de enrutamiento
            if attempt_num > 1 and last_error:
                decision = await self._analyze_error_and_decide(filepath, last_error, attempt_num)
                if decision == "escalate" and attempt_num <= self.MAX_LOCAL_RETRIES:
                    self.notify(f"Escalado inteligente activado para {filepath} (Error de diseño).", "LOG")
                    attempt_num = 4 

            level = self.ESCALATION_LEVELS[attempt_num-1]
            is_cloud = level in ("gemini", "claude")

            # On first cloud escalation, append system logs
            if is_cloud and not _log_context_injected:
                _log_context_injected = True
                try:
                    log_snippet = self._log_collector.collect(stack=blueprint.get("stack_sugerido", {}).get("backend", "python"), workspace=source_dir)
                    if log_snippet: last_error = f"{last_error}\n{log_snippet}"
                except: pass

            if level == "qwen":
                qwen_attempt += 1
                task = self._build_task(**_base_task_kwargs, qwen_attempt=qwen_attempt)
                raw = await self._call_ollama(task, filepath, qwen_attempt, last_error, skills_context, profile_context)
            elif level == "gemini":
                gemini_attempt += 1
                task = self._build_task(**_base_task_kwargs, qwen_attempt=1)
                _ec = self._build_escalation_context(last_failed_code, last_error_reason) if gemini_attempt == 1 and last_failed_code else last_error
                raw = await self._call_gemini(task, filepath, _ec, skills_context, profile_context)
            else:
                claude_attempt += 1
                task = self._build_task(**_base_task_kwargs, qwen_attempt=1)
                _ec = self._build_escalation_context(last_failed_code, last_error_reason) if claude_attempt == 1 and last_failed_code else last_error
                raw = await self._call_claude(task, filepath, _ec, skills_context, profile_context)

            response = self._prepare_generated_code(raw, goal_id, goal_hash, filepath)
            
            # Validación
            is_valid, validation_msg = self._validate_syntax(response, filepath)
            if is_valid and response and not self._is_driver_error(response):
                self.notify(f"Archivo {filepath} generado con éxito usando {level} (L{attempt_num})", "SUCCESS")
                
                # SODA Beta: Register Shadow Mode Traces
                if hasattr(self, "orch") and self.orch:
                    try:
                        self.orch.observatory.register_success(
                            filepath=filepath,
                            module=module,
                            blueprint=blueprint,
                            architecture=architecture,
                            code_content=response,
                            gbrain_context=gbrain_context
                        )
                        if attempt_num > 1 and last_failed_code:
                            self.orch.observatory.register_repair(
                                last_failed_code=last_failed_code,
                                last_error_reason=last_error_reason,
                                corrected_code=response,
                                filepath=filepath,
                                attempt_num=attempt_num
                            )
                    except Exception:
                        pass

                return GeneratedFile(filepath, response, goal_id, validated=True, attempts=attempt_num)

            last_error_reason = validation_msg or "respuesta inválida"
            last_failed_code = response
            last_error = f"{last_error_reason}\n\n{response[:800]}"
            if level == "qwen": qwen_errors.append(last_error[:500])

        # Final failure
        self.notify(f"CRÍTICO: Fallaron los 9 niveles para {filepath}.", "HEALTH_WARN")
        return GeneratedFile(filepath, response, goal_id, validated=False, attempts=9)

    async def generate_module(
        self, module: dict, blueprint: dict, architecture: dict,
        copilot_feedback: Optional[str] = None,
        user_requirements: str = "",
        dependency_context: Optional[dict] = None,
        skills_context: Optional[str] = None,
        profile_context: Optional[str] = None,
        design_context: Optional[str] = None,
        source_dir: Optional[Path] = None,
        runtime_errors: str = "",
        master_contract: Optional[dict] = None,
    ) -> list[GeneratedFile]:
        mod = dict(module)
        if copilot_feedback:
            mod["_copilot_feedback"] = copilot_feedback
        files = mod.get("archivos_principales", [])
        tag = f"[paralelo x{len(files)}]" if len(files) > 1 else "[1 archivo]"
        print(f"  [->] Módulo: {mod['nombre']} ({len(files)} archivo/s) {tag}")

        tasks = [
            self.generate_file(
                filepath, mod, blueprint, architecture,
                user_requirements=user_requirements,
                dependency_context=dependency_context,
                skills_context=skills_context,
                profile_context=profile_context,
                design_context=design_context,
                source_dir=source_dir,
                runtime_errors=runtime_errors,
                master_contract=master_contract,
            )
            for filepath in files
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[GeneratedFile] = []
        for filepath, result in zip(files, raw_results):
            if isinstance(result, Exception):
                print(f"    [!] {filepath} — error en generación paralela: {result}")
                goal_id = build_file_goal_id(mod["nombre"], filepath)
                results.append(GeneratedFile(filepath, "", goal_id, validated=False, attempts=9))
            else:
                results.append(result)
        return results
