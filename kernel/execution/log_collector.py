"""LogCollector — discovers and reads runtime logs from installed tools on Windows.

Supports: npm, yarn, node, python/pip, uvicorn, fastapi, postgres, redis,
          nginx, IIS, dotnet, go, rust/cargo, java/maven, and any *.log
          file inside the project workspace.
"""
from __future__ import annotations

import glob
import os
import time
from pathlib import Path
from typing import Optional

_LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", "C:/Users/Default/AppData/Local"))
_APPDATA      = Path(os.environ.get("APPDATA",      "C:/Users/Default/AppData/Roaming"))
_PROGRAMFILES = Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
_TEMP         = Path(os.environ.get("TEMP", "C:/Temp"))

# ── Known system log directories per stack / tool ─────────────────────────────
#
# Values are glob-expandable path strings so wildcards like * work.

_SYSTEM_LOG_DIRS: dict[str, list[str]] = {
    "npm": [
        str(_LOCALAPPDATA / "npm-cache" / "_logs"),
    ],
    "yarn": [
        str(_LOCALAPPDATA / "Yarn" / "log"),
        str(_APPDATA / "yarn" / "log"),
    ],
    "node": [
        str(_LOCALAPPDATA / "npm-cache" / "_logs"),
        str(_LOCALAPPDATA / "node" / "logs"),
    ],
    "python": [
        str(_LOCALAPPDATA / "pip" / "log"),
        str(_TEMP),                          # pip sometimes writes here
    ],
    "postgres": [
        str(_PROGRAMFILES / "PostgreSQL" / "*" / "data" / "log"),
        str(_PROGRAMFILES / "PostgreSQL" / "*" / "data" / "pg_log"),
        "C:/PostgreSQL/*/data/log",
    ],
    "redis": [
        str(_PROGRAMFILES / "Redis"),
        "C:/Redis",
    ],
    "nginx": [
        "C:/nginx/logs",
        str(_PROGRAMFILES / "nginx" / "logs"),
    ],
    "iis": [
        "C:/inetpub/logs/LogFiles",
    ],
    "dotnet": [
        str(_LOCALAPPDATA / "Temp"),
    ],
    "go": [
        str(_LOCALAPPDATA / "go" / "log"),
    ],
    "rust": [
        str(_LOCALAPPDATA / "cargo" / "log"),
    ],
    "java": [
        str(_LOCALAPPDATA / "maven" / "log"),
        "C:/maven/logs",
    ],
}

# Stack aliases (architecture.json may use different names)
_STACK_ALIASES: dict[str, list[str]] = {
    "node":       ["node", "npm", "yarn"],
    "python":     ["python", "pip", "uvicorn", "fastapi", "django", "flask"],
    "postgres":   ["postgres", "postgresql", "pg"],
    "redis":      ["redis"],
    "nginx":      ["nginx"],
    "iis":        ["iis"],
    "dotnet":     ["dotnet", "csharp", "c#", "aspnet"],
    "go":         ["go", "golang"],
    "rust":       ["rust", "cargo"],
    "java":       ["java", "spring", "maven", "mvn"],
}


def _expand_dirs(patterns: list[str]) -> list[Path]:
    """Expand glob patterns to real directories that exist."""
    result: list[Path] = []
    for pattern in patterns:
        for match in glob.glob(pattern):
            p = Path(match)
            if p.is_dir():
                result.append(p)
    return result


def _recent_log_files(
    directory: Path,
    max_age_seconds: int,
    extensions: tuple[str, ...] = (".log", ".txt", ""),
) -> list[Path]:
    """Return log files modified within the last max_age_seconds, newest first."""
    now = time.time()
    files: list[tuple[float, Path]] = []
    try:
        for entry in directory.iterdir():
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in extensions and entry.suffix != "":
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            age = now - mtime
            if age <= max_age_seconds:
                files.append((mtime, entry))
    except (PermissionError, FileNotFoundError, OSError):
        pass
    files.sort(reverse=True)
    return [f for _, f in files]


def _tail(path: Path, max_bytes: int) -> str:
    """Read the last max_bytes of a text file."""
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
            raw = fh.read(max_bytes)
        return raw.decode("utf-8", errors="replace")
    except (OSError, PermissionError):
        return ""


