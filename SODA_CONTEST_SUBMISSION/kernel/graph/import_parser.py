"""Import parser — builds a file-level dependency graph from generated source code.

Supports Python (ast-based) and JS/TS (regex-based).
Returns nodes + edges suitable for Cytoscape.js rendering.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path


_JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?\s+from\s+['"](\.[^'"]+)['"]|require\s*\(\s*['"](\.[^'"]+)['"]\s*\))""",
    re.MULTILINE,
)

_LANG_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".jsx": "javascript", ".tsx": "typescript", ".css": "css",
    ".html": "html", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".md": "markdown", ".sh": "shell", ".txt": "plaintext",
}

_PARSE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx"}


@dataclass
class GraphData:
    nodes: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)


def parse_project_graph(source_dir: Path) -> GraphData:
    """Parse all source files and return nodes + import edges."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    seen_edges: set[tuple[str, str]] = set()

    # Collect all files as nodes
    for fpath in sorted(source_dir.rglob("*")):
        if not fpath.is_file():
            continue
        rel = fpath.relative_to(source_dir).as_posix()
        ext = fpath.suffix.lower()
        nodes[rel] = {
            "id": rel,
            "label": fpath.name,
            "type": _LANG_MAP.get(ext, "plaintext"),
            "path": rel,
            "size": fpath.stat().st_size,
        }

    # Parse imports for each parseable file
    for rel, node_data in list(nodes.items()):
        fpath = source_dir / rel
        ext = fpath.suffix.lower()
        if ext not in _PARSE_EXTS:
            continue
        try:
            source = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if ext == ".py":
            _parse_python(source, rel, source_dir, nodes, edges, seen_edges)
        else:
            _parse_js(source, rel, fpath, source_dir, nodes, edges, seen_edges)

    return GraphData(nodes=list(nodes.values()), edges=edges)


def _parse_python(
    source: str, rel: str, source_dir: Path,
    nodes: dict, edges: list, seen: set,
) -> None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _add_python_edge(alias.name, rel, source_dir, nodes, edges, seen)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _add_python_edge(node.module, rel, source_dir, nodes, edges, seen)


def _add_python_edge(
    module: str, src_rel: str, source_dir: Path,
    nodes: dict, edges: list, seen: set,
) -> None:
    candidates = [
        module.replace(".", "/") + ".py",
        module.replace(".", "/") + "/__init__.py",
    ]
    for cand in candidates:
        if cand in nodes and (src_rel, cand) not in seen:
            seen.add((src_rel, cand))
            edges.append({"source": src_rel, "target": cand, "type": "import"})
            return


def _parse_js(
    source: str, rel: str, fpath: Path, source_dir: Path,
    nodes: dict, edges: list, seen: set,
) -> None:
    for m in _JS_IMPORT_RE.finditer(source):
        imp = m.group(1) or m.group(2)
        if not imp:
            continue
        base = fpath.parent
        resolved = (base / imp).resolve()
        for ext in ("", ".js", ".ts", ".jsx", ".tsx", "/index.js", "/index.ts"):
            candidate = Path(str(resolved) + ext)
            try:
                crel = candidate.relative_to(source_dir).as_posix()
                if crel in nodes and (rel, crel) not in seen:
                    seen.add((rel, crel))
                    edges.append({"source": rel, "target": crel, "type": "import"})
                    break
            except ValueError:
                continue


def module_graph_from_architecture(architecture: dict) -> GraphData:
    """Build module-level graph from architecture.json data."""
    modules = architecture.get("modulos", [])
    nodes = [
        {
            "id": m["nombre"],
            "label": m["nombre"],
            "type": "module",
            "path": None,
            "files": len(m.get("archivos_principales", [])),
        }
        for m in modules
    ]
    edges = []
    seen: set[tuple[str, str]] = set()
    module_names = {m["nombre"] for m in modules}
    for m in modules:
        for dep in (m.get("dependencias") or []):
            if dep in module_names and (m["nombre"], dep) not in seen:
                seen.add((m["nombre"], dep))
                edges.append({"source": m["nombre"], "target": dep, "type": "depends"})
    return GraphData(nodes=nodes, edges=edges)
