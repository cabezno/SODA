"""Tests for MetadataInjector — extension-aware comment styles and sanitization."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kernel.goals.metadata_injector import MetadataInjector


@pytest.fixture
def inj():
    return MetadataInjector()


# ── build_header ────────────────────────────────────────────────────────────

def test_python_header_uses_hash(inj):
    h = inj.build_header("my_goal", "abc123", "main.py")
    assert h.startswith("# --- METADATA SODA ---")
    assert "# goal_id: my_goal" in h

def test_js_header_uses_slash(inj):
    h = inj.build_header("g", "h", "app.js")
    assert h.startswith("// --- METADATA SODA ---")
    assert "// goal_id: g" in h

def test_ts_header_uses_slash(inj):
    h = inj.build_header("g", "h", "component.tsx")
    assert "// goal_id" in h

def test_mjs_header_uses_slash(inj):
    h = inj.build_header("g", "h", "next.config.mjs")
    assert "// goal_id" in h

def test_css_header_uses_block(inj):
    h = inj.build_header("g", "h", "styles.css")
    assert h.startswith("/* --- METADATA SODA ---")

def test_json_header_is_empty(inj):
    h = inj.build_header("g", "h", "package.json")
    assert h == ""

def test_yaml_header_is_empty(inj):
    h = inj.build_header("g", "h", "docker-compose.yml")
    assert h == ""


# ── ensure_metadata ──────────────────────────────────────────────────────────

def test_ensure_adds_hash_to_python(inj):
    result = inj.ensure_metadata("print('hi')", "gid", "ghash", "main.py")
    assert "# --- METADATA SODA ---" in result
    assert "print('hi')" in result

def test_ensure_adds_slash_to_ts(inj):
    result = inj.ensure_metadata("export const x = 1;", "gid", "ghash", "index.ts")
    assert "// --- METADATA SODA ---" in result
    assert "export const x = 1;" in result

def test_ensure_skips_json(inj):
    content = '{"name": "app"}'
    result = inj.ensure_metadata(content, "gid", "ghash", "package.json")
    assert result == content

def test_ensure_skips_if_already_has_slash_metadata(inj):
    content = "// --- METADATA SODA ---\n// goal_id: x\n// --- FIN METADATA ---\ncode"
    result = inj.ensure_metadata(content, "gid", "ghash", "app.ts")
    assert result.count("METADATA SODA") == 1

def test_ensure_skips_if_already_has_hash_metadata(inj):
    content = "# --- METADATA SODA ---\n# goal_id: x\n# --- FIN METADATA ---\ncode"
    result = inj.ensure_metadata(content, "gid", "ghash", "main.py")
    assert result.count("METADATA SODA") == 1


# ── strip_misplaced_metadata ─────────────────────────────────────────────────

def test_strip_removes_hash_block_from_ts(inj):
    content = (
        "# --- METADATA SODA ---\n"
        "# goal_id: foo\n"
        "# goal_hash: bar\n"
        "# --- FIN METADATA ---\n"
        "export const x = 1;\n"
    )
    result = inj.strip_misplaced_metadata(content, "index.ts")
    assert "# goal_id" not in result
    assert "export const x = 1;" in result

def test_strip_removes_long_form_from_mjs(inj):
    content = (
        "// --- METADATA SODA (no editar manualmente) ---\n"
        "# goal_id: foo\n"
        "# goal_path: x\n"
        "# generated: 2025\n"
        "# goal_hash: bar\n"
        "// --- FIN METADATA ---\n"
        "const cfg = {};\n"
    )
    result = inj.strip_misplaced_metadata(content, "next.config.mjs")
    assert "# goal_id" not in result
    assert "const cfg = {};" in result

def test_strip_leaves_python_untouched(inj):
    content = (
        "# --- METADATA SODA ---\n"
        "# goal_id: foo\n"
        "# --- FIN METADATA ---\n"
        "x = 1\n"
    )
    result = inj.strip_misplaced_metadata(content, "main.py")
    assert result == content

def test_strip_leaves_json_untouched(inj):
    content = '{"a": 1}'
    result = inj.strip_misplaced_metadata(content, "data.json")
    assert result == content

def test_strip_noop_when_no_metadata(inj):
    content = "export default function App() { return null; }\n"
    result = inj.strip_misplaced_metadata(content, "App.tsx")
    assert result == content
