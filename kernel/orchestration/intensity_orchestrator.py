from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class IntensityProfile:
    level: int
    label: str
    parallel_agents: int
    review_required: bool
    arbiter_required: bool

    def to_dict(self) -> dict:
        return asdict(self)


class IntensityOrchestrator:
    """Selects execution intensity profile based on request complexity."""

    MEDIUM_KEYWORDS = (
        "api", "crud", "dashboard", "integration", "notifications", "admin panel",
        "fullstack", "full stack", "frontend", "backend", "react", "nextjs", "next.js",
        "fastapi", "django", "express", "database", "sqlite", "postgres", "mysql",
    )
    HIGH_KEYWORDS = (
        "auth", "oauth", "jwt", "payment", "stripe", "mercadopago", "websocket",
        "queue", "docker", "microservice", "multi service", "ci/cd",
        "celery", "redis", "cache", "search", "elasticsearch", "s3", "storage",
        "llm", "openai", "gemini", "claude", "ai", "ml", "embedding", "vector",
        "agent", "pipeline", "workflow", "scheduler", "cron",
    )
    CRITICAL_KEYWORDS = (
        "multitenant", "multi-tenant", "compliance", "pci", "kubernetes",
        "high availability", "event-driven", "distributed", "audit",
        "soda", "multi-agent", "multiagent", "orchestrator", "saas",
        "real-time", "realtime", "streaming", "pubsub", "pub/sub",
    )

    def choose_profile(self, request_text: str) -> IntensityProfile:
        score = self._score_request(request_text)
        if score <= 0:
            return IntensityProfile(1, "low", 1, False, False)
        if score <= 2:
            return IntensityProfile(2, "medium", 2, False, False)
        if score <= 4:
            return IntensityProfile(3, "high", 2, True, False)
        return IntensityProfile(4, "critical", 3, True, True)

    def choose_level(self, request_text: str) -> str:
        return self.choose_profile(request_text).label

    def choose_execution_level(self, request_text: str) -> int:
        return self.choose_profile(request_text).level

    def _score_request(self, request_text: str) -> int:
        text = (request_text or "").strip().lower()
        score = 0
        length = len(text)

        if length >= 120:
            score += 1
        if length >= 500:
            score += 2
        if any(keyword in text for keyword in self.MEDIUM_KEYWORDS):
            score += 1
        if any(keyword in text for keyword in self.HIGH_KEYWORDS):
            score += 2
        if any(keyword in text for keyword in self.CRITICAL_KEYWORDS):
            score += 3
        return score
