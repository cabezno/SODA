"""functional_test_generator — generates E2E HTTP tests from blueprint funcionalidades.

Unlike TestGenerator (which tests units via typed interfaces), this module generates
black-box functional tests that verify the running application satisfies the user's
original requirements as stated in blueprint.funcionalidades.

Output: a single `tests/test_functional_e2e.py` (pytest + httpx) that exercises
every funcionalidad via real HTTP calls against a locally-running instance.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Callable


_E2E_OUTPUT_FILE = "tests/test_functional_e2e.py"
_MAX_FUNCIONALIDADES = 20   # cap to avoid token overload


class FunctionalTestGenerator:
    """Generates and optionally runs a functional E2E test suite from blueprint requirements."""

    def __init__(
        self,
        gemini_driver=None,
        context_builder=None,
        notify_fn: Optional[Callable] = None,
    ):
        self.gemini = gemini_driver
        self.builder = context_builder
        self._notify = notify_fn or (lambda *a, **kw: None)

    async def generate(
        self,
        source_dir: Path,
        blueprint: dict,
        architecture: dict,
        base_url: str = "http://localhost:8000",
    ) -> str | None:
        """Generate the E2E test file.

        Returns the generated test content, or None if generation failed.
        The file is written to `source_dir / tests / test_functional_e2e.py`.
        """
        funcionalidades = blueprint.get("funcionalidades", [])
        if not funcionalidades:
            self._notify("FunctionalTestGenerator: blueprint sin funcionalidades — omitiendo.", "LOG", {})
            return None

        # Build the prompt
        task = self._build_prompt(funcionalidades, blueprint, architecture, base_url)

        self._notify(
            f"FunctionalTestGenerator: generando suite E2E para {len(funcionalidades[:_MAX_FUNCIONALIDADES])} funcionalidad(es)…",
            "AI_WORKING",
            {"phase": "functional_tests"},
        )

        content: str | None = None

        # Try Gemini first (better at following HTTP patterns), then Gemini
        for driver, provider in [(self.gemini, "gemini"), (self.ollama, "ollama")]:
            if driver is None:
                continue
            try:
                if self.builder:
                    payload = self.builder.build_payload(provider, "functional_test_engineer", task)
                    if provider == "gemini":
                        raw = await driver.prompt(payload.get("system", ""), payload["user"])
                    else:
                        result = await driver.call(payload.get("system", ""), payload["user"])
                        raw = result.content if hasattr(result, "content") else str(result)
                else:
                    if provider == "gemini":
                        raw = await driver.prompt("", task)
                    else:
                        result = await driver.call("", task)
                        raw = result.content if hasattr(result, "content") else str(result)

                if hasattr(raw, "content"):
                    raw = raw.content
                stripped = self._strip_fence(str(raw or ""))
                if stripped and len(stripped.strip()) > 100 and not stripped.startswith("ERROR:"):
                    content = stripped
                    break
            except Exception as exc:
                self._notify(
                    f"FunctionalTestGenerator: {provider} falló: {exc}",
                    "HEALTH_WARN",
                    {"phase": "functional_tests", "provider": provider},
                )

        if not content:
            return None

        out = source_dir / _E2E_OUTPUT_FILE
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")

        self._notify(
            f"Suite E2E generada: {_E2E_OUTPUT_FILE}",
            "FILE_GENERATED",
            {"filename": _E2E_OUTPUT_FILE, "code": content, "validated": False, "phase": "functional_tests"},
        )
        return content

    def _build_prompt(
        self,
        funcionalidades: list,
        blueprint: dict,
        architecture: dict,
        base_url: str,
    ) -> str:
        stack = blueprint.get("stack_sugerido", {})

        # Serialize funcionalidades as compact list
        funcs_block = "\n".join(
            f"- [{f.get('id', f'func_{i}')}] {f.get('nombre', '')} — {f.get('descripcion', '')}"
            for i, f in enumerate(funcionalidades[:_MAX_FUNCIONALIDADES])
        )

        # Extract backend endpoints from architecture for context
        endpoints_block = self._summarize_endpoints(architecture)

        return (
            f"PROYECTO: {blueprint.get('nombre_proyecto', 'sin nombre')}\n"
            f"BASE_URL: {base_url}\n"
            f"STACK: {json.dumps(stack, ensure_ascii=False)}\n\n"
            f"<funcionalidades_requeridas>\n{funcs_block}\n</funcionalidades_requeridas>\n\n"
            f"<endpoints_conocidos>\n{endpoints_block}\n</endpoints_conocidos>\n\n"
            "INSTRUCCIÓN:\n"
            "Generá un archivo pytest completo (`tests/test_functional_e2e.py`) que:\n"
            "1. Use httpx.Client (síncrono) o pytest-asyncio + httpx.AsyncClient.\n"
            "2. Para cada funcionalidad en <funcionalidades_requeridas>, tenga AL MENOS un test que:\n"
            "   a) Llame al endpoint real del backend en BASE_URL.\n"
            "   b) Verifique que la respuesta HTTP es 2xx.\n"
            "   c) Verifique que el cuerpo de la respuesta contiene los campos esperados.\n"
            "3. Use una fixture `base_url` con el valor exacto BASE_URL.\n"
            "4. Si un endpoint requiere autenticación, primero haga login y use el token.\n"
            "5. Los tests deben ser independientes (no dependan del orden de ejecución).\n\n"
            "Solo el código Python del archivo de tests. Sin explicaciones, sin markdown."
        )

    def _summarize_endpoints(self, architecture: dict) -> str:
        lines: list[str] = []
        for mod in architecture.get("modulos", []):
            for ep in mod.get("endpoints", []):
                if isinstance(ep, dict):
                    method = ep.get("method", "GET").upper()
                    path = ep.get("path", "")
                    name = ep.get("name", "")
                    lines.append(f"{method} {path}  # {name}")
                elif isinstance(ep, str):
                    lines.append(ep)
        return "\n".join(lines) if lines else "(endpoints no declarados — inferilos del contexto)"

    @staticmethod
    def _strip_fence(code: str) -> str:
        lines = code.strip().splitlines()
        if not lines:
            return code
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)
