"""
SecurityReviewer — static security analysis of generated code.

Runs fast, deterministic rules (no AI needed for detection).
Optionally calls Gemini for fix suggestions on critical findings.

Rules cover:
  - Hardcoded secrets / credentials
  - Missing authentication on endpoints (when blueprint requires auth)
  - Wide-open CORS
  - SQL injection via f-strings / concatenation
  - Insecure defaults (debug=True, SECRET_KEY placeholder, etc.)
  - Sensitive data in logs
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────── models ──

@dataclass
class SecurityFinding:
    rule: str
    severity: str          # "critical" | "high" | "medium" | "low"
    file: str
    line: Optional[int]
    message: str
    snippet: str = ""

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "snippet": self.snippet[:120],
        }


@dataclass
class SecurityReport:
    findings: list[SecurityFinding] = field(default_factory=list)
    score: float = 100.0   # 0-100 (lower = worse)
    passed: bool = True
    ai_suggestions: list[dict] = field(default_factory=list)

    @property
    def critical(self) -> list[SecurityFinding]:
        return [f for f in self.findings if f.severity == "critical"]

    @property
    def high(self) -> list[SecurityFinding]:
        return [f for f in self.findings if f.severity == "high"]

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 1),
            "passed": self.passed,
            "critical_count": len(self.critical),
            "high_count": len(self.high),
            "total_findings": len(self.findings),
            "findings": [f.to_dict() for f in self.findings[:30]],
            "ai_suggestions": self.ai_suggestions,
        }


# ─────────────────────────────────────────── rule helpers ──

def _lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []


def _skip(path: Path) -> bool:
    bad = {"node_modules", ".git", "__pycache__", "venv", "dist", "build",
           ".next", "target", "bin", "obj", "test", "tests", "spec", "migrations"}
    return any(s in path.parts for s in bad)


def _files(source_dir: Path, *exts: str) -> list[Path]:
    result = []
    for ext in exts:
        for p in source_dir.rglob(f"*{ext}"):
            if not _skip(p):
                result.append(p)
    return result


# ─────────────────────────────────────────── individual rules ──

# SEC001 — Hardcoded secrets
_SECRET_PATTERNS = [
    (r'(?i)(password|passwd|pwd|secret|api[_-]?key|token|auth[_-]?key)\s*=\s*["\'][^"\']{6,}["\']', "Valor de credencial hardcodeado"),
    (r'sk-[a-zA-Z0-9]{20,}', "API key de OpenAI/Anthropic hardcodeada"),
    (r'AIza[0-9A-Za-z\-_]{35}', "API key de Google hardcodeada"),
    (r'(?i)secret[_-]?key\s*=\s*["\'][^"\']{8,}["\']', "SECRET_KEY hardcodeada"),
    (r'Bearer\s+[a-zA-Z0-9\-_]{20,}', "Token Bearer hardcodeado"),
]

def _rule_hardcoded_secrets(source_dir: Path, _blueprint: dict) -> list[SecurityFinding]:
    findings = []
    exts = (".py", ".ts", ".js", ".jsx", ".tsx", ".java", ".cs", ".go", ".rb", ".php")
    for f in _files(source_dir, *exts):
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        lines = _lines(f)
        for i, line in enumerate(lines, 1):
            for pattern, msg in _SECRET_PATTERNS:
                if re.search(pattern, line):
                    # Skip placeholder values
                    if re.search(r'(?i)(your[_-]?|<|>|xxx|placeholder|changeme|example|test)', line):
                        continue
                    findings.append(SecurityFinding(
                        rule="SEC001", severity="critical", file=rel, line=i,
                        message=f"{msg}.",
                        snippet=line.strip()[:100],
                    ))
    return findings


# SEC002 — SQL injection via string concatenation / f-strings
_SQL_INJECTION_PATTERNS = [
    r'(?i)(execute|query|raw)\s*\(\s*f["\'].*\{',
    r'(?i)(execute|query|raw)\s*\(\s*["\'].*\+\s*\w',
    r'(?i)cursor\.execute\s*\(\s*["\'].*%\s*\w',
]

def _rule_sql_injection(source_dir: Path, _blueprint: dict) -> list[SecurityFinding]:
    findings = []
    for f in _files(source_dir, ".py", ".php", ".java", ".js", ".ts"):
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        lines = _lines(f)
        for i, line in enumerate(lines, 1):
            for pattern in _SQL_INJECTION_PATTERNS:
                if re.search(pattern, line):
                    findings.append(SecurityFinding(
                        rule="SEC002", severity="critical", file=rel, line=i,
                        message="Posible SQL injection: query construida con concatenación/f-string. Usá parámetros bindados.",
                        snippet=line.strip()[:100],
                    ))
    return findings


# SEC003 — CORS abierto en producción
_CORS_OPEN_PATTERNS = [
    r'(?i)allow[_-]?origins?\s*[=:]\s*[\["\']?\s*\*',
    r'(?i)cors\s*\(\s*origins?\s*=\s*[\["\']?\s*\*',
    r'(?i)Access-Control-Allow-Origin["\s]*:\s*["\']?\*',
    r'(?i)allow_all_origins\s*=\s*True',
]

def _rule_cors_open(source_dir: Path, _blueprint: dict) -> list[SecurityFinding]:
    findings = []
    for f in _files(source_dir, ".py", ".ts", ".js", ".java", ".cs", ".go"):
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        lines = _lines(f)
        for i, line in enumerate(lines, 1):
            for pattern in _CORS_OPEN_PATTERNS:
                if re.search(pattern, line):
                    findings.append(SecurityFinding(
                        rule="SEC003", severity="high", file=rel, line=i,
                        message="CORS configurado con wildcard '*' — permite requests desde cualquier origen.",
                        snippet=line.strip()[:100],
                    ))
    return findings


# SEC004 — Debug mode activado
_DEBUG_PATTERNS = [
    (r'(?i)debug\s*=\s*True', "python"),
    (r'(?i)app\.run\s*\(.*debug\s*=\s*True', "python"),
    (r'(?i)NODE_ENV\s*[=:]\s*["\']development["\']', "node"),
    (r'(?i)DEBUG\s*=\s*1', "any"),
]

def _rule_debug_mode(source_dir: Path, _blueprint: dict) -> list[SecurityFinding]:
    findings = []
    for f in _files(source_dir, ".py", ".js", ".ts", ".env"):
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        if ".env.example" in rel:
            continue
        lines = _lines(f)
        for i, line in enumerate(lines, 1):
            for pattern, _ in _DEBUG_PATTERNS:
                if re.search(pattern, line):
                    findings.append(SecurityFinding(
                        rule="SEC004", severity="medium", file=rel, line=i,
                        message="Modo debug activo — no debe llegar a producción.",
                        snippet=line.strip()[:100],
                    ))
    return findings


# SEC005 — Endpoints sin autenticación cuando blueprint requiere auth
def _rule_missing_auth(source_dir: Path, blueprint: dict) -> list[SecurityFinding]:
    findings = []
    features = [str(f).lower() for f in blueprint.get("funcionalidades", [])]
    desc = blueprint.get("descripcion", "").lower()
    requires_auth = any(
        kw in features or kw in desc
        for kw in ("auth", "login", "jwt", "token", "usuario", "user", "account", "session")
    )
    if not requires_auth:
        return []

    # Python/FastAPI: endpoints without Depends(get_current_user) or similar
    for f in _files(source_dir, ".py"):
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        src = "\n".join(_lines(f))
        # Find route definitions
        routes = re.findall(r'@(?:app|router)\.(get|post|put|patch|delete)\s*\(["\']([^"\']+)["\']', src)
        has_auth_import = bool(re.search(r'(?i)(get_current_user|oauth2_scheme|security|Depends.*auth)', src))
        if routes and not has_auth_import:
            findings.append(SecurityFinding(
                rule="SEC005", severity="high", file=rel, line=None,
                message=f"Archivo con {len(routes)} endpoint(s) pero sin importar mecanismo de autenticación — el blueprint requiere auth.",
                snippet=f"Rutas detectadas: {[r[1] for r in routes[:3]]}",
            ))

    return findings


# SEC006 — Datos sensibles en logs
_SENSITIVE_LOG_PATTERNS = [
    r'(?i)(log|print|console\.log)\s*\(.*\b(password|passwd|secret|token|credit.card|ssn|cvv)\b',
    r'(?i)(logger\.(info|debug|warning|error))\s*\(.*\b(password|token|secret)\b',
]

def _rule_sensitive_logs(source_dir: Path, _blueprint: dict) -> list[SecurityFinding]:
    findings = []
    for f in _files(source_dir, ".py", ".ts", ".js", ".java", ".cs"):
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        lines = _lines(f)
        for i, line in enumerate(lines, 1):
            for pattern in _SENSITIVE_LOG_PATTERNS:
                if re.search(pattern, line):
                    findings.append(SecurityFinding(
                        rule="SEC006", severity="medium", file=rel, line=i,
                        message="Posible log de datos sensibles (contraseña/token).",
                        snippet=line.strip()[:100],
                    ))
    return findings


# SEC007 — Placeholder de SECRET_KEY sin cambiar
def _rule_secret_key_placeholder(source_dir: Path, _blueprint: dict) -> list[SecurityFinding]:
    findings = []
    placeholders = re.compile(
        r'(?i)(secret[_-]?key|jwt[_-]?secret)\s*[=:]\s*["\']'
        r'(changeme|change.me|your.secret|mysecret|supersecret|dev.secret|development)["\']'
    )
    for f in _files(source_dir, ".py", ".env", ".ts", ".js", ".yaml", ".yml"):
        rel = str(f.relative_to(source_dir)).replace("\\", "/")
        if ".example" in rel:
            continue
        lines = _lines(f)
        for i, line in enumerate(lines, 1):
            if placeholders.search(line):
                findings.append(SecurityFinding(
                    rule="SEC007", severity="critical", file=rel, line=i,
                    message="SECRET_KEY con valor placeholder — debe ser aleatoria y confidencial.",
                    snippet=line.strip()[:100],
                ))
    return findings


# ─────────────────────────────────────────── main class ──

ALL_RULES = [
    _rule_hardcoded_secrets,
    _rule_sql_injection,
    _rule_cors_open,
    _rule_debug_mode,
    _rule_missing_auth,
    _rule_sensitive_logs,
    _rule_secret_key_placeholder,
]

_SEVERITY_PENALTY = {"critical": 25, "high": 15, "medium": 5, "low": 1}


class SecurityReviewer:
    """
    Runs static security rules on the generated source directory.
    Optionally requests AI fix suggestions for critical/high findings.
    """

    def __init__(self, gemini_driver=None, context_builder=None, notify_fn=None):
        self.gemini = gemini_driver
        self.builder = context_builder
        self.notify = notify_fn or (lambda *a, **kw: None)

    def review(self, source_dir: Path, blueprint: dict) -> SecurityReport:
        report = SecurityReport()
        all_findings: list[SecurityFinding] = []

        for rule_fn in ALL_RULES:
            try:
                found = rule_fn(source_dir, blueprint)
                all_findings.extend(found)
            except Exception as e:
                self.notify(f"SecurityReviewer: regla {rule_fn.__name__} falló: {e}", "LOG", {})

        # Deduplicate by (rule, file, line)
        seen: set[tuple] = set()
        for f in all_findings:
            key = (f.rule, f.file, f.line, f.snippet[:40])
            if key not in seen:
                seen.add(key)
                report.findings.append(f)

        # Score
        penalty = sum(_SEVERITY_PENALTY.get(f.severity, 0) for f in report.findings)
        report.score = max(0.0, 100.0 - penalty)
        report.passed = len(report.critical) == 0 and len(report.high) == 0

        if report.findings:
            self.notify(
                f"SecurityReviewer: {len(report.findings)} hallazgo(s) — score {report.score:.0f}/100"
                f" [{len(report.critical)} críticos, {len(report.high)} altos]",
                "HEALTH_WARN" if not report.passed else "LOG",
                report.to_dict(),
            )
            for f in report.findings:
                icon = "🔴" if f.severity == "critical" else "🟠" if f.severity == "high" else "🟡"
                print(f"  [{f.rule}] {icon} {f.file}:{f.line or '?'} — {f.message}")
        else:
            self.notify("SecurityReviewer: sin hallazgos de seguridad.", "LOG", {})
            print("  [SECURITY] Sin hallazgos detectados.")

        return report

    async def request_ai_suggestions(self, report: SecurityReport, source_dir: Path) -> list[dict]:
        """Ask Gemini for fix suggestions on critical/high findings."""
        if not self.gemini or not self.builder:
            return []
        actionable = [f for f in report.findings if f.severity in ("critical", "high")]
        if not actionable:
            return []

        findings_text = "\n".join(
            f"  [{f.rule}] {f.severity.upper()} en {f.file}:{f.line or '?'}: {f.message}\n"
            f"  Snippet: {f.snippet}"
            for f in actionable[:10]
        )

        # Collect relevant file snippets
        file_snippets = ""
        seen_files: set[str] = set()
        for finding in actionable[:5]:
            if finding.file in seen_files:
                continue
            seen_files.add(finding.file)
            fp = source_dir / finding.file
            if fp.exists():
                content = fp.read_text(encoding="utf-8", errors="ignore")[:2000]
                file_snippets += f"\n### {finding.file}\n{content}\n"

        task = (
            f"HALLAZGOS DE SEGURIDAD A CORREGIR:\n{findings_text}\n\n"
            f"ARCHIVOS RELEVANTES:{file_snippets}\n\n"
            f"Para cada hallazgo, proporcioná el código corregido. "
            f'Respondé con JSON array: [{{"file": "ruta", "fix_description": "qué cambiaste", "corrected_snippet": "código corregido"}}]'
        )

        try:
            payload = self.builder.build_payload("gemini", "code_fixer", task)
            response = await self.gemini.prompt(payload["system"], payload["user"])
            import json as _json, re as _re
            m = _re.search(r"\[.*\]", response, _re.DOTALL)
            if m:
                suggestions = _json.loads(m.group(0))
                report.ai_suggestions = suggestions
                self.notify(
                    f"SecurityReviewer: {len(suggestions)} sugerencia(s) IA generada(s).",
                    "LOG", {"suggestions": [s.get("file") for s in suggestions]},
                )
                return suggestions
        except Exception as e:
            self.notify(f"SecurityReviewer AI suggestions error: {e}", "LOG", {})

        return []
