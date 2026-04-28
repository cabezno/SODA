from __future__ import annotations

import hashlib
from pathlib import Path

# Extensions that use // line comments
_SLASH_COMMENT_EXTS = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".svelte", ".vue"}
# Extensions that use /* */ block comments
_BLOCK_COMMENT_EXTS = {".css", ".scss", ".sass", ".less"}
# Extensions where injecting any comment is unsafe (leave as-is)
_NO_COMMENT_EXTS = {".json", ".jsonc", ".html", ".xml", ".yaml", ".yml", ".toml", ".md"}


def _comment_style(filepath: str) -> str:
    """Return 'hash', 'slash', 'block', or 'none' based on file extension."""
    ext = Path(filepath).suffix.lower()
    if ext in _SLASH_COMMENT_EXTS:
        return "slash"
    if ext in _BLOCK_COMMENT_EXTS:
        return "block"
    if ext in _NO_COMMENT_EXTS:
        return "none"
    return "hash"  # Python, shell, Ruby, etc.


class MetadataInjector:
    def build_header(self, goal_id: str, goal_hash: str | None = None, filepath: str = "") -> str:
        goal_hash = goal_hash or hashlib.sha256(goal_id.encode("utf-8")).hexdigest()[:16]
        style = _comment_style(filepath)

        if style == "slash":
            return (
                "// --- METADATA SODA ---\n"
                f"// goal_id: {goal_id}\n"
                f"// goal_hash: {goal_hash}\n"
                "// --- FIN METADATA ---"
            )
        if style == "block":
            return (
                "/* --- METADATA SODA ---\n"
                f" * goal_id: {goal_id}\n"
                f" * goal_hash: {goal_hash}\n"
                " * --- FIN METADATA --- */"
            )
        if style == "none":
            return ""  # never inject into JSON/HTML/YAML

        # hash style (Python, shell, etc.)
        return (
            "# --- METADATA SODA ---\n"
            f"# goal_id: {goal_id}\n"
            f"# goal_hash: {goal_hash}\n"
            "# --- FIN METADATA ---"
        )

    def strip_misplaced_metadata(self, content: str, filepath: str) -> str:
        """Remove SODA metadata blocks from non-Python files where they break syntax.

        Handles both the pure `# ---` form and the mixed `// --- / # inner / // ---` form
        that models sometimes generate for JS/TS files.
        """
        style = _comment_style(filepath)
        if style in ("hash", "none"):
            return content  # Python/shell: keep; JSON/HTML: no metadata anyway

        _OPENERS = (
            "# --- METADATA SODA ---",
            "# --- METADATA SODA (no editar manualmente) ---",
            "// --- METADATA SODA ---",
            "// --- METADATA SODA (no editar manualmente) ---",
        )
        _CLOSERS = ("# --- FIN METADATA ---", "// --- FIN METADATA ---")

        lines = content.splitlines()
        cleaned = []
        in_block = False
        for line in lines:
            stripped = line.strip()
            if stripped in _OPENERS:
                in_block = True
                continue
            if in_block:
                if stripped in _CLOSERS:
                    in_block = False
                continue
            cleaned.append(line)
        return "\n".join(cleaned).lstrip("\n") + ("\n" if cleaned else "")

    def ensure_metadata(self, content: str, goal_id: str, goal_hash: str | None = None, filepath: str = "") -> str:
        normalized = (content or "").lstrip("\ufeff")

        style = _comment_style(filepath)
        if style == "none":
            return normalized  # never modify JSON/HTML/YAML

        # Already has metadata — skip regardless of comment style
        for marker in ("# --- METADATA SODA", "// --- METADATA SODA", "/* --- METADATA SODA"):
            if marker in normalized:
                return normalized

        lines = normalized.splitlines()
        prefix = []
        # Preserve shebang and coding declarations (Python/shell only)
        if style == "hash":
            while lines and (lines[0].startswith("#!") or lines[0].startswith("# -*- coding:")):
                prefix.append(lines.pop(0))

        body = "\n".join(lines).lstrip("\n")
        header = self.build_header(goal_id, goal_hash, filepath)

        parts = []
        if prefix:
            parts.append("\n".join(prefix))
        if header:
            parts.append(header)
        if body:
            parts.append(body)
        return "\n\n".join(parts).rstrip() + "\n"
