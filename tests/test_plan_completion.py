"""
Tests for plan completion items:
- skill_repository new language templates (Go, Rust, C#)
- WisdomAgent loop guard + fast exit
- SkillShAdapter (Fase 4)
- Orchestrator.get_project_status
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

for _mod in ("docker", "anthropic", "google.generativeai", "ollama",
             "telegram", "telegram.ext", "pywebview", "chromadb",
             "watchdog", "watchdog.observers", "watchdog.events",
             "github", "git"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills" / "base"


def run(coro):
    return asyncio.run(coro)


# ═══════════════════════════════════════════════════════════════════════════
# skill_repository new language templates
# ═══════════════════════════════════════════════════════════════════════════

class TestRepositoryTemplates:

    def _read(self, lang: str) -> str:
        return (SKILLS_DIR / "skill_repository" / "knowledge" / f"repository_{lang}.md").read_text(encoding="utf-8")

    # Go
    def test_go_template_exists(self):
        assert (SKILLS_DIR / "skill_repository" / "knowledge" / "repository_go.md").exists()

    def test_go_template_has_interface(self):
        content = self._read("go")
        assert "UserRepository" in content
        assert "interface" in content

    def test_go_template_has_concrete_impl(self):
        content = self._read("go")
        assert "SQLiteUserRepository" in content

    def test_go_template_has_dependency_injection(self):
        content = self._read("go")
        assert "func New" in content or "NewSQLite" in content

    # Rust
    def test_rust_template_exists(self):
        assert (SKILLS_DIR / "skill_repository" / "knowledge" / "repository_rust.md").exists()

    def test_rust_template_has_trait(self):
        content = self._read("rust")
        assert "trait UserRepository" in content
        assert "async_trait" in content

    def test_rust_template_has_sqlx_impl(self):
        content = self._read("rust")
        assert "SqliteUserRepository" in content
        assert "sqlx" in content

    # C#
    def test_csharp_template_exists(self):
        assert (SKILLS_DIR / "skill_repository" / "knowledge" / "repository_csharp.md").exists()

    def test_csharp_template_has_interface(self):
        content = self._read("csharp")
        assert "IUserRepository" in content
        assert "interface" in content

    def test_csharp_template_has_ef_impl(self):
        content = self._read("csharp")
        assert "EfUserRepository" in content or "DbContext" in content

    def test_csharp_template_has_di_pattern(self):
        content = self._read("csharp")
        assert "AddScoped" in content or "builder.Services" in content

    def test_skill_matcher_can_load_all_templates(self):
        from kernel.capabilities.skill_matcher import SkillMatcher
        matcher = SkillMatcher(None, None)
        ctx = matcher.load_skill_context(["skill_repository"], role="code_generator")
        # Primary skill → full load → system_prompt + first 2 knowledge files
        assert len(ctx) > 200


# ═══════════════════════════════════════════════════════════════════════════
# Wisdom loop guard + fast exit
# ═══════════════════════════════════════════════════════════════════════════

class TestWisdomLoopGuard:

    def _make_gemini_always_unclear(self):
        """Driver que siempre devuelve is_clear_enough=False."""
        import json
        driver = MagicMock()
        driver.call = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "is_clear_enough": False,
                "critical_questions": ["¿Más detalles?"]
            }),
            error_code=None
        ))
        return driver

    def test_loop_exits_after_max_iterations(self):
        """Loop siempre unclear → debe salir tras 5 iteraciones."""
        from kernel.orchestration.layer0_wisdom import resolve_ambiguities

        call_count = 0

        async def ask_fn(q):
            nonlocal call_count
            call_count += 1
            return "más detalles aquí"

        gemini = self._make_gemini_always_unclear()
        result = run(resolve_ambiguities(
            user_prompt="Quiero una app",
            gemini_driver=gemini,
            ask_user_fn=ask_fn,
        ))
        # Should have terminated and returned the enriched prompt
        assert isinstance(result, str)
        assert len(result) > len("Quiero una app")

    def test_skip_keyword_exits_immediately(self):
        """Responder 'skip' debe salir del loop sin más preguntas."""
        from kernel.orchestration.layer0_wisdom import resolve_ambiguities
        import json

        ask_calls = []

        async def ask_fn(q):
            ask_calls.append(q)
            return "skip"

        gemini = MagicMock()
        gemini.call = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "is_clear_enough": False,
                "critical_questions": ["¿Pregunta 1?", "¿Pregunta 2?", "¿Pregunta 3?"]
            }),
            error_code=None
        ))
        result = run(resolve_ambiguities(
            user_prompt="A" * 200,  # long enough to pass poor_prompt check
            gemini_driver=gemini,
            ask_user_fn=ask_fn,
        ))
        # After answering "skip" on the first question, loop exits
        assert len(ask_calls) == 1
        assert isinstance(result, str)

    def test_auto_decision_keyword_injects_freedom(self):
        """'carta libre' debe añadir instrucción de autonomía y retornar inmediatamente."""
        from kernel.orchestration.layer0_wisdom import resolve_ambiguities
        import json

        async def ask_fn(q):
            return "carta libre"

        gemini = MagicMock()
        gemini.call = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "is_clear_enough": False,
                "critical_questions": ["¿Pregunta?"]
            }),
            error_code=None
        ))
        result = run(resolve_ambiguities(
            user_prompt="A" * 200,
            gemini_driver=gemini,
            ask_user_fn=ask_fn,
        ))
        assert "carta libre" in result.lower() or "INSTRUCCIÓN DE AGILIDAD" in result

    def test_clear_prompt_exits_immediately(self):
        """Si Gemini dice is_clear_enough=True y el prompt es largo, sale en 1 iteración."""
        from kernel.orchestration.layer0_wisdom import resolve_ambiguities
        import json

        asked = []

        async def ask_fn(q):
            asked.append(q)
            return "respuesta"

        gemini = MagicMock()
        gemini.call = AsyncMock(return_value=MagicMock(
            content=json.dumps({"is_clear_enough": True, "critical_questions": []}),
            error_code=None
        ))
        result = run(resolve_ambiguities(
            user_prompt="A" * 200,
            gemini_driver=gemini,
            ask_user_fn=ask_fn,
        ))
        assert asked == []  # no questions asked
        assert result == "A" * 200

    def test_max_questions_per_batch_capped_at_five(self):
        """Aunque Gemini devuelva 7 preguntas, solo se hacen 5 + la de auto-decisión."""
        from kernel.orchestration.layer0_wisdom import resolve_ambiguities
        import json

        asked = []

        async def ask_fn(q):
            asked.append(q)
            return "respuesta"

        gemini = MagicMock()
        # Returns 7 questions — should be capped to 5 + 1 auto-decision
        gemini.call = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "is_clear_enough": False,
                "critical_questions": [f"¿Pregunta {i}?" for i in range(1, 8)]
            }),
            error_code=None
        ))
        # Make it clear on second evaluation to stop after 1 batch
        call_n = [0]
        async def smart_call(**kwargs):
            call_n[0] += 1
            if call_n[0] == 1:
                return MagicMock(content=json.dumps({
                    "is_clear_enough": False,
                    "critical_questions": [f"¿Pregunta {i}?" for i in range(1, 8)]
                }), error_code=None)
            return MagicMock(content=json.dumps({
                "is_clear_enough": True, "critical_questions": []
            }), error_code=None)

        gemini.call = smart_call
        result = run(resolve_ambiguities(
            user_prompt="A" * 200,
            gemini_driver=gemini,
            ask_user_fn=ask_fn,
        ))
        # 5 real questions + 1 auto-decision option = 6 max
        assert len(asked) <= 6


# ═══════════════════════════════════════════════════════════════════════════
# SkillShAdapter
# ═══════════════════════════════════════════════════════════════════════════

SAMPLE_SKILL_MD = """
# SKILL: Test Skill

