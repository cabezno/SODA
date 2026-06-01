"""
Deep analysis of an existing project folder.
Reads code files, calls AI for structured understanding:
  - Purpose and domain
  - Tech stack and architecture
  - Code quality issues
  - Missing features / bugs
  - Actionable suggestions
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional


# Extensions to read; skip binaries, lock files, etc.
_READ_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cs", ".cpp", ".c", ".h",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".r",
    ".html", ".css", ".scss", ".sass",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".env.example",
    ".sql", ".sh", ".bat", ".ps1", ".md", ".txt", ".cfg",
}
_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "target", "bin", "obj",
    ".idea", ".vscode", "migrations", ".mypy_cache", ".pytest_cache",
}
_MAX_FILE_BYTES = 8_000    # per file
_MAX_TOTAL_BYTES = 80_000  # total context budget


def collect_project_files(root: Path) -> dict[str, str]:
    """Walk a directory and return {relative_path: content} for readable files."""
    files: dict[str, str] = {}
    total = 0
    for path in sorted(root.rglob("*")):
        if any(skip in path.parts for skip in _SKIP_DIRS):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in _READ_EXTS:
            continue
        try:
            raw = path.read_bytes()[:_MAX_FILE_BYTES]
            text = raw.decode("utf-8", errors="replace")
            rel = str(path.relative_to(root)).replace("\\", "/")
            files[rel] = text
            total += len(text)
            if total > _MAX_TOTAL_BYTES:
                break
        except Exception:
            continue
    return files


def build_analysis_prompt(files: dict[str, str], extra_context: str = "") -> str:
    tree = "\n".join(f"  {k}" for k in sorted(files.keys()))
    snippets = []
    for rel, content in list(files.items())[:30]:
        lines = content.splitlines()[:60]
        snippets.append(f"### {rel}\n```\n" + "\n".join(lines) + "\n```")
    code_block = "\n\n".join(snippets)
    extra = f"\nContexto adicional del usuario: {extra_context}\n" if extra_context else ""

    return f"""Analizá este proyecto de software con profundidad y devolvé un JSON estructurado.

ÁRBOL DE ARCHIVOS:
{tree}

{extra}
CÓDIGO FUENTE (extractos):
{code_block}

Respondé SOLO con este JSON exacto (sin texto adicional):
{{
  "purpose": "qué hace este proyecto (1-2 oraciones claras)",
  "domain": "categoría: web_app | api | cli | library | mobile | desktop | data | other",
  "stack": {{
    "language": "lenguaje principal",
    "framework": "framework principal o vacío",
    "database": "base de datos detectada o vacío",
    "other": ["otras tecnologías relevantes"]
  }},
  "architecture": "descripción breve de la arquitectura (MVC, microservicios, monolito, etc.)",
  "entry_points": ["archivos de entrada principales"],
  "run_command": "comando para ejecutar (vacío si no detectado)",
  "install_command": "comando para instalar dependencias (vacío si no detectado)",
  "quality": {{
    "score": 1-10,
    "strengths": ["puntos fuertes del código"],
    "issues": ["problemas detectados con descripción concreta"],
    "missing": ["qué falta o es incompleto"]
  }},
  "suggested_actions": [
    {{"id": "fix_bugs", "label": "Corregir bugs detectados", "description": "descripción de los bugs", "priority": "high|medium|low"}},
    {{"id": "refactor", "label": "Refactorizar y mejorar", "description": "qué mejorar", "priority": "medium"}},
    {{"id": "add_tests", "label": "Añadir tests", "description": "qué testear", "priority": "medium"}},
    {{"id": "add_docs", "label": "Documentar código", "description": "qué documentar", "priority": "low"}},
    {{"id": "add_feature", "label": "Añadir funcionalidad", "description": "sugerencias de features", "priority": "medium"}},
    {{"id": "migrate_language", "label": "Migrar a otro lenguaje", "description": "opciones de migración recomendadas", "priority": "low"}},
    {{"id": "run_and_test", "label": "Ejecutar y probar", "description": "ejecutar el proyecto y verificar que funciona", "priority": "high"}}
  ],
  "migration_targets": ["lenguajes recomendados para migrar, si aplica"],
  "complexity": "low|medium|high",
  "estimated_effort": "descripción del esfuerzo para mejorar/completar",
  "questions": [
    {{"id": "q1", "question": "pregunta específica basada en los problemas detectados", "type": "choice", "options": ["opción A", "opción B", "opción C", "Decidir automáticamente"]}},
    {{"id": "q2", "question": "otra pregunta concreta sobre prioridades o alcance", "type": "choice", "options": ["opción A", "opción B", "Decidir automáticamente"]}}
  ]
}}

REGLAS PARA "questions":
- Generá entre 2 y 5 preguntas CONCRETAS basadas en los problemas reales que encontraste en ESTE proyecto.
- NO hagas preguntas genéricas. Cada pregunta debe referenciar algo específico del código analizado.
- Ejemplos buenos: "El módulo auth.py no tiene validación de tokens expirados. ¿Querés que SODA lo corrija automáticamente o lo revisás vos?", "Detecté 3 funciones duplicadas entre utils.py y helpers.py. ¿Las consolidamos en un módulo compartido?"
- Siempre incluí "Decidir automáticamente" como última opción para que el usuario pueda delegar.
- Si el proyecto está bien y no hay problemas claros, podés devolver "questions": []"""


async def analyze_project(
    root: Path,
    extra_context: str = "",
    prefer_gemini: bool = True,
) -> dict:
    """Run full project analysis using AI. Returns the structured analysis dict."""
    files = collect_project_files(root)
    if not files:
        return {
            "purpose": "No se encontraron archivos de código",
            "domain": "other", "stack": {}, "quality": {"score": 0, "issues": ["Sin archivos"]},
            "suggested_actions": [], "migration_targets": [], "entry_points": [],
            "run_command": "", "install_command": "", "complexity": "low",
        }

    prompt = build_analysis_prompt(files, extra_context)
    system = (
        "Sos un senior software architect. Analizás proyectos de software con precisión técnica. "
        "Respondés SOLO con JSON válido, sin markdown, sin texto adicional."
    )

    raw = ""
    try:
        if prefer_gemini:
            from kernel.drivers.gemini_driver import GeminiDriver
            raw = await GeminiDriver().prompt(system, prompt)
        else:
            raise RuntimeError("skip")
    except Exception:
        try:
            from kernel.drivers.gemini_driver import GeminiDriver
            raw = await GeminiDriver().prompt(system, prompt)
        except Exception as e2:
            return {"error": str(e2), "purpose": "Error al analizar", "suggested_actions": []}

    # Extract JSON
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            result = json.loads(match.group())
            result["_files"] = list(files.keys())
            result["_file_count"] = len(files)
            return result
        except json.JSONDecodeError:
            pass

    return {"purpose": raw[:400], "suggested_actions": [], "_files": list(files.keys())}
