from __future__ import annotations

import json
import logging
import subprocess
import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class GBrainService:
    """
    SODA FUSION Integration with Garry Tan's GBrain (https://github.com/garrytan/gbrain).
    Allows SODA FUSION agents to query, read, write, and sync with the user's personal knowledge brain.
    """

    def __init__(self, orchestrator, brain_repo: str = "D:/Desktop/vortex/brain", gbrain_cmd: str = "gbrain"):
        self.orch = orchestrator
        self.brain_repo = Path(brain_repo)
        self.gbrain_cmd = gbrain_cmd
        self._is_active = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if the gbrain CLI is available in the system PATH."""
        try:
            # Try running 'gbrain version'
            res = subprocess.run([self.gbrain_cmd, "version"], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                logger.info(f"GBrain available: {res.stdout.strip()}")
                return True
            return False
        except Exception as exc:
            logger.warning(f"GBrain CLI not available in PATH: {exc}")
            return False

    def is_available(self) -> bool:
        """Return True if gbrain CLI is successfully integrated and available."""
        return self._is_active

    def run_command(self, args: List[str]) -> subprocess.CompletedProcess[str]:
        """Execute a gbrain CLI command safely."""
        cmd = [self.gbrain_cmd] + args
        try:
            # Use shell=True if needed on Windows, but list format usually works on MSYS/Windows
            return subprocess.run(cmd, capture_output=True, text=True, check=False)
        except Exception as exc:
            # Fallback if shell/path issues on Windows
            logger.error(f"Failed to execute gbrain command {cmd}: {exc}")
            # Create a mock completed process with error code
            return subprocess.CompletedProcess(args=cmd, returncode=-1, stdout="", stderr=str(exc))

    # ------------------------------------------------------------------
    # Search & Retrieval
    # ------------------------------------------------------------------

    def query(self, text: str, mode: str = "hybrid") -> str:
        """
        Query the brain for relevant passages.
        modes:
          - 'hybrid': uses 'gbrain query <text>' (RRF + expansion)
          - 'keyword': uses 'gbrain search <text>' (tsvector)
        Returns a formatted block of matches or empty string if no results.
        """
        if not self._is_active:
            return ""

        # Clean query text
        clean_text = text.replace('"', '').replace('\n', ' ').strip()
        if not clean_text:
            return ""

        cmd_type = "query" if mode == "hybrid" else "search"
        res = self.run_command([cmd_type, clean_text])

        if res.returncode != 0:
            logger.warning(f"gbrain {cmd_type} error: {res.stderr}")
            return ""

        output = res.stdout.strip()
        if not output or "No results" in output:
            return ""

        return output

    def get_rag_context(self, current_task_description: str, limit: int = 5) -> str:
        """
        Enrich a prompt context with matching snippets from GBrain.
        Extracts key noun phrases/concepts from the description and queries GBrain.
        """
        if not self._is_active:
            return ""

        # Extract keywords or use the description directly if short
        # Simple heuristic: split sentences or use the first 200 chars for semantic search
        search_query = current_task_description
        if len(current_task_description) > 300:
            # Grab first few sentences or lines as the search query
            lines = [l.strip() for l in current_task_description.split("\n") if l.strip()]
            if lines:
                search_query = lines[0]
                if len(search_query) < 50 and len(lines) > 1:
                    search_query += " " + lines[1]

        # Query using hybrid search
        matches = self.query(search_query, mode="hybrid")
        if not matches:
            # Try keyword search as fallback
            matches = self.query(search_query, mode="keyword")

        if not matches:
            return ""

        return (
            "## CONTEXTO DE CONOCIMIENTO (GBRAIN PERSONAL)\n"
            "Los siguientes fragmentos fueron recuperados de tu base de conocimiento personal (GBrain) "
            "y contienen pautas, decisiones o convenciones relevantes para esta tarea:\n\n"
            f"{matches}\n"
        )

    # ------------------------------------------------------------------
    # Page Management (Get, Put, Capture)
    # ------------------------------------------------------------------

    def get_page(self, slug: str) -> Optional[str]:
        """Retrieve a specific page's content from the brain."""
        if not self._is_active:
            return None

        res = self.run_command(["get", slug])
        if res.returncode == 0:
            return res.stdout
        logger.warning(f"gbrain get '{slug}' failed: {res.stderr}")
        return None

    def put_page(self, slug: str, content: str) -> bool:
        """Write or update a page in the brain."""
        if not self._is_active:
            return False

        # On Windows, writing content via stdin is cleanest to avoid shell escaping issues
        cmd = [self.gbrain_cmd, "put", slug]
        try:
            res = subprocess.run(cmd, input=content, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                logger.info(f"Successfully updated brain page: {slug}")
                return True
            logger.error(f"gbrain put '{slug}' error: {res.stderr}")
            return False
        except Exception as exc:
            logger.error(f"Exception during gbrain put '{slug}': {exc}")
            return False

    def capture(self, content: str, slug: Optional[str] = None, type_name: Optional[str] = None) -> bool:
        """
        Capture a quick note, event, or report into the brain.
        Places it in the inbox or the configured page path.
        """
        if not self._is_active:
            return False

        args = ["capture"]
        if slug:
            args += ["--slug", slug]
        if type_name:
            args += ["--type", type_name]

        cmd = [self.gbrain_cmd] + args
        try:
            res = subprocess.run(cmd, input=content, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                logger.info("Successfully captured note to GBrain")
                return True
            logger.error(f"gbrain capture error: {res.stderr}")
            return False
        except Exception as exc:
            logger.error(f"Exception during gbrain capture: {exc}")
            return False

    # ------------------------------------------------------------------
    # Maintenance & Synchronization
    # ------------------------------------------------------------------

    def sync(self) -> bool:
        """
        Perform git-to-brain sync on the brain repo.
        Runs 'gbrain sync --repo <repo_path> --no-embed'.
        """
        if not self._is_active:
            return False

        args = ["sync", "--no-embed"]
        if self.brain_repo.exists():
            args += ["--repo", str(self.brain_repo)]

        self.orch._notify(f"Sincronizando base de conocimiento GBrain en {self.brain_repo}...", "GBRAIN_SYNC")
        res = self.run_command(args)
        if res.returncode == 0:
            self.orch._notify("GBrain sincronizado exitosamente.", "GBRAIN_SUCCESS")
            return True
        self.orch._notify(f"Error sincronizando GBrain: {res.stderr}", "GBRAIN_ERROR")
        return False

    def dream(self) -> bool:
        """Run the overnight maintenance dream cycle on the brain."""
        if not self._is_active:
            return False

        self.orch._notify("Iniciando ciclo de mantenimiento (Dream) en GBrain...", "GBRAIN_DREAM")
        res = self.run_command(["dream"])
        if res.returncode == 0:
            self.orch._notify("Ciclo de mantenimiento GBrain completado.", "GBRAIN_SUCCESS")
            return True
        self.orch._notify(f"Error en ciclo de mantenimiento GBrain: {res.stderr}", "GBRAIN_ERROR")
        return False

    def stats(self) -> Dict[str, Any]:
        """Retrieve and parse brain statistics."""
        stats_dict = {"pages": 0, "chunks": 0, "links": 0, "tags": 0, "by_type": {}}
        if not self._is_active:
            return stats_dict

        res = self.run_command(["stats"])
        if res.returncode != 0:
            return stats_dict

        lines = res.stdout.splitlines()
        by_type_section = False

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            if "By type:" in line_str:
                by_type_section = True
                continue

            if not by_type_section:
                match = re.match(r"^([^:]+):\s*(\d+)", line_str)
                if match:
                    key = match.group(1).strip().lower()
                    val = int(match.group(2))
                    stats_dict[key] = val
            else:
                match = re.match(r"^([^:]+):\s*(\d+)", line_str)
                if match:
                    key = match.group(1).strip().lower()
                    val = int(match.group(2))
                    stats_dict["by_type"][key] = val

        return stats_dict
