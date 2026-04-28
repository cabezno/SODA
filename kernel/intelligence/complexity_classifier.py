"""ProjectComplexityClassifier — pure Python, no AI (Arquitecto v2).

Analyzes a project blueprint and returns a complexity level used to select
the appropriate Claude model for the Architect.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Model assignment by complexity — Arquitecto v2
# ---------------------------------------------------------------------------
MODEL_ASSIGNMENT_BY_COMPLEXITY: dict[str, str] = {
    "simple": "claude-haiku-4-5-20251001",
    "medium": "claude-sonnet-4-6",
    "complex": "claude-opus-4-7",
}

MODEL_CALL_CONFIG: dict[str, dict] = {
    "claude-haiku-4-5-20251001": {"max_tokens": 8192},
    "claude-sonnet-4-6":         {"max_tokens": 64000},
    # Opus output cap is 32K; max_continuations allows multi-turn completion for large JSONs
    "claude-opus-4-7":           {"max_tokens": 32000, "max_continuations": 2},
}

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_REGULATED_KEYWORDS = {
    "salud", "health", "hipaa", "medico", "médico", "clinica", "clínica",
    "finanzas", "finance", "financial", "banking", "banco", "pci", "pci-dss",
    "legal", "gdpr", "rgpd", "compliance", "regulado",
}

_REALTIME_KEYWORDS = {
    "tiempo real", "real-time", "realtime", "websocket", "socket.io",
    "live", "streaming", "chat en vivo", "notificación en tiempo",
}

_MULTITENANT_KEYWORDS = {
    "multi-tenant", "multitenant", "multi tenant", "saas", "tenant",
    "organización", "organization", "workspace",
}

_AUTH_COMPLEX_KEYWORDS = {"oauth", "sso", "saml", "mfa", "2fa", "ldap", "openid"}
_AUTH_MODERATE_KEYWORDS = {"jwt", "refresh token", "roles", "permisos", "rbac"}

_SENSITIVE_KEYWORDS = {
    "contraseña", "password", "tarjeta", "credit card", "dni", "pasaporte",
    "datos personales", "pii", "datos sensibles",
}

_COMPLIANCE_PATTERN = re.compile(
    r"\b(gdpr|hipaa|pci[\-\s]?dss|sox|rgpd|iso\s*27001)\b", re.IGNORECASE
)


class ComplexityLevel(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class ComplexitySignals(BaseModel):
    """Signals extracted from the blueprint."""

    estimated_modules: int = Field(default=0, ge=0)
    estimated_loc: int = Field(default=0, ge=0)
    stack_count: int = Field(default=1, ge=1)
    external_integrations: list[str] = Field(default_factory=list)
    requires_realtime: bool = False
    requires_multi_tenant: bool = False
    requires_compliance: list[str] = Field(default_factory=list)
    auth_complexity: Literal["simple", "moderate", "complex"] = "simple"
    estimated_users: int = Field(default=0, ge=0)
    regulated_industry: bool = False
    handles_sensitive_data: bool = False
    complex_workflows: bool = False


class ComplexityAssessment(BaseModel):
    """Result of the complexity evaluation."""

    level: ComplexityLevel
    score: int
    signals: ComplexitySignals
    reasoning: str
    override_available: bool = True


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class ProjectComplexityClassifier:
    """Classifies projects by complexity for model assignment.

    Pure Python — no AI involved.
    """

    def classify(self, blueprint: dict) -> ComplexityAssessment:
        signals = self._extract_signals(blueprint)
        scores = self._calculate_scores(signals)
        level = self._determine_level(scores)
        level = self._apply_minimum_level(level, signals)
        

            
        reasoning = self._build_reasoning(signals, scores, level)

        return ComplexityAssessment(
            level=level,
            score=scores[level.value],
            signals=signals,
            reasoning=reasoning,
        )

    # ------------------------------------------------------------------
    # Signal extraction
    # ------------------------------------------------------------------

    def _extract_signals(self, blueprint: dict) -> ComplexitySignals:
        text = self._blueprint_text(blueprint)
        text_lower = text.lower()

        return ComplexitySignals(
            estimated_modules=self._estimate_modules(blueprint),
            estimated_loc=self._estimate_loc(blueprint),
            stack_count=self._count_stacks(blueprint),
            external_integrations=self._extract_integrations(blueprint, text_lower),
            requires_realtime=self._has_any(text_lower, _REALTIME_KEYWORDS),
            requires_multi_tenant=self._has_any(text_lower, _MULTITENANT_KEYWORDS),
            requires_compliance=self._extract_compliance(text),
            auth_complexity=self._classify_auth(text_lower),
            estimated_users=self._estimate_users(blueprint, text_lower),
            regulated_industry=self._has_any(text_lower, _REGULATED_KEYWORDS),
            handles_sensitive_data=self._has_any(text_lower, _SENSITIVE_KEYWORDS),
            complex_workflows=self._has_complex_workflows(blueprint, text_lower),
        )

    def _blueprint_text(self, blueprint: dict) -> str:
        """Flatten relevant blueprint fields into searchable text."""
        parts: list[str] = []
        for key in (
            "descripcion", "description", "nombre", "name",
            "funcionalidades", "features", "tipo_proyecto", "project_type",
            "stack_sugerido", "stack", "integraciones", "integrations",
            "requisitos", "requirements",
        ):
            val = blueprint.get(key)
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict):
                        parts.extend(str(v) for v in item.values())
            elif isinstance(val, dict):
                parts.extend(str(v) for v in val.values())
        return " ".join(parts)

    def _estimate_modules(self, blueprint: dict) -> int:
        """Estimate module count from features list or explicit field."""
        if "modulos_estimados" in blueprint:
            return int(blueprint["modulos_estimados"])
        features = blueprint.get("funcionalidades") or blueprint.get("features", [])
        if isinstance(features, list):
            # Rough heuristic: ~2 features per module
            return max(1, len(features) // 2 + (1 if len(features) % 2 else 0))
        return 3  # default guess

    def _estimate_loc(self, blueprint: dict) -> int:
        """Estimate lines of code from explicit field or module count."""
        if "loc_estimadas" in blueprint:
            return int(blueprint["loc_estimadas"])
        modules = self._estimate_modules(blueprint)
        # Heuristic: 600 lines per module on average
        return modules * 600

    def _count_stacks(self, blueprint: dict) -> int:
        """Count distinct technology stacks."""
        stack = blueprint.get("stack_sugerido") or blueprint.get("stack", {})
        if isinstance(stack, dict):
            # Count distinct non-empty top-level stack categories
            return max(1, len([v for v in stack.values() if v]))
        if isinstance(stack, list):
            return max(1, len(stack))
        return 1

    def _extract_integrations(self, blueprint: dict, text_lower: str) -> list[str]:
        """Extract external service integrations."""
        integrations: list[str] = []

        # Explicit field
        explicit = blueprint.get("integraciones") or blueprint.get("integrations", [])
        if isinstance(explicit, list):
            integrations.extend(str(i) for i in explicit if i)

        # Keyword scan
        integration_keywords = {
            "stripe", "paypal", "mercadopago", "sendgrid", "twilio", "aws",
            "s3", "firebase", "google maps", "google analytics", "slack",
            "whatsapp", "telegram", "smtp", "email", "sms", "push notif",
        }
        for kw in integration_keywords:
            if kw in text_lower and kw not in integrations:
                integrations.append(kw)

        return list(dict.fromkeys(integrations))  # deduplicate, preserve order

    def _extract_compliance(self, text: str) -> list[str]:
        return list({m.group(0).upper() for m in _COMPLIANCE_PATTERN.finditer(text)})

    def _classify_auth(self, text_lower: str) -> Literal["simple", "moderate", "complex"]:
        if self._has_any(text_lower, _AUTH_COMPLEX_KEYWORDS):
            return "complex"
        if self._has_any(text_lower, _AUTH_MODERATE_KEYWORDS):
            return "moderate"
        return "simple"

    def _estimate_users(self, blueprint: dict, text_lower: str) -> int:
        if "usuarios_estimados" in blueprint:
            return int(blueprint["usuarios_estimados"])
        # Keyword heuristics
        if any(kw in text_lower for kw in ("millones", "millions", "100k", "1m")):
            return 100_000
        if any(kw in text_lower for kw in ("miles", "thousands", "10k", "50k")):
            return 10_000
        if any(kw in text_lower for kw in ("empresa", "company", "corporativo", "corporate")):
            return 500
        return 0

    def _has_complex_workflows(self, blueprint: dict, text_lower: str) -> bool:
        workflow_keywords = {
            "workflow", "proceso de negocio", "business process",
            "aprobación", "approval", "estado", "state machine",
            "pipeline", "etapas múltiples", "multi-step",
        }
        return self._has_any(text_lower, workflow_keywords)

    @staticmethod
    def _has_any(text: str, keywords: set[str]) -> bool:
        return any(kw in text for kw in keywords)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _calculate_scores(self, signals: ComplexitySignals) -> dict[str, int]:
        simple_score = 0
        medium_score = 0
        complex_score = 0

        # SIMPLE signals
        if signals.estimated_modules <= 3:
            simple_score += 3
        if signals.estimated_loc < 2000:
            simple_score += 2
        if signals.stack_count == 1:
            simple_score += 2
        if len(signals.external_integrations) == 0:
            simple_score += 2
        if not signals.requires_realtime:
            simple_score += 1
        if signals.auth_complexity == "simple":
            simple_score += 1
        if signals.estimated_users < 100:
            simple_score += 1

        # MEDIUM signals
        if 4 <= signals.estimated_modules <= 8:
            medium_score += 3
        if 2000 <= signals.estimated_loc <= 10000:
            medium_score += 2
        if signals.stack_count == 2:
            medium_score += 2
        if 1 <= len(signals.external_integrations) <= 3:
            medium_score += 2
        if signals.auth_complexity == "moderate":
            medium_score += 1
        if 100 <= signals.estimated_users < 10000:
            medium_score += 1

        # COMPLEX signals
        if signals.estimated_modules > 8:
            complex_score += 3
        if signals.estimated_loc > 10000:
            complex_score += 3
        if signals.stack_count > 2:
            complex_score += 2
        if len(signals.external_integrations) > 3:
            complex_score += 2
        if signals.requires_realtime:
            complex_score += 2
        if signals.requires_multi_tenant:
            complex_score += 2
        if len(signals.requires_compliance) > 0:
            complex_score += 3
        if signals.auth_complexity == "complex":
            complex_score += 2
        if signals.estimated_users >= 10000:
            complex_score += 2
        if signals.regulated_industry:
            complex_score += 2
        if signals.handles_sensitive_data:
            complex_score += 1
        if signals.complex_workflows:
            complex_score += 1

        return {
            "simple": simple_score,
            "medium": medium_score,
            "complex": complex_score,
        }

    def _determine_level(self, scores: dict[str, int]) -> ComplexityLevel:
        # Never underestimate: if complex score is high, it's complex
        if scores["complex"] >= 6:
            return ComplexityLevel.COMPLEX

        # Medium beats simple by a clear margin
        if scores["medium"] > scores["simple"] + 2:
            return ComplexityLevel.MEDIUM

        # Tie between medium and complex → be conservative
        if abs(scores["medium"] - scores["complex"]) <= 2 and scores["complex"] >= 4:
            return ComplexityLevel.COMPLEX

        # Default to the highest scorer
        return ComplexityLevel(max(scores, key=lambda k: scores[k]))

    def _apply_minimum_level(
        self, level: ComplexityLevel, signals: ComplexitySignals
    ) -> ComplexityLevel:
        """Enforce minimum complexity for non-negotiable signals.

        Regulated industries must be at least MEDIUM regardless of size,
        because compliance constraints affect architecture even for small projects.
        """
        if signals.regulated_industry and level == ComplexityLevel.SIMPLE:
            return ComplexityLevel.MEDIUM
        if signals.requires_compliance and level == ComplexityLevel.SIMPLE:
            return ComplexityLevel.MEDIUM
        return level

    def _build_reasoning(
        self,
        signals: ComplexitySignals,
        scores: dict[str, int],
        level: ComplexityLevel,
    ) -> str:
        lines: list[str] = [
            f"Proyecto clasificado como {level.value}",
            f"Scores: {scores}",
        ]

        if level == ComplexityLevel.SIMPLE:
            lines += [
                "Factores principales:",
                f"- Módulos estimados: {signals.estimated_modules}",
                f"- Integraciones externas: {len(signals.external_integrations)}",
                "- Sin requisitos especiales",
            ]
        elif level == ComplexityLevel.MEDIUM:
            lines += [
                "Factores principales:",
                f"- Módulos estimados: {signals.estimated_modules}",
                f"- {len(signals.external_integrations)} integraciones externas",
                f"- Complejidad de autenticación: {signals.auth_complexity}",
            ]
        else:
            lines.append("Factores principales:")
            if signals.requires_compliance:
                lines.append(f"- Compliance requerido: {signals.requires_compliance}")
            if signals.requires_multi_tenant:
                lines.append("- Multi-tenant")
            if signals.requires_realtime:
                lines.append("- Tiempo real")
            lines.append(f"- {signals.estimated_modules} módulos estimados")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Model selector (public helper)
# ---------------------------------------------------------------------------

def select_model_for_architect(
    complexity: ComplexityLevel,
    user_override: ComplexityLevel | None = None,
) -> str:
    """Return the model ID to use for the Architect."""
    final_level = user_override if user_override is not None else complexity
    return MODEL_ASSIGNMENT_BY_COMPLEXITY[final_level.value]
