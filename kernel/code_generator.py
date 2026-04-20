import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from kernel.context.context_builder import ContextBuilder
from kernel.docker_sandbox import DockerSandbox
from kernel.integrity.goal_integrity_validator import GoalIntegrityValidator


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
NON_PYTHON_EXTENSIONS = {".html", ".css", ".js", ".json", ".yaml", ".yml", ".md", ".txt"}


class CodeGenerator:
    MAX_LOCAL_RETRIES = 3

    def __init__(self, ollama_driver, claude_driver):
        self.ollama = ollama_driver
        self.claude = claude_driver
        self.builder = ContextBuilder()
        self.sandbox = DockerSandbox()
        self.validator = GoalIntegrityValidator()

    def _build_task(self, filepath: str, module: dict, blueprint: dict, architecture: dict) -> str:
        stack = blueprint.get("stack_sugerido", {})
        contracts = architecture.get("contratos", [])
        relevant = [
            c for c in contracts
            if module["nombre"] in (c.get("modulo_origen", ""), c.get("modulo_destino", ""))
        ]
        goal_id = f"{module['nombre'].lower().replace(' ', '_')}__{Path(filepath).stem}"

        return json.dumps({
            "archivo_a_generar": filepath,
            "goal_id": goal_id,
            "modulo": module["nombre"],
            "responsabilidad": module["responsabilidad"],
            "stack": stack,
            "dependencias_del_modulo": module.get("dependencias", []),
            "contratos_relevantes": relevant,
            "endpoints": module.get("endpoints", []),
        }, ensure_ascii=False, indent=2)

    def _validate_syntax(self, code: str, filepath: str) -> tuple[bool, str]:
        ext = Path(filepath).suffix.lower()
        if ext in NON_PYTHON_EXTENSIONS:
            return True, "non-python: skip syntax check"
        result = self.sandbox.run(
            code=SYNTAX_CHECK,
            extra_files={"target.py": code},
        )
        ok = result.success and "SYNTAX_OK" in result.stdout
        return ok, result.stdout.strip()

    async def _call_ollama(self, task: str, error_context: Optional[str] = None) -> str:
        user = task
        if error_context:
            user += f"\n\nERROR EN INTENTO PREVIO:\n{error_context}"
        payload = self.builder.build_payload("ollama", "code_generator", user)
        return await self.ollama.prompt(payload["system"], payload["user"])

    async def _call_claude(self, task: str, error_context: Optional[str] = None) -> str:
        user = task
        if error_context:
            user += f"\n\nFALLÓ EL MODELO LOCAL. ERROR:\n{error_context}"
        payload = self.builder.build_payload("claude", "code_generator", user)
        return await self.claude.prompt(payload["system"], payload["user"])

    async def generate_file(
        self, filepath: str, module: dict, blueprint: dict, architecture: dict
    ) -> GeneratedFile:
        task = self._build_task(filepath, module, blueprint, architecture)
        goal_id = json.loads(task)["goal_id"]
        last_error: Optional[str] = None
        attempts = 0

        for attempt in range(1, self.MAX_LOCAL_RETRIES + 1):
            attempts = attempt
            print(f"    [Qwen] {filepath} — intento {attempt}/{self.MAX_LOCAL_RETRIES}")
            response = await self._call_ollama(task, last_error)

            if "Error" in response:
                last_error = response[:200]
                continue

            ext = Path(filepath).suffix.lower()
            if ext in PYTHON_EXTENSIONS and not self.validator.validate_content(response):
                last_error = "Metadata SODA faltante o mal formada"
                continue

            ok, msg = self._validate_syntax(response, filepath)
            if ok:
                print(f"    [OK] {filepath} — OK en intento {attempt}")
                return GeneratedFile(filepath, response, goal_id, validated=True, attempts=attempt)

            last_error = msg

        # Escalada a Claude
        attempts += 1
        print(f"    [^^] Escalando a Claude para {filepath}...")
        response = await self._call_claude(task, last_error)

        ext = Path(filepath).suffix.lower()
        needs_metadata = ext in PYTHON_EXTENSIONS
        if "Error" not in response and (not needs_metadata or self.validator.validate_content(response)):
            ok, _ = self._validate_syntax(response, filepath)
            if ok:
                print(f"    [OK] {filepath} — OK vía Claude")
                return GeneratedFile(filepath, response, goal_id, validated=True, attempts=attempts)

        print(f"    [!] {filepath} — falló todos los intentos. Guardando igualmente.")
        return GeneratedFile(filepath, response or "", goal_id, validated=False, attempts=attempts)

    async def generate_module(
        self, module: dict, blueprint: dict, architecture: dict
    ) -> list[GeneratedFile]:
        files = module.get("archivos_principales", [])
        print(f"  [->] Módulo: {module['nombre']} ({len(files)} archivo/s)")
        results = []
        for filepath in files:
            result = await self.generate_file(filepath, module, blueprint, architecture)
            results.append(result)
        return results