def _read_dir(directory: Path, max_bytes: int, max_age_seconds: int) -> str:
    """Read tail of the most recent log file in a directory."""
    files = _recent_log_files(directory, max_age_seconds)
    if not files:
        return ""
    # Read up to 3 most recent files
    parts: list[str] = []
    remaining = max_bytes
    for f in files[:3]:
        if remaining <= 0:
            break
        chunk = _tail(f, remaining)
        if chunk.strip():
            parts.append(f"--- {f.name} ---\n{chunk}")
            remaining -= len(chunk)
    return "\n".join(parts)


class LogCollector:
    """Discovers and reads recent log entries from tools and the project workspace.

    System-wide log directories are scanned with a short time window (default 5 min)
    to avoid contaminating one project's context with errors from a previous run.
    Workspace logs are always preferred and not time-limited.
    """

    def __init__(
        self,
        max_bytes_per_tool: int = 3_000,
        max_age_minutes: int = 5,  # short window prevents cross-project contamination
    ) -> None:
        self.max_bytes_per_tool = max_bytes_per_tool
        self.max_age_seconds    = max_age_minutes * 60

    def collect(
        self,
        stack: str,
        workspace: Optional[Path] = None,
        extra_stacks: Optional[list[str]] = None,
    ) -> str:
        """Return a formatted string with recent log content relevant to the stack.

        Args:
            stack:        Primary stack name ("node", "python", "go", etc.)
            workspace:    Project source directory — scanned for *.log files.
            extra_stacks: Additional tool names (e.g., ["postgres", "redis"]).
        """
        sections: list[str] = []

        # 1. Workspace logs (highest priority — closest to the actual failure)
        if workspace and workspace.is_dir():
            ws_logs = self._collect_workspace(workspace)
            if ws_logs:
                sections.append(f"[WORKSPACE LOGS]\n{ws_logs}")

        # 2. System logs for detected stacks
        tool_keys = self._resolve_tools(stack, extra_stacks or [])
        for tool in tool_keys:
            dirs = _expand_dirs(_SYSTEM_LOG_DIRS.get(tool, []))
            for d in dirs:
                content = _read_dir(d, self.max_bytes_per_tool, self.max_age_seconds)
                if content.strip():
                    sections.append(f"[{tool.upper()} LOGS — {d}]\n{content}")

        if not sections:
            return ""

        header = "═" * 60
        return (
            f"\n{header}\nLOGS DEL SISTEMA (últimos {self.max_age_seconds // 60} min)\n{header}\n"
            + "\n\n".join(sections)
            + f"\n{header}\n"
        )

    def _collect_workspace(self, workspace: Path) -> str:
        """Read *.log files and logs/ directories inside the project workspace."""
        parts: list[str] = []
        remaining = self.max_bytes_per_tool * 2  # workspace gets more budget

        # logs/ directory
        logs_dir = workspace / "logs"
        if logs_dir.is_dir():
            content = _read_dir(logs_dir, remaining // 2, self.max_age_seconds)
            if content.strip():
                parts.append(f"[logs/]\n{content}")
                remaining -= len(content)

        # *.log files directly in workspace
        for log_file in sorted(workspace.glob("*.log"), key=lambda f: -f.stat().st_mtime)[:5]:
            if remaining <= 0:
                break
            chunk = _tail(log_file, min(remaining, 2000))
            if chunk.strip():
                parts.append(f"[{log_file.name}]\n{chunk}")
                remaining -= len(chunk)

        # stderr / output files generated by common runners
        for fname in ("stderr.txt", "error.log", "app.log", "server.log", "debug.log"):
            p = workspace / fname
            if p.exists() and remaining > 0:
                chunk = _tail(p, min(remaining, 1500))
                if chunk.strip():
                    parts.append(f"[{fname}]\n{chunk}")
                    remaining -= len(chunk)

        return "\n".join(parts)

    def _resolve_tools(self, stack: str, extra: list[str]) -> list[str]:
        """Map stack names to log tool keys."""
        keys: list[str] = []
        all_names = [stack.lower()] + [s.lower() for s in extra]
        for name in all_names:
            for tool_key, aliases in _STACK_ALIASES.items():
                if name in aliases and tool_key not in keys:
                    keys.append(tool_key)
                    break
            else:
                # Direct match
                if name in _SYSTEM_LOG_DIRS and name not in keys:
                    keys.append(name)
        return keys
