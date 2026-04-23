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
    # 6-level escalation ladder:
    # L1-L3: Qwen retries  L4: Claude  L5: Gemini  L6: Claude Haiku (fallback)
    ESCALATION_LEVELS = ["qwen", "qwen", "qwen", "claude", "gemini", "claude_haiku"]

    def __init__(self, ollama_driver, claude_driver, gemini_driver=None):
        self.ollama = ollama_driver
        self.claude = claude_driver
        self.gemini = gemini_driver
        self.builder = ContextBuilder()
        self.sandbox = DockerSandbox()
        self.metadata_injector = MetadataInjector()
        self.validator = GoalIntegrityValidator()
        self.notify: Callable = _noop  # set by orchestrator after init
        # Learning system — set by orchestrator after init
        self.observer = None   # BehaviorObserver | None
        self.coach = None      # LocalAICoach | None
        self.tracker = None    # PerformanceTracker | None — set by orchestrator after init

    def _build_task(
        self, filepath: str, module: dict, blueprint: dict, architecture: dict,
        user_requirements: str = "",
        dependency_context: Optional[dict] = None,
        design_context: Optional[str] = None,
    ) -> str:
        stack = blueprint.get("stack_sugerido", {})
        contracts = architecture.get("contratos", [])
        relevant = [
            c for c in contracts
            if module["nombre"] in (c.get("modulo_origen", ""), c.get("modulo_destino", ""))
        ]
        goal_id = build_file_goal_id(module["nombre"], filepath)
        goal_hash = build_file_goal_node(module, filepath).hash or build_file_goal_node(module, filepath).sync_hash()

        task: dict = {
            "archivo_a_generar": filepath,
            "goal_id": goal_id,
            "goal_hash": goal_hash,
            "modulo": module["nombre"],
            "responsabilidad": module["responsabilidad"],
            "stack": stack,
            "dependencias_del_modulo": module.get("dependencias", []),
            "contratos_relevantes": relevant,
            "endpoints": module.get("endpoints", []),
        }
        # Inject Copilot feedback when present (added by orchestrator Qwen↔Copilot loop)
        if "_copilot_feedback" in module:
            task["copilot_feedback"] = module["_copilot_feedback"]
        if user_requirements:
            task["requisitos_usuario"] = user_requirements
        html_hint = get_html_hint(filepath, blueprint, architecture)
        if html_hint:
            task["plantilla_ui"] = html_hint.strip()

        # Inject actual generated code from dependency modules so the AI can
        # match variable names, endpoints, import paths, and schemas exactly.
        if dependency_context:
            MAX_CHARS = 3000
            MAX_FILES = 4
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

        if design_context:
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

    def _prepare_generated_code(self, response: str, goal_id: str, goal_hash: str, filepath: str) -> str:
        code = self._strip_fence(response or "")
        ext = Path(filepath).suffix.lower()
        if ext in PYTHON_EXTENSIONS and code and not self._is_driver_error(code) and not code.lstrip().startswith("Error"):
            code = self.metadata_injector.ensure_metadata(code, goal_id, goal_hash)
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
        self.notify(
            f"Qwen generando {filepath} (intento {attempt}/{self.MAX_LOCAL_RETRIES})",
            "AI_WORKING",
            {"ai": "Qwen", "model": self.ollama.model, "file": filepath, "attempt": attempt},
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
        response = await self.ollama.prompt(payload["system"], payload["user"])
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
    ) -> GeneratedFile:
        task = self._build_task(
            filepath, module, blueprint, architecture,
            user_requirements=user_requirements,
            dependency_context=dependency_context,
            design_context=design_context,
        )
        task_payload = json.loads(task)
        goal_id = task_payload["goal_id"]
        goal_hash = task_payload["goal_hash"]
        last_error: Optional[str] = None
        response = ""

        ext = Path(filepath).suffix.lower()
        needs_metadata = ext in PYTHON_EXTENSIONS

        def _is_good(resp: str) -> bool:
            return (
                bool(resp)
                and not resp.lstrip().startswith("Error")
                and not self._is_driver_error(resp)
                and (not needs_metadata or self.validator.validate_content(resp))
                and self._validate_syntax(resp, filepath)[0]
            )

        qwen_attempt = 0
        qwen_errors: list[str] = []
        first_cloud_level: Optional[str] = None  # track when we leave Qwen

        for level_idx, level in enumerate(self.ESCALATION_LEVELS):
            attempt_num = level_idx + 1
            is_cloud = level in ("claude", "gemini", "claude_haiku")

            if level == "qwen":
                qwen_attempt += 1
                print(f"    [L{attempt_num}/Qwen] {filepath} — intento {qwen_attempt}")
                raw = await self._call_ollama(task, filepath, qwen_attempt, last_error, skills_context, profile_context)

            elif level == "claude":
                if first_cloud_level is None:
                    first_cloud_level = "claude"
                print(f"    [L{attempt_num}/Claude] Escalando {filepath}…")
                raw = await self._call_claude(task, filepath, last_error, skills_context, profile_context)

            elif level == "gemini":
                if not self.gemini:
                    continue
                if first_cloud_level is None:
                    first_cloud_level = "gemini"
                print(f"    [L{attempt_num}/Gemini] Escalando {filepath}…")
                raw = await self._call_gemini(task, filepath, last_error, skills_context, profile_context)

            elif level == "claude_haiku":
                if first_cloud_level is None:
                    first_cloud_level = "claude_haiku"
                print(f"    [L{attempt_num}/Haiku] Escalando {filepath}…")
                raw = await self._call_claude_haiku(task, filepath, last_error, skills_context, profile_context)

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
                    except Exception:
                        pass

                if self.tracker is not None:
                    self.tracker.record_file_generated(
                        provider=level, level=attempt_num, validated=True
                    )
                return GeneratedFile(filepath, response, goal_id, validated=True, attempts=attempt_num)

            last_error = response[:200] if response else f"L{attempt_num} vacío"
            if level == "qwen":
                qwen_errors.append(last_error)

        print(f"    [!] {filepath} — 6 niveles fallaron. Guardando sin validar.")
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
    ) -> list[GeneratedFile]:
        mod = dict(module)
        if copilot_feedback:
            mod["_copilot_feedback"] = copilot_feedback
        files = mod.get("archivos_principales", [])
        print(f"  [->] Módulo: {mod['nombre']} ({len(files)} archivo/s)")
        results = []
        for filepath in files:
            result = await self.generate_file(
                filepath, mod, blueprint, architecture,
                user_requirements=user_requirements,
                dependency_context=dependency_context,
                skills_context=skills_context,
                profile_context=profile_context,
                design_context=design_context,
            )
            results.append(result)
        return results
