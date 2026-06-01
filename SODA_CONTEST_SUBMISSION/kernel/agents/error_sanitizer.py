"""error_sanitizer — strips noise from runtime stack traces before sending to LLMs."""
from __future__ import annotations

import re
from pathlib import Path

# Lines containing these strings are third-party internals — skip them
_NOISE_MARKERS = (
    "node_modules",
    "site-packages",
    "at internal/",
    "at node:internal",
    "at processTicksAndRejections",
    "at async Promise.all",
    "(__pycache__",
    "Traceback (most recent",   # keep the header line itself via special handling
)

# File-reference patterns: extract paths that point to user code
_FILE_REF_RE = re.compile(
    r'(?:at\s+\S+\s+\()?'           # optional "at Foo.bar ("
    r'((?:src|app|lib|pages|routes|components|api|utils|hooks|services|'
    r'models|controllers|middleware|config|test|tests|'
    r'[\w\-]+(?:/[\w\-\.]+)+)'       # directory/file paths
    r'\.(?:ts|tsx|js|jsx|py|go|java|cs|rb|php|rs|swift)'
    r'(?::\d+(?::\d+)?)?)'           # optional :line:col
    r'\)?',
    re.IGNORECASE,
)


def sanitize_runtime_error(raw_stderr: str, workspace_path: str | Path) -> str:
    """Filter a raw runtime stack trace down to what matters for an LLM fixer.

    Steps:
    1. Take only the last 2 000 characters (fatal errors are at the end).
    2. Strip absolute workspace paths so the LLM sees relative paths.
    3. Remove lines that reference node_modules, site-packages, or Node internals.
    4. Collapse consecutive blank lines.
    """
    # 1. Take the tail — errors accumulate at the end of stderr
    tail = raw_stderr[-2000:]

    # 2. Remove workspace absolute prefix so paths become project-relative
    ws = str(workspace_path).rstrip("/\\")
    # Normalize both forward and backward slashes
    for sep in ("/", "\\"):
        tail = tail.replace(ws + sep, "")
    # Also try just the basename in case the path was already relative-ish
    tail = tail.replace(ws, "")

    # 3. Filter out library-internal lines
    clean_lines: list[str] = []
    for line in tail.splitlines():
        if any(marker in line for marker in _NOISE_MARKERS):
            continue
        clean_lines.append(line)

    # 4. Collapse runs of blank lines into a single blank
    result_lines: list[str] = []
    prev_blank = False
    for line in clean_lines:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        result_lines.append(line)
        prev_blank = is_blank

    return "\n".join(result_lines).strip()


def extract_files_from_error(clean_error: str) -> list[str]:
    """Return a deduplicated list of source file paths mentioned in the sanitized error."""
    seen: set[str] = set()
    files: list[str] = []
    for match in _FILE_REF_RE.finditer(clean_error):
        # Strip line:col suffix so we get a clean path
        raw = match.group(1)
        path = re.sub(r':\d+(?::\d+)?$', '', raw).strip()
        if path and path not in seen:
            seen.add(path)
            files.append(path)
    return files
