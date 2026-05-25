"""
KnowledgeBase — builds and queries the learned pattern library.

Reads observation JSONL files written by BehaviorObserver and organizes them
into queryable pattern collections. Also maintains a curated patterns JSON file
that can be manually edited or AI-synthesized.

Storage layout:
  data/learning/patterns/python.json
  data/learning/patterns/javascript.json
  data/learning/patterns/typescript.json
  data/learning/patterns/go.json
  ...
  data/learning/patterns/cross_language.json  ← architecture & phase patterns

Query flow:
  1. Check curated patterns (JSON files) first — highest quality
  2. Fall back to raw observations (JSONL) for recency
  3. Score by language match, framework match, recency

Pattern record schema (in JSON files):
{
  "id": "uuid",
  "type": "code" | "escalation" | "architecture" | "phase",
  "language": "python",
  "framework": "fastapi",
  "role": "code_generator",
  "description": "one-line description of what this pattern solves",
  "context_hint": "short summary of when to apply this",
  "example_input": "...",   # optional: task summary or input context
  "example_output": "...",  # code snippet or architecture snippet
  "quality": 0.9,           # 0-1, manually set or inferred from validation
  "provider": "gemini",     # who generated this (for escalation cases)
  "hits": 0,                # how many times this pattern was surfaced
  "_ts": "2026-01-01T..."
}
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PATTERNS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "learning" / "patterns"
_OBS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "learning" / "observations"
_LOCK = threading.Lock()

_LANG_ALIASES = {
    "react": "javascript", "react_ts": "typescript", "vue": "javascript",
    "nodejs": "javascript", "node": "javascript",
}


def _normalize_lang(lang: str) -> str:
    return _LANG_ALIASES.get(lang.lower(), lang.lower())


def _load_patterns(lang: str) -> list[dict]:
    path = _PATTERNS_DIR / f"{lang}.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_patterns(lang: str, patterns: list[dict]) -> None:
    _PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
    path = _PATTERNS_DIR / f"{lang}.json"
    with _LOCK:
        path.write_text(json.dumps(patterns, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_recent_observations(filename: str, limit: int = 200) -> list[dict]:
    path = _OBS_DIR / filename
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        records = []
        for line in reversed(lines[-limit:]):
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
        return records
    except Exception:
        return []


class KnowledgeBase:
    """
    Manages the learned pattern library.

    Thread-safe: reads/writes use a file-level lock.
    Graceful: all methods return empty results on any error.
    """

    # ─── Write API ───────────────────────────────────────────────────────────

    def add_code_pattern(
        self,
        *,
        language: str,
        framework: str = "",
        role: str = "code_generator",
        description: str,
        context_hint: str = "",
        example_input: str = "",
        example_output: str,
        quality: float = 0.8,
        provider: str = "unknown",
    ) -> str:
        """Persist a curated code pattern. Returns the new pattern ID."""
        lang = _normalize_lang(language)
        patterns = _load_patterns(lang)
        record = {
            "id": str(uuid.uuid4())[:8],
            "type": "code",
            "language": lang,
            "framework": framework,
            "role": role,
            "description": description,
            "context_hint": context_hint,
            "example_input": example_input[:400],
            "example_output": example_output[:800],
            "quality": quality,
            "provider": provider,
            "hits": 0,
            "_ts": datetime.now(timezone.utc).isoformat(),
        }
        patterns.append(record)
        _save_patterns(lang, patterns)
        return record["id"]

    def add_escalation_pattern(
        self,
        *,
        language: str,
        description: str,
        failure_pattern: str,    # what Qwen typically gets wrong
        solution_snippet: str,   # what the cloud AI did right
        provider: str,
        quality: float = 0.9,
    ) -> str:
        """Persist an escalation recovery pattern."""
        lang = _normalize_lang(language)
        patterns = _load_patterns("escalation_patterns")
        record = {
            "id": str(uuid.uuid4())[:8],
            "type": "escalation",
            "language": lang,
            "description": description,
            "failure_pattern": failure_pattern[:400],
            "solution_snippet": solution_snippet[:800],
            "provider": provider,
            "quality": quality,
            "hits": 0,
            "_ts": datetime.now(timezone.utc).isoformat(),
        }
        patterns.append(record)
        _save_patterns("escalation_patterns", patterns)
        return record["id"]

    def add_architecture_pattern(
        self,
        *,
        project_type: str,
        description: str,
        modules_summary: str,
        stack_hint: str,
        quality: float = 0.85,
        provider: str = "gemini",
    ) -> str:
        """Persist a successful architecture pattern."""
        patterns = _load_patterns("cross_language")
        record = {
            "id": str(uuid.uuid4())[:8],
            "type": "architecture",
            "project_type": project_type,
            "description": description,
            "modules_summary": modules_summary[:600],
            "stack_hint": stack_hint[:200],
            "quality": quality,
            "provider": provider,
            "hits": 0,
            "_ts": datetime.now(timezone.utc).isoformat(),
        }
        patterns.append(record)
        _save_patterns("cross_language", patterns)
        return record["id"]

    # ─── Query API ───────────────────────────────────────────────────────────

    def query_code_examples(
        self,
        language: str,
        framework: str = "",
        role: str = "code_generator",
        n: int = 3,
    ) -> list[dict]:
        """Return the top-N most relevant code patterns for a given language/framework."""
        lang = _normalize_lang(language)
        curated = _load_patterns(lang)

        # Score: framework match bonus + quality + hits (capped)
        def _score(p: dict) -> float:
            s = p.get("quality", 0.5)
            if framework and p.get("framework", "").lower() == framework.lower():
                s += 0.3
            if p.get("role", "") == role:
                s += 0.1
            s += min(p.get("hits", 0), 10) * 0.01
            return s

        scored = sorted(curated, key=_score, reverse=True)[:n]

        # If not enough curated, supplement with raw observations
        if len(scored) < n:
            raw = _load_recent_observations("code_generation.jsonl", limit=100)
            raw_for_lang = [
                r for r in raw
                if _normalize_lang(r.get("language", "")) == lang
                and r.get("validated", False)
                and r.get("response_snippet", "")
            ]
            for r in raw_for_lang[: n - len(scored)]:
                scored.append({
                    "type": "code",
                    "language": lang,
                    "description": f"Generación reciente — {r.get('filepath', '')}",
                    "example_output": r.get("response_snippet", ""),
                    "provider": r.get("provider", "unknown"),
                    "quality": 0.7 if r.get("validated") else 0.3,
                    "_from_obs": True,
                })

        return scored[:n]

    def query_escalation_patterns(
        self,
        language: str,
        n: int = 2,
    ) -> list[dict]:
        """Return escalation recovery patterns for a language."""
        lang = _normalize_lang(language)
        curated = [
            p for p in _load_patterns("escalation_patterns")
            if _normalize_lang(p.get("language", "")) == lang
        ]
        if not curated:
            # Derive from raw escalation observations
            raw = _load_recent_observations("escalations.jsonl", limit=50)
            curated = [
                {
                    "type": "escalation",
                    "language": lang,
                    "description": f"Caso real — {r.get('filepath', '')}",
                    "failure_pattern": r.get("qwen_last_error", ""),
                    "solution_snippet": r.get("cloud_response_snippet", ""),
                    "provider": r.get("cloud_provider", "gemini"),
                }
                for r in raw
                if _normalize_lang(r.get("language", "")) == lang
                and r.get("cloud_validated", False)
            ][:n]
        return curated[:n]

    def query_architecture_patterns(self, project_type: str = "", n: int = 2) -> list[dict]:
        """Return architecture patterns, optionally filtered by project type."""
        patterns = _load_patterns("cross_language")
        arch = [p for p in patterns if p.get("type") == "architecture"]
        if project_type:
            arch = sorted(arch, key=lambda p: (p.get("project_type", "") == project_type), reverse=True)
        return arch[:n]

    def increment_hits(self, pattern_id: str, lang_file: str) -> None:
        """Track how often a pattern is actually used."""
        try:
            patterns = _load_patterns(lang_file)
            for p in patterns:
                if p.get("id") == pattern_id:
                    p["hits"] = p.get("hits", 0) + 1
                    _save_patterns(lang_file, patterns)
                    break
        except Exception:
            pass

    # ─── Synthesis from observations (call periodically or on demand) ─────────

    def synthesize_from_observations(self, min_quality: float = 0.75) -> int:
        """
        Promote validated raw observations to curated patterns.
        Returns number of new patterns added.
        """
        added = 0
        raw = _load_recent_observations("code_generation.jsonl", limit=500)
        for r in raw:
            if not r.get("validated") or not r.get("response_snippet"):
                continue
            lang = _normalize_lang(r.get("language", "other"))
            existing = _load_patterns(lang)
            # Avoid duplicates by checking snippet similarity (simple prefix check)
            snippet = r.get("response_snippet", "")[:100]
            if any(p.get("example_output", "")[:100] == snippet for p in existing):
                continue
            self.add_code_pattern(
                language=lang,
                framework=r.get("framework", ""),
                description=f"Auto-sintetizado de {r.get('filepath', 'unknown')} — proyecto {r.get('project_id', '')}",
                context_hint=r.get("task_summary", "")[:200],
                example_output=r.get("response_snippet", ""),
                quality=0.8 if r.get("provider") in ("gemini", "gemini") else 0.65,
                provider=r.get("provider", "unknown"),
            )
            added += 1
        return added

    def stats(self) -> dict:
        """Return pattern counts per language file."""
        result = {}
        for f in _PATTERNS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                result[f.stem] = len(data)
            except Exception:
                result[f.stem] = -1
        return result
