"""test_triage — classify test failures as 'bad test' or 'bad code'.

'bad test'  → regenerate the test file (wrong import, wrong mock, misnamed symbol)
'bad code'  → run AutoFixAgent on the source file (logic error, missing impl)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class TriageVerdict(str, Enum):
    BAD_TEST = "bad_test"      # problem is in the test file itself
    BAD_CODE = "bad_code"      # problem is in the source being tested
    UNKNOWN = "unknown"        # cannot determine — skip auto-fix


@dataclass
class TriageResult:
    verdict: TriageVerdict
    reason: str
    source_files: list[str]    # source files implicated (for AutoFixAgent)
    test_file: str             # test file implicated (for regeneration)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "reason": self.reason,
            "source_files": self.source_files,
            "test_file": self.test_file,
        }


# ── Patterns that suggest the TEST is wrong ──────────────────────────────────

_BAD_TEST_PATTERNS = [
    # ImportError / AttributeError on a test-side import
    re.compile(r"ImportError.*test_", re.IGNORECASE),
    re.compile(r"ModuleNotFoundError.*test_", re.IGNORECASE),
    re.compile(r"AttributeError.*'NoneType'.*mock", re.IGNORECASE),
    re.compile(r"AttributeError.*spec", re.IGNORECASE),
    # Test referenced a function/class that doesn't exist in source
    re.compile(r"has no attribute '(\w+)'.*test", re.IGNORECASE),
    # Mock misconfiguration
    re.compile(r"patch.*not found|cannot patch|mocker\.patch.*Error", re.IGNORECASE),
    # Fixture not found
    re.compile(r"fixture '(\w+)' not found", re.IGNORECASE),
    # Wrong test structure (jest)
    re.compile(r"Your test suite must contain at least one test", re.IGNORECASE),
    re.compile(r"Cannot find module '.*' from '.*test", re.IGNORECASE),
    re.compile(r"SyntaxError.*test_", re.IGNORECASE),
]

# ── Patterns that suggest the SOURCE CODE is wrong ───────────────────────────

_BAD_CODE_PATTERNS = [
    # Logic errors
    re.compile(r"AssertionError"),
    re.compile(r"assert .* == .*"),
    re.compile(r"Expected.*Received", re.IGNORECASE),         # jest
    re.compile(r"expected.*to.*(?:equal|be|contain)", re.IGNORECASE),
    # Runtime crashes in source
    re.compile(r"AttributeError: '(?!NoneType).*' object has no attribute"),
    re.compile(r"TypeError: .* takes \d+ positional argument"),
    re.compile(r"KeyError:"),
    re.compile(r"ValueError:"),
    re.compile(r"ZeroDivisionError"),
    re.compile(r"IndexError"),
    re.compile(r"NameError: name '(\w+)' is not defined"),
    # HTTP / API failures
    re.compile(r"(?:4\d\d|5\d\d) (?:Not Found|Internal Server Error|Unauthorized|Forbidden)", re.IGNORECASE),
    re.compile(r"status(?:_?code)?\s*[=:]\s*(?:4\d\d|5\d\d)"),
    # Missing interface implementation (caught by conformance verifier but may surface in tests)
    re.compile(r"NotImplementedError"),
    re.compile(r"abstract.*not.*implement", re.IGNORECASE),
]

# ── Source file extractors ────────────────────────────────────────────────────

_SOURCE_FILE_RE = re.compile(
    r'(?:src|app|lib|api|routes|services|models|controllers|utils|middleware)'
    r'(?:[/\\][\w\-\.]+)+'
    r'\.(?:py|ts|js|go|java|cs|rs)',
    re.IGNORECASE,
)


def _extract_source_files(output: str, source_dir: Path) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for m in _SOURCE_FILE_RE.finditer(output):
        raw = m.group(0).replace("\\", "/")
        # Verify file exists in source_dir
        if (source_dir / raw).exists() and raw not in seen:
            seen.add(raw)
            results.append(raw)
    return results


def _extract_test_file(output: str, test_file_hint: str = "") -> str:
    """Return the test file path from the failure output, or the hint."""
    if test_file_hint:
        return test_file_hint
    m = re.search(r'(tests?/test_[\w/\-]+\.(?:py|ts|js))', output, re.IGNORECASE)
    return m.group(1) if m else ""


# ─────────────────────────────── main function ──

def triage_test_failure(
    test_output: str,
    test_file: str = "",
    source_dir: Optional[Path] = None,
) -> TriageResult:
    """Classify a test failure from runner stdout/stderr.

    Parameters
    ----------
    test_output : str
        Combined stdout+stderr from the test runner.
    test_file : str
        The test file path that failed (hint — used as fallback).
    source_dir : Path | None
        Root of generated source — used to verify that extracted paths exist.
    """
    src_dir = source_dir or Path(".")

    bad_test_score = sum(1 for p in _BAD_TEST_PATTERNS if p.search(test_output))
    bad_code_score = sum(1 for p in _BAD_CODE_PATTERNS if p.search(test_output))

    source_files = _extract_source_files(test_output, src_dir)
    found_test = _extract_test_file(test_output, test_file)

    if bad_test_score > bad_code_score:
        return TriageResult(
            verdict=TriageVerdict.BAD_TEST,
            reason=f"El error apunta al propio archivo de test (score bad_test={bad_test_score} > bad_code={bad_code_score}).",
            source_files=source_files,
            test_file=found_test,
        )

    if bad_code_score > 0:
        return TriageResult(
            verdict=TriageVerdict.BAD_CODE,
            reason=f"El error apunta a lógica en el código fuente (score bad_code={bad_code_score}, bad_test={bad_test_score}).",
            source_files=source_files,
            test_file=found_test,
        )

    return TriageResult(
        verdict=TriageVerdict.UNKNOWN,
        reason="No se pudo clasificar el error automáticamente.",
        source_files=source_files,
        test_file=found_test,
    )


# ─────────────────────────────── batch triage ──

@dataclass
class BatchTriageReport:
    bad_test_count: int = 0
    bad_code_count: int = 0
    unknown_count: int = 0
    results: list[TriageResult] = None

    def __post_init__(self):
        if self.results is None:
            self.results = []

    def to_dict(self) -> dict:
        return {
            "bad_test_count": self.bad_test_count,
            "bad_code_count": self.bad_code_count,
            "unknown_count": self.unknown_count,
            "results": [r.to_dict() for r in self.results],
        }


def triage_failures(
    failures: list[dict],
    source_dir: Optional[Path] = None,
) -> BatchTriageReport:
    """Triage a list of failure dicts from a test runner report.

    Each failure dict should have at minimum:
      - "output": str  (combined stdout+stderr for this test)
      - "test_file": str  (optional — the test file path)
    """
    report = BatchTriageReport()
    for failure in failures:
        output = failure.get("output", "")
        test_file = failure.get("test_file", "")
        result = triage_test_failure(output, test_file, source_dir)
        report.results.append(result)
        if result.verdict == TriageVerdict.BAD_TEST:
            report.bad_test_count += 1
        elif result.verdict == TriageVerdict.BAD_CODE:
            report.bad_code_count += 1
        else:
            report.unknown_count += 1
    return report
