"""Shared utility for AI capacity-error detection and fallback chains."""

CAPACITY_CODES = frozenset({"RATE_LIMIT", "OVERLOADED", "CONNECTION", "AUTH", "TIMEOUT", "API"})


def is_capacity_error(result: str) -> bool:
    """Return True if the driver result is a recoverable capacity/connectivity error."""
    if not result.startswith("ERROR:"):
        return False
    code = result[6:].split(":", 1)[0].strip()
    return code in CAPACITY_CODES


def error_code(result: str) -> str:
    if not result.startswith("ERROR:"):
        return ""
    return result[6:].split(":", 1)[0].strip()
