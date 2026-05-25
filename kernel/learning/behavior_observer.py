"""
BehaviorObserver — captures AI behavior at every pipeline step.

Records observations from all providers (Qwen, Gemini, Gemini) across all roles
(code_generator, global_architect, requirements_interviewer, etc.) and stores them
as append-only JSONL files for subsequent knowledge base construction.

Storage layout:
  data/learning/observations/code_generation.jsonl
  data/learning/observations/escalations.jsonl
  data/learning/observations/phase_outcomes.jsonl
  data/learning/observations/architecture.jsonl

Each record is a self-contained JSON object with timestamp, provider, role, and
enough context to reconstruct what happened and why it succeeded or failed.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "learning" / "observations"
_LOCK = threading.Lock()


def _write(filename: str, record: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _DATA_DIR / filename
    record["_ts"] = datetime.now(timezone.utc).isoformat()
    line = json.dumps(record, ensure_ascii=False)
    with _LOCK:
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def _lang_from_path(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    return {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "react", ".tsx": "react_ts", ".vue": "vue",
        ".html": "html", ".css": "css", ".go": "go",
        ".java": "java", ".cs": "csharp", ".rs": "rust",
        ".rb": "ruby", ".php": "php", ".kt": "kotlin",
    }.get(ext, "other")


class BehaviorObserver:
    """
    Passive observer — never blocks the pipeline. All writes are fire-and-forget
    in the calling thread but wrapped in a lock so they don't corrupt JSONL files.
    """

    def record_code_generation(
        self,
        *,
        provider: str,
        filepath: str,
        task_summary: str,        # first 400 chars of the task JSON
        response_snippet: str,    # first 600 chars of the generated code
        validated: bool,
        attempt: int,
        project_id: str = "",
        module_name: str = "",
        framework: str = "",
    ) -> None:
        """Record any successful code generation regardless of provider."""
        try:
            _write("code_generation.jsonl", {
                "provider": provider,
                "language": _lang_from_path(filepath),
                "filepath": filepath,
                "module": module_name,
                "framework": framework,
                "validated": validated,
                "attempt": attempt,
                "project_id": project_id,
                "task_summary": task_summary[:400],
                "response_snippet": response_snippet[:600],
            })
        except Exception as e:
            logger.debug("BehaviorObserver.record_code_generation failed: %s", e)

    def record_escalation(
        self,
        *,
        filepath: str,
        qwen_attempts: list[str],   # last error from each Qwen attempt
        cloud_provider: str,         # "gemini" | "gemini" | "gemini_haiku"
        cloud_response_snippet: str,
        cloud_validated: bool,
        failure_reason: str = "",
        project_id: str = "",
        module_name: str = "",
    ) -> None:
        """Record cases where Qwen failed and a cloud AI succeeded — gold data for learning."""
        try:
            _write("escalations.jsonl", {
                "filepath": filepath,
                "language": _lang_from_path(filepath),
                "module": module_name,
                "project_id": project_id,
                "qwen_attempts": len(qwen_attempts),
                "qwen_last_error": (qwen_attempts[-1] if qwen_attempts else "")[:300],
                "failure_reason": failure_reason[:200],
                "cloud_provider": cloud_provider,
                "cloud_response_snippet": cloud_response_snippet[:800],
                "cloud_validated": cloud_validated,
            })
        except Exception as e:
            logger.debug("BehaviorObserver.record_escalation failed: %s", e)

    def record_phase_outcome(
        self,
        *,
        phase: str,
        provider: str,
        role: str,
        input_summary: str,
        output_summary: str,
        success: bool,
        project_id: str = "",
        extra: Optional[dict] = None,
    ) -> None:
        """Record the outcome of a pipeline phase (architecture, requirements, etc.)."""
        try:
            _write("phase_outcomes.jsonl", {
                "phase": phase,
                "provider": provider,
                "role": role,
                "success": success,
                "project_id": project_id,
                "input_summary": input_summary[:300],
                "output_summary": output_summary[:400],
                **(extra or {}),
            })
        except Exception as e:
            logger.debug("BehaviorObserver.record_phase_outcome failed: %s", e)

    def record_architecture(
        self,
        *,
        provider: str,
        project_type: str,
        description_summary: str,
        module_count: int,
        stack: dict,
        architecture_snippet: str,
        project_id: str = "",
        attempt: int = 1,
    ) -> None:
        """Record successful architecture designs for pattern learning."""
        try:
            _write("architecture.jsonl", {
                "provider": provider,
                "project_type": project_type,
                "description_summary": description_summary[:300],
                "module_count": module_count,
                "stack": stack,
                "architecture_snippet": architecture_snippet[:800],
                "project_id": project_id,
                "attempt": attempt,
            })
        except Exception as e:
            logger.debug("BehaviorObserver.record_architecture failed: %s", e)

    # ─── Bulk statistics helpers ──────────────────────────────────────────────

    def stats(self) -> dict:
        """Return counts per observation file."""
        result = {}
        for f in _DATA_DIR.glob("*.jsonl"):
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
                result[f.stem] = len([l for l in lines if l.strip()])
            except Exception:
                result[f.stem] = -1
        return result
