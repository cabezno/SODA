"""Detect whether required runtime tools are installed for a given stack."""
import asyncio
import subprocess
import sys
from typing import NamedTuple


class ToolStatus(NamedTuple):
    name: str
    available: bool
    version: str
    required_for: str


async def _check(name: str, cmd: list[str]) -> tuple[bool, str]:
    def _run():
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    subprocess.list2cmdline(cmd), shell=True,
                    capture_output=True, text=True, timeout=8,
                )
            else:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if r.returncode == 0:
                first = (r.stdout + r.stderr).strip().splitlines()
                return True, first[0] if first else ""
            return False, ""
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            return False, ""
    return await asyncio.to_thread(_run)


async def check_stack_tools(run_cmd: str, install_cmd: str) -> list[ToolStatus]:
    """Return availability of every runtime tool required by the project stack."""
    rc = (run_cmd or "").lower()
    ic = (install_cmd or "").lower()

    tasks: list[tuple[str, list[str], str]] = []  # (name, cmd, required_for)

    is_python = "pip" in ic or any(x in rc for x in ("python", "uvicorn", "flask", "fastapi", "django", "gunicorn"))
    is_node   = any(x in ic for x in ("npm", "yarn", "pnpm")) or any(x in rc for x in ("npm ", "node ", "npx "))
    is_dotnet = "dotnet" in ic or "dotnet" in rc
    is_go     = "go run" in rc or "go build" in rc or "go mod" in ic
    is_rust   = "cargo" in rc or "cargo" in ic
    is_java   = any(x in ic for x in ("mvn", "gradle")) or any(x in rc for x in ("mvn ", "gradle "))
    is_php    = "composer" in ic or "php" in rc
    is_ruby   = "bundle" in ic or "rails" in rc or "ruby" in rc

    if is_python:
        tasks.append(("python", ["python", "--version"],  "Python runtime"))
    if is_node:
        tasks.append(("node",   ["node",   "--version"],  "Node.js runtime"))
        tasks.append(("npm",    ["npm",    "--version"],  "npm"))
    if is_dotnet:
        tasks.append(("dotnet", ["dotnet", "--version"],  ".NET SDK"))
    if is_go:
        tasks.append(("go",     ["go",     "version"],    "Go compiler"))
    if is_rust:
        tasks.append(("cargo",  ["cargo",  "--version"],  "Rust / Cargo"))
    if is_java:
        tasks.append(("mvn",    ["mvn",    "--version"],  "Maven"))
    if is_php:
        tasks.append(("php",    ["php",    "--version"],  "PHP runtime"))
        tasks.append(("composer", ["composer", "--version"], "Composer"))
    if is_ruby:
        tasks.append(("ruby",   ["ruby",   "--version"],  "Ruby runtime"))

    if not tasks:
        return []

    results = await asyncio.gather(*(_check(n, cmd) for n, cmd, _ in tasks))
    return [
        ToolStatus(name=n, available=ok, version=ver, required_for=label)
        for (n, _, label), (ok, ver) in zip(tasks, results)
    ]
