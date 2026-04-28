import asyncio
import json
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
        # C: Dynamic Model Router — pre-classify files before calling any AI
        from kernel.intelligence.file_complexity_router import FileComplexityRouter
        self._router = FileComplexityRouter()
        # Template injection: paths relative to source_dir that were copied from a template.
        # generate_file skips generation for these — template content wins.
        self.injected_files: set[str] = set()

    # B — Temperatura escalonada por intento de Qwen
    # Intento 1: determinístico (evita alucinaciones en el camino feliz)
    # Intento 2: algo de variación (el primero falló, necesitamos diferencia)
    # Intento 3: máxima variación (último recurso antes de escalar a la nube)
    QWEN_TEMPERATURES = [0.2, 0.5, 0.7]

    def _build_task(
        self, filepath: str, module: dict, blueprint: dict, architecture: dict,
        user_requirements: str = "",
        dependency_context: Optional[dict] = None,
        design_context: Optional[str] = None,
        source_dir: Optional[Path] = None,
        qwen_attempt: int = 1,
        runtime_errors: str = "",
    ) -> str:
        stack = blueprint.get("stack_sugerido", {})
        contracts = architecture.get("contratos", [])
        relevant = [
            c for c in contracts
            if module["nombre"] in (c.get("modulo_origen", ""), c.get("modulo_destino", ""))
        ]
        goal_id = build_file_goal_id(module["nombre"], filepath)
        goal_hash = build_file_goal_node(module, filepath).hash or build_file_goal_node(module, filepath).sync_hash()

        # A — Prompt adaptivo: los reintentos de Qwen usan un JSON más pequeño.
        # El contexto exhaustivo (dependencias, contratos, diseño) ayuda en el intento 1
        # pero satura el context window de Qwen 7B en los reintentos — empeora la calidad.
        is_qwen_retry = qwen_attempt > 1

        task: dict = {
            "archivo_a_generar": filepath,
            "goal_id": goal_id,
            "goal_hash": goal_hash,
            "modulo": module["nombre"],
            "responsabilidad": module["responsabilidad"],
            "stack": stack,
            "endpoints": module.get("endpoints", []),
        }

        # Contratos y lista de dependencias: siempre en intento 1; omitidos en reintentos
        if not is_qwen_retry:
            task["dependencias_del_modulo"] = module.get("dependencias", [])
            task["contratos_relevantes"] = relevant

        # Copilot feedback y requisitos: siempre presentes (son cortos y directamente útiles)
        if "_copilot_feedback" in module:
            task["copilot_feedback"] = module["_copilot_feedback"]
        if user_requirements:
            task["requisitos_usuario"] = user_requirements

        html_hint = get_html_hint(filepath, blueprint, architecture)
        if html_hint and not is_qwen_retry:
            task["plantilla_ui"] = html_hint.strip()

        # Código de dependencias: límites reducidos en reintentos de Qwen para no saturar
        if dependency_context:
            MAX_CHARS = 800 if is_qwen_retry else 3000
            MAX_FILES = 2 if is_qwen_retry else 4
            dep_code: dict = {}
            for dep_nombre in module.get("dependencias", []):
                if dep_nombre not in dependency_context:
                    continue
                files = dependency_context[dep_nombre]
                truncated = {
                    fp: (content[:MAX_CHARS] + "\n# ... (truncado)" if len(content) > MAX_CHARS else content)
                    for fp, content in list(files.items())[:MAX_FILES]
                }
                if truncated:
                    dep_code[dep_nombre] = truncated
            if dep_code:
                task["codigo_generado_dependencias"] = dep_code

        # Errores de runtime del nivel anterior: siempre presentes (crítico para el fix)
        if runtime_errors:
            task["errores_runtime_nivel_anterior"] = runtime_errors[:1200]

        # Especificación de diseño: solo en intento 1 (es el campo más largo)
        if design_context and not is_qwen_retry:
            task["especificacion_diseno"] = design_context

        return json.dumps(task, ensure_ascii=False, indent=2)

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

    # AI models frequently generate wrong package names or literal "undefined" versions.
    _WRONG_PKG_NAMES: dict[str, str] = {
        "@framer-motion/framer-motion": "framer-motion",
        "@react-router/react-router": "react-router",
        "@axios/axios": "axios",
        "@lodash/lodash": "lodash",
    }

    # AI frequently hallucinates non-existent patch/minor versions for these packages.
    # Pinned to the latest known-stable semver range.
    _VERSION_CORRECTIONS: dict[str, str] = {
        "@types/jest": "^29.5.0",
        "@types/node": "^20.0.0",
        "@types/react": "^18.0.0",
        "@types/react-dom": "^18.0.0",
        "@types/express": "^4.17.0",
        "@types/lodash": "^4.14.0",
        "@types/uuid": "^9.0.0",
        "nodemailer": "^6.9.0",
        "next-auth": "^4.24.0",
        "@electron-toolkit/preload": "^3.0.0",
        "@electron-toolkit/utils": "^3.0.0",
    }

    @classmethod
    def _sanitize_package_json_content(cls, content: str) -> str:
        """Fix broken dependency declarations in generated package.json."""
        try:
            pkg = json.loads(content)
        except Exception:
            return content
        changed = False
        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            deps = pkg.get(section)
            if not isinstance(deps, dict):
                continue
            for wrong, correct in cls._WRONG_PKG_NAMES.items():
                if wrong in deps:
                    deps[correct] = deps.pop(wrong)
                    changed = True
            for name in list(deps.keys()):
                v = deps[name]
                if v in ("undefined", None, ""):
                    deps[name] = "*"
                    changed = True
                elif name in cls._VERSION_CORRECTIONS:
                    deps[name] = cls._VERSION_CORRECTIONS[name]
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
        user = task
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

        # Build the initial full task (attempt 1) to extract goal_id/hash
        _base_task_kwargs = dict(
            filepath=filepath, module=module, blueprint=blueprint, architecture=architecture,
            user_requirements=user_requirements, dependency_context=dependency_context,
            design_context=design_context, source_dir=source_dir,
            runtime_errors=runtime_errors,
        )
        task = self._build_task(**_base_task_kwargs, qwen_attempt=1)
        task_payload = json.loads(task)
        goal_id = task_payload["goal_id"]
        goal_hash = task_payload["goal_hash"]

        # C — incremental rebuild: skip Python files whose goal_hash matches what's on disk.
        # Avoids regenerating files that haven't changed between runs (partial failures, modify()).
        if source_dir is not None and ext in PYTHON_EXTENSIONS:
            _existing = source_dir / filepath
            if _existing.exists():
                try:
                    _cached = _existing.read_text(encoding="utf-8", errors="ignore")
                    if f"# goal_hash: {goal_hash}" in _cached:
                        print(f"    [SKIP] {filepath} — sin cambios (goal_hash match)")
                        self.notify(f"Saltando {filepath} — sin cambios", "FILE_SKIPPED",
                                    {"filepath": filepath, "goal_hash": goal_hash})
                        return GeneratedFile(filepath, _cached, goal_id, validated=True, attempts=0)
                except Exception:
                    pass  # fall through to full generation
        last_error: Optional[str] = None
        response = ""
        _fail_reason: list[str] = []  # single-element list; populated by _is_good on failure

        def _is_good(resp: str) -> bool:
            _fail_reason.clear()
            if not resp or resp.lstrip().startswith("Error") or self._is_driver_error(resp):
                _fail_reason.append("respuesta vacía o error de driver")
                return False
            ok, msg = self._validate_syntax(resp, filepath)
            if not ok:
                _fail_reason.append(msg or "error de sintaxis")
                return False
            # C: metadata is always post-processed by _prepare_generated_code before _is_good
            # is called — never reject valid code because of missing metadata.
            return True

        qwen_attempt = 0
        gemini_attempt = 0
        claude_attempt = 0
        qwen_errors: list[str] = []
        first_cloud_level: Optional[str] = None  # track when we leave Qwen
        _log_context_injected = False             # inject logs only once per escalation

        # Resolve stack name for log collection
        _stack_name = (
            blueprint.get("stack_sugerido", {}).get("backend", "")
            or blueprint.get("stack_sugerido", {}).get("frontend", "")
            or ""
        ).lower()

        # C: Dynamic Model Router — classify before the loop to skip Qwen for complex files
        _complexity = self._router.classify(filepath, module)
        _effective_levels = self._router.effective_levels(_complexity, self.ESCALATION_LEVELS)
        if _complexity != "simple":
            self.notify(
                f"Router: {filepath} → {_complexity.upper()}, "
                f"saltando a {_effective_levels[0].capitalize()} directamente",
                "LOG",
                {"filepath": filepath, "complexity": _complexity},
            )

        for level_idx, level in enumerate(_effective_levels):
            attempt_num = level_idx + 1
            is_cloud = level in ("claude", "gemini")

            # On first cloud escalation, append system logs to error context
            if is_cloud and not _log_context_injected:
                _log_context_injected = True
                try:
                    log_snippet = self._log_collector.collect(
                        stack=_stack_name or "node",
                        workspace=source_dir,
                    )
                    if log_snippet and last_error:
                        last_error = f"{last_error}\n{log_snippet}"
                    elif log_snippet:
                        last_error = log_snippet
                except Exception as _lc_exc:
                    print(f"    [log_collector] collect() falló (ignorado): {_lc_exc}")

            if level == "qwen":
                qwen_attempt += 1
                # A — reconstruir el task para cada intento: reintentos usan prompt reducido
                task = self._build_task(**_base_task_kwargs, qwen_attempt=qwen_attempt)
                temp = self.QWEN_TEMPERATURES[min(qwen_attempt - 1, len(self.QWEN_TEMPERATURES) - 1)]
                print(f"    [L{attempt_num}/Qwen] {filepath} — intento {qwen_attempt}/3 (temp={temp})")
                raw = await self._call_ollama(task, filepath, qwen_attempt, last_error, skills_context, profile_context)

            elif level == "gemini":
                if not self.gemini:
                    last_error = f"L{attempt_num} Gemini no disponible"
                    continue
                if first_cloud_level is None:
                    first_cloud_level = "gemini"
                gemini_attempt += 1
                # B: first Gemini attempt gets full context; re-escalations focus on the error only
                _sc = skills_context if gemini_attempt == 1 else None
                _pc = profile_context if gemini_attempt == 1 else None
                print(f"    [L{attempt_num}/Gemini] {filepath} — intento {gemini_attempt}/3")
                raw = await self._call_gemini(task, filepath, last_error, _sc, _pc)

            elif level == "claude":
                if first_cloud_level is None:
                    first_cloud_level = "claude"
                claude_attempt += 1
                # B: first Claude attempt gets full context; re-escalations focus on the error only
                _sc = skills_context if claude_attempt == 1 else None
                _pc = profile_context if claude_attempt == 1 else None
                print(f"    [L{attempt_num}/Claude] {filepath} — intento {claude_attempt}/3")
                raw = await self._call_claude(task, filepath, last_error, _sc, _pc)

            else:
                continue

            response = self._prepare_generated_code(raw, goal_id, goal_hash, filepath)

            if _is_good(response):
                print(f"    [OK] {filepath} — OK vía {level} (L{attempt_num})")
                module_name = module.get("nombre", "")
                project_id = blueprint.get("project_id", "") or blueprint.get("id", "")
                framework = " ".join(str(v) for v in blueprint.get("stack_sugerido", {}).values())[:60]

                # Record successful generation for all providers
                if self.observer is not None:
                    try:
                        self.observer.record_code_generation(
                            provider=level,
                            filepath=filepath,
                            task_summary=task[:400],
                            response_snippet=response[:600],
                            validated=True,
                            attempt=attempt_num,
                            project_id=project_id,
                            module_name=module_name,
                            framework=framework,
                        )
                        # If this was a cloud escalation, record the escalation case
                        if is_cloud and qwen_errors:
                            self.observer.record_escalation(
                                filepath=filepath,
                                qwen_attempts=qwen_errors,
                                cloud_provider=level,
                                cloud_response_snippet=response[:800],
                                cloud_validated=True,
                                failure_reason=qwen_errors[-1][:200] if qwen_errors else "",
                                project_id=project_id,
                                module_name=module_name,
                            )
                    except Exception as _obs_exc:
                        print(f"    [observer] record_code_generation error (ignorado): {_obs_exc}")

                if self.tracker is not None:
                    self.tracker.record_file_generated(
                        provider=level, level=attempt_num, validated=True
                    )
                return GeneratedFile(filepath, response, goal_id, validated=True, attempts=attempt_num)

            # A: include rejection reason so the next model knows WHY it failed, not just what it generated
            _reason = _fail_reason[0] if _fail_reason else ""
            _snippet = response[:800] if response else ""
            last_error = f"{_reason}\n\n{_snippet}" if (_reason and _snippet) else (_reason or _snippet or f"L{attempt_num} vacío")
            if level == "qwen":
                qwen_errors.append(last_error[:500])

        # All 9 levels failed — notify with full context
        _all_errors_summary = {
            "qwen_errors": [e[:300] for e in qwen_errors],
            "last_response_snippet": (response or "")[:800],
            "file": filepath,
            "module": module.get("nombre", ""),
        }
        print(f"    [!] {filepath} — 9 niveles fallaron (Qwen×3 → Gemini×3 → Claude×3). Guardando sin validar.")
        if self._notify_fn:
            self._notify_fn(
                f"CRÍTICO: {filepath} — todos los 9 niveles de escalación fallaron. Guardando sin validar.",
                "HEALTH_WARN",
                {"phase": "development", **_all_errors_summary},
            )
        if self.tracker is not None:
            self.tracker.record_file_generated(
                provider="none", level=len(self.ESCALATION_LEVELS), validated=False
            )
        return GeneratedFile(
            filepath,
            self._prepare_generated_code(response or "", goal_id, goal_hash, filepath),
            goal_id,
            validated=False,
            attempts=len(self.ESCALATION_LEVELS),
        )

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
    ) -> list[GeneratedFile]:
        mod = dict(module)
        if copilot_feedback:
            mod["_copilot_feedback"] = copilot_feedback
        files = mod.get("archivos_principales", [])
        tag = f"[paralelo x{len(files)}]" if len(files) > 1 else "[1 archivo]"
        print(f"  [->] Módulo: {mod['nombre']} ({len(files)} archivo/s) {tag}")

        # A — parallel file generation: files within the same module are independent
        # (dependency_context only contains already-completed modules, not sibling files).
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
