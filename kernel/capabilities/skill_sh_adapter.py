"""
SkillShAdapter — Fase 4 del plan de evolución SODA.

Convierte skills del ecosistema skills.sh / Claude Code al formato SODA.

Skills externas (skills.sh):
  - Están en formato SKILL.md (instrucciones de comportamiento para Claude Code agents)
  - Contienen secciones: title, description, steps, examples

Skills SODA (skills/base/ o skills/community/):
  - manifest.yaml + system_prompt.md + knowledge/*.md
  - El coder recibe el knowledge como contexto técnico

El adapter extrae la sección técnica (examples, patterns, best practices)
y genera archivos compatibles con SODA en skills/community/{skill_name}/.

Uso:
    adapter = SkillShAdapter()
    path = await adapter.convert_from_url(
        "https://raw.githubusercontent.com/org/repo/main/SKILL.md",
        target_lang="typescript"
    )
    # → skills/community/skill_name/manifest.yaml + knowledge/
"""
from __future__ import annotations

import re
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


# ── Parsed representation of a skills.sh SKILL.md ────────────────────────────

@dataclass
class ExternalSkill:
    title: str
    description: str
    steps: list[str]
    examples: list[str]
    keywords: list[str]
    raw: str


# ── Adapter ───────────────────────────────────────────────────────────────────

class SkillShAdapter:
    """
    Downloads, parses, and converts a skills.sh SKILL.md to SODA format.

    The conversion strategy:
    1. Parse the external SKILL.md for structured sections
    2. Extract technical patterns from 'examples' and 'steps'
    3. Generate SODA-compatible manifest.yaml + system_prompt.md + knowledge/
    4. Save to skills/community/{slug}/

    Skills in skills/community/ are discovered by SkillMatcher and
    SkillDiscoveryAgent the same way as skills/base/ — no extra config needed.
    """

    COMMUNITY_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "community"

    # Section headers seen in skills.sh SKILL.md files
    _TITLE_RE = re.compile(r'^#\s+(.+)', re.MULTILINE)
    _DESC_RE = re.compile(r'^#+\s*(?:Description|Overview)\s*\n+(.*?)(?=\n#+|\Z)', re.DOTALL | re.MULTILINE | re.IGNORECASE)
    _STEPS_RE = re.compile(r'^#+\s*(?:Steps?|Instructions?|Usage)\s*\n+(.*?)(?=\n#+|\Z)', re.DOTALL | re.MULTILINE | re.IGNORECASE)
    _EXAMPLE_RE = re.compile(r'^#+\s*(?:Examples?|Sample|Demo)\s*\n+(.*?)(?=\n#+|\Z)', re.DOTALL | re.MULTILINE | re.IGNORECASE)
    _KEYWORD_RE = re.compile(r'(?:keywords?|tags?)\s*[:=]\s*(.+)', re.IGNORECASE)
    _CODE_BLOCK_RE = re.compile(r'```(?:\w+)?\n(.*?)```', re.DOTALL)

    def __init__(self, community_dir: Optional[Path] = None):
        self._community_dir = community_dir or self.COMMUNITY_DIR
        self._community_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────────

    async def convert_from_url(
        self,
        skill_md_url: str,
        target_lang: str = "python",
        force: bool = False,
    ) -> Optional[Path]:
        """
        Downloads a SKILL.md from a URL and converts it to SODA format.
        Returns the path to the created skill directory, or None on failure.
        """
        raw = self._fetch(skill_md_url)
        if not raw:
            return None
        return self.convert_from_text(raw, target_lang=target_lang, source_url=skill_md_url, force=force)

    def convert_from_text(
        self,
        skill_md_text: str,
        target_lang: str = "python",
        source_url: str = "",
        force: bool = False,
    ) -> Optional[Path]:
        """
        Converts a SKILL.md string to SODA format.
        Returns the path to the created skill directory, or None on failure.
        """
        parsed = self._parse(skill_md_text)
        if not parsed.title:
            return None

        slug = self._slugify(parsed.title)
        skill_dir = self._community_dir / slug

        if skill_dir.exists() and not force:
            return skill_dir  # already converted

        if skill_dir.exists() and force:
            import shutil
            shutil.rmtree(skill_dir)

        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "knowledge").mkdir(exist_ok=True)

        self._write_manifest(skill_dir, parsed, slug, source_url)
        self._write_system_prompt(skill_dir, parsed)
        self._write_knowledge(skill_dir, parsed, target_lang)

        return skill_dir

    # ── Parsing ───────────────────────────────────────────────────────────────

    def _parse(self, text: str) -> ExternalSkill:
        title = ""
        m = self._TITLE_RE.search(text)
        if m:
            title = m.group(1).strip()
            # Remove leading "SKILL:" prefix if present
            title = re.sub(r'^skill\s*[:–-]\s*', '', title, flags=re.IGNORECASE).strip()

        description = ""
        m = self._DESC_RE.search(text)
        if m:
            description = m.group(1).strip()

        steps: list[str] = []
        m = self._STEPS_RE.search(text)
        if m:
            block = m.group(1).strip()
            steps = [
                re.sub(r'^\d+\.\s*', '', line).strip()
                for line in block.splitlines()
                if line.strip() and not line.strip().startswith('#')
            ]

        examples: list[str] = []
        m = self._EXAMPLE_RE.search(text)
        if m:
            # Extract code blocks from the examples section
            examples = self._CODE_BLOCK_RE.findall(m.group(1))

        keywords: list[str] = []
        m = self._KEYWORD_RE.search(text)
        if m:
            keywords = [k.strip() for k in re.split(r'[,\s]+', m.group(1)) if k.strip()]

        # Fallback: extract keywords from title words
        if not keywords and title:
            keywords = [w.lower() for w in re.split(r'\W+', title) if len(w) > 2]

        return ExternalSkill(
            title=title,
            description=description or f"Community skill: {title}",
            steps=steps,
            examples=examples,
            keywords=keywords,
            raw=text,
        )

    # ── Writers ───────────────────────────────────────────────────────────────

    def _write_manifest(self, skill_dir: Path, skill: ExternalSkill, slug: str, source_url: str) -> None:
        data = {
            "name": slug,
            "category": "community",
            "description": skill.description[:120],
            "source": source_url or "manual",
            "applies_to_roles": {
                "code_generator": {"load_level": "full"},
                "global_architect": {"load_level": "summary"},
            },
            "activation_keywords": skill.keywords[:15],
            "version": "community-1.0",
        }
        (skill_dir / "manifest.yaml").write_text(
            yaml.dump(data, allow_unicode=True, default_flow_style=False),
            encoding="utf-8"
        )

    def _write_system_prompt(self, skill_dir: Path, skill: ExternalSkill) -> None:
        lines = [f"## Skill: {skill.title}", "", skill.description, ""]
        if skill.steps:
            lines.append("### Key Steps")
            for i, step in enumerate(skill.steps[:10], 1):
                if step:
                    lines.append(f"{i}. {step}")
            lines.append("")
        (skill_dir / "system_prompt.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_knowledge(self, skill_dir: Path, skill: ExternalSkill, lang: str) -> None:
        if not skill.examples:
            # No code examples found — write a minimal reference file
            content = f"## {skill.title} — Reference\n\n{skill.description}\n"
            if skill.steps:
                content += "\n### Steps\n" + "\n".join(f"- {s}" for s in skill.steps)
            (skill_dir / "knowledge" / "reference.md").write_text(content, encoding="utf-8")
            return

        lines = [f"## {skill.title} — Code Examples ({lang})", ""]
        for i, example in enumerate(skill.examples[:5], 1):
            lines.append(f"### Example {i}")
            lines.append(f"```{lang}")
            lines.append(example.strip())
            lines.append("```")
            lines.append("")

        (skill_dir / "knowledge" / f"examples_{lang}.md").write_text(
            "\n".join(lines), encoding="utf-8"
        )

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _slugify(title: str) -> str:
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[\s-]+', '_', slug).strip('_')
        if not slug.startswith('skill_'):
            slug = f"skill_{slug}"
        return slug[:60]

    @staticmethod
    def _fetch(url: str, timeout: int = 10) -> Optional[str]:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.URLError, OSError):
            return None