## Description
A skill for testing the adapter pipeline with example code.

Keywords: test, example, demo

## Steps
1. Install the dependency
2. Import the module
3. Use the function

## Examples

```python
def hello(name: str) -> str:
    return f"Hello, {name}!"

result = hello("world")
print(result)
```

```python
class TestService:
    def run(self) -> None:
        print("running")
```
"""


class TestSkillShAdapter:

    def _adapter(self, tmp_path) -> object:
        from kernel.capabilities.skill_sh_adapter import SkillShAdapter
        return SkillShAdapter(community_dir=tmp_path / "community")

    def test_convert_from_text_creates_skill_dir(self, tmp_path):
        adapter = self._adapter(tmp_path)
        result = adapter.convert_from_text(SAMPLE_SKILL_MD, target_lang="python")
        assert result is not None
        assert result.is_dir()

    def test_manifest_yaml_created(self, tmp_path):
        adapter = self._adapter(tmp_path)
        skill_dir = adapter.convert_from_text(SAMPLE_SKILL_MD)
        assert (skill_dir / "manifest.yaml").exists()

    def test_system_prompt_created(self, tmp_path):
        adapter = self._adapter(tmp_path)
        skill_dir = adapter.convert_from_text(SAMPLE_SKILL_MD)
        assert (skill_dir / "system_prompt.md").exists()

    def test_knowledge_dir_created_with_examples(self, tmp_path):
        adapter = self._adapter(tmp_path)
        skill_dir = adapter.convert_from_text(SAMPLE_SKILL_MD)
        knowledge_files = list((skill_dir / "knowledge").glob("*.md"))
        assert len(knowledge_files) >= 1

    def test_knowledge_contains_code_examples(self, tmp_path):
        adapter = self._adapter(tmp_path)
        skill_dir = adapter.convert_from_text(SAMPLE_SKILL_MD)
        content = next((skill_dir / "knowledge").glob("*.md")).read_text()
        assert "hello" in content or "TestService" in content

    def test_manifest_has_activation_keywords(self, tmp_path):
        import yaml
        adapter = self._adapter(tmp_path)
        skill_dir = adapter.convert_from_text(SAMPLE_SKILL_MD)
        manifest = yaml.safe_load((skill_dir / "manifest.yaml").read_text())
        assert len(manifest.get("activation_keywords", [])) > 0

    def test_manifest_slug_starts_with_skill_(self, tmp_path):
        import yaml
        adapter = self._adapter(tmp_path)
        skill_dir = adapter.convert_from_text(SAMPLE_SKILL_MD)
        manifest = yaml.safe_load((skill_dir / "manifest.yaml").read_text())
        assert manifest["name"].startswith("skill_")

    def test_force_flag_overwrites_existing(self, tmp_path):
        adapter = self._adapter(tmp_path)
        skill_dir = adapter.convert_from_text(SAMPLE_SKILL_MD)
        # Write sentinel
        (skill_dir / "knowledge" / "sentinel.txt").write_text("original")
        # Re-convert with force
        adapter.convert_from_text(SAMPLE_SKILL_MD, force=True)
        # Sentinel should be gone (dir recreated)
        assert not (skill_dir / "knowledge" / "sentinel.txt").exists()

    def test_idempotent_without_force(self, tmp_path):
        adapter = self._adapter(tmp_path)
        first = adapter.convert_from_text(SAMPLE_SKILL_MD)
        (first / "knowledge" / "sentinel.txt").write_text("keep")
        second = adapter.convert_from_text(SAMPLE_SKILL_MD)  # no force
        assert first == second
        assert (first / "knowledge" / "sentinel.txt").exists()

    def test_empty_skill_returns_none(self, tmp_path):
        adapter = self._adapter(tmp_path)
        result = adapter.convert_from_text("")
        assert result is None

    def test_quality_validator_passes_good_skill(self, tmp_path):
        from kernel.capabilities.skill_sh_adapter import validate_community_skill
        adapter = self._adapter(tmp_path)
        skill_dir = adapter.convert_from_text(SAMPLE_SKILL_MD)
        report = validate_community_skill(skill_dir)
        assert report.has_examples
        assert report.has_keywords

    def test_quality_validator_flags_missing_manifest(self, tmp_path):
        from kernel.capabilities.skill_sh_adapter import validate_community_skill
        bad_dir = tmp_path / "skill_bad"
        bad_dir.mkdir()
        report = validate_community_skill(bad_dir)
        assert "missing manifest.yaml" in report.issues

    def test_skill_discoverable_by_skill_matcher(self, tmp_path):
        """A converted community skill is discovered by SkillMatcher."""
        from kernel.capabilities.skill_matcher import SkillMatcher

        adapter = self._adapter(tmp_path)
        skill_dir = adapter.convert_from_text(SAMPLE_SKILL_MD)

        # SkillMatcher globs */*/manifest.yaml from skills_dir root.
        # community skills live at community/{name}/manifest.yaml,
        # so we point at tmp_path (the parent of community/).
        matcher = SkillMatcher(None, None)
        matcher.skills_dir = tmp_path

        available = matcher._load_available_skills()
        assert any(s["name"].startswith("skill_") for s in available)
