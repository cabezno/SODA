"""TemplateInjector — copies validated scaffold templates into source_dir before AI generation.

Flow:
  1. find_best_template(blueprint)  — score all templates by stack match
  2. validate(template_dir)         — confirm it has usable files
  3. inject(template_dir, source_dir) — copy files, write manifest
  4. save_as_template(...)          — after DEV, persist infra files as new template

The manifest (_soda_injected.json) lets generate_file skip template-provided files.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Optional

# Files that contain only infrastructure — safe to save as templates.
# These don't carry business logic so they're reusable across similar projects.
INFRA_FILES: frozenset[str] = frozenset({
    "package.json", "package-lock.json",
    "Dockerfile", "dockerfile",
    "docker-compose.yml", "docker-compose.yaml",
    "go.mod", "go.sum",
    "requirements.txt", "requirements-dev.txt", "pyproject.toml",
    "tsconfig.json", "tsconfig.node.json",
    "vite.config.ts", "vite.config.js",
    "tailwind.config.ts", "tailwind.config.js", "postcss.config.js",
    "CMakeLists.txt", "pom.xml", "build.gradle", "Cargo.toml",
    ".env.example", ".gitignore", "README.md",
    "jest.config.ts", "jest.config.js", "vitest.config.ts",
})

_MANIFEST_NAME = "_soda_injected.json"


def _stack_text(blueprint: dict) -> str:
    stack = blueprint.get("stack_sugerido", {})
    return " ".join(str(v).lower() for v in stack.values() if v)


def _score_template(template_dir: Path, stack_text: str) -> int:
    """Return a match score (0 = no match) between a template dir and project stack."""
    dir_str = str(template_dir).lower().replace("\\", "/")
    # Extract the last 2 path segments as the identifier (e.g. "fullstack/fastapi-react")
    parts = dir_str.split("/")
    identifier = " ".join(parts[-2:]) if len(parts) >= 2 else dir_str

    score = 0
    stack_words = set(re.split(r"[\s\-_/\.]+", stack_text))
    id_words = set(re.split(r"[\s\-_/\.]+", identifier))

    for word in stack_words:
        if len(word) < 2:
            continue
        if word in id_words:
            score += 3           # exact word match in dir name
        elif any(word in iw for iw in id_words):
            score += 1           # substring match
    return score


def _validate_template(template_dir: Path) -> tuple[bool, str]:
    """Return (is_valid, reason). Valid = has at least one file with meaningful content."""
    if not template_dir.is_dir():
        return False, "directorio no existe"
    files = [f for f in template_dir.rglob("*") if f.is_file() and f.stat().st_size > 10]
    if not files:
        return False, "sin archivos utiles"
    return True, f"{len(files)} archivo(s) encontrado(s)"


def _stack_slug(blueprint: dict) -> str:
    """Build a filesystem-safe slug from the project stack."""
    stack = blueprint.get("stack_sugerido", {})
    parts = []
    for key in ("backend", "frontend", "database"):
        val = str(stack.get(key, "")).lower().strip()
        if val and val not in ("none", "n/a", ""):
            slug = re.sub(r"[^a-z0-9]", "", val)[:10]
            if slug and slug not in parts:
                parts.append(slug)
    return "-".join(parts[:3]) or "generic"


class TemplateInjector:
    def __init__(self, templates_dir: Path):
        self.templates_dir = Path(templates_dir)

    # ------------------------------------------------------------------ #
    # 1. Find                                                              #
    # ------------------------------------------------------------------ #

    def find_best_template(self, blueprint: dict) -> Optional[Path]:
        """Return the highest-scoring template directory, or None if nothing matches."""
        if not self.templates_dir.is_dir():
            return None

        stack_txt = _stack_text(blueprint)
        if not stack_txt.strip():
            return None

        candidates: list[tuple[int, Path]] = []
        for entry in self.templates_dir.rglob("*"):
            if not entry.is_dir():
                continue
            # Skip meta directories (e.g. directories that only contain a .README.md)
            files = [f for f in entry.iterdir() if f.is_file() and not f.name.startswith(".")]
            subdirs = [d for d in entry.iterdir() if d.is_dir()]
            if not files and not subdirs:
                continue
            score = _score_template(entry, stack_txt)
            if score > 0:
                candidates.append((score, entry))

        if not candidates:
            return None

        # Take highest-scoring; prefer deeper paths (more specific templates)
        candidates.sort(key=lambda x: (x[0], len(x[1].parts)), reverse=True)
        return candidates[0][1]

    # ------------------------------------------------------------------ #
    # 2. Validate                                                          #
    # ------------------------------------------------------------------ #

    def validate(self, template_dir: Path) -> tuple[bool, str]:
        return _validate_template(template_dir)

    # ------------------------------------------------------------------ #
    # 3. Inject                                                            #
    # ------------------------------------------------------------------ #

    def inject(self, template_dir: Path, source_dir: Path) -> list[str]:
        """Copy template files into source_dir (skip existing). Returns relative paths copied."""
        copied: list[str] = []
        for src in template_dir.rglob("*"):
            if not src.is_file():
                continue
            if src.name.startswith(".README") or src.name == _MANIFEST_NAME:
                continue
            rel = src.relative_to(template_dir)
            dst = source_dir / rel
            if dst.exists():
                continue  # never overwrite — generated content wins
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(str(rel).replace("\\", "/"))

        if copied:
            manifest = source_dir / _MANIFEST_NAME
            manifest.write_text(
                json.dumps({"injected": copied, "template": str(template_dir)}, indent=2),
                encoding="utf-8",
            )
        return copied

    # ------------------------------------------------------------------ #
    # 4. Save as template                                                  #
    # ------------------------------------------------------------------ #

    def save_as_template(
        self,
        source_dir: Path,
        blueprint: dict,
        category: str = "fullstack",
    ) -> Optional[Path]:
        """Persist infra files from source_dir as a new template for future projects."""
        slug = _stack_slug(blueprint)
        template_dir = self.templates_dir / category / slug
        if template_dir.exists():
            return None  # template already exists, don't overwrite

        saved: list[Path] = []
        for f in source_dir.rglob("*"):
            if not f.is_file():
                continue
            if f.name in INFRA_FILES:
                rel = f.relative_to(source_dir)
                dst = template_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
                saved.append(dst)

        if not saved:
            return None

        # Write a README for the new template
        (template_dir / "README.md").write_text(
            f"# Template: {slug}\n\nGenerado automáticamente por SODA.\n"
            f"Stack: {_stack_text(blueprint)}\n",
            encoding="utf-8",
        )
        print(f"  [template] Plantilla guardada: {template_dir} ({len(saved)} archivo(s))")
        return template_dir

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def load_manifest(source_dir: Path) -> set[str]:
        """Return set of filepaths that were injected from a template (for skip logic)."""
        manifest = source_dir / _MANIFEST_NAME
        if not manifest.exists():
            return set()
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            return set(data.get("injected", []))
        except Exception:
            return set()