# ── Quality validator ─────────────────────────────────────────────────────────

@dataclass
class SkillQualityReport:
    slug: str
    has_examples: bool
    has_keywords: bool
    description_length: int
    issues: list[str]

    @property
    def is_acceptable(self) -> bool:
        return len(self.issues) == 0


def validate_community_skill(skill_dir: Path) -> SkillQualityReport:
    """
    Basic quality check for a converted community skill.
    Used before injecting it into a project context.
    """
    issues: list[str] = []
    manifest_path = skill_dir / "manifest.yaml"
    sp_path = skill_dir / "system_prompt.md"
    knowledge_dir = skill_dir / "knowledge"

    if not manifest_path.exists():
        issues.append("missing manifest.yaml")
        return SkillQualityReport(skill_dir.name, False, False, 0, issues)

    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    keywords = data.get("activation_keywords", [])
    description = data.get("description", "")

    if not keywords:
        issues.append("no activation_keywords — skill will never be auto-detected")
    if len(description) < 20:
        issues.append("description too short")
    if not sp_path.exists():
        issues.append("missing system_prompt.md")

    knowledge_files = list(knowledge_dir.glob("*.md")) if knowledge_dir.exists() else []
    has_examples = any(
        "```" in f.read_text(encoding="utf-8")
        for f in knowledge_files
    )
    if not has_examples:
        issues.append("no code examples in knowledge/ — skill provides little value to coder")

    return SkillQualityReport(
        slug=skill_dir.name,
        has_examples=has_examples,
        has_keywords=bool(keywords),
        description_length=len(description),
        issues=issues,
    )
