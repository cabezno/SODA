from abc import ABC, abstractmethod
from typing import Optional


# Events that are forwarded to external channels
EXTERNAL_EVENTS = {
    "START", "DONE", "FAILED", "CHECKPOINT",
    "HEALTH_WARN", "WISDOM", "BRANCH_CREATED", "EVOLUTION",
    "USER_QUESTION",
}


class MessagingGateway(ABC):
    """Base class for all external communication channels."""

    @abstractmethod
    async def send(self, message: str, data: Optional[dict] = None) -> bool:
        """Send a message. Returns True if delivered."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the channel has valid credentials."""

    def should_forward(self, event_type: str) -> bool:
        return event_type in EXTERNAL_EVENTS

    def format_event(self, event_type: str, message: str, data: Optional[dict] = None) -> str:
        icons = {
            "START":         "[>>]",
            "DONE":          "[OK]",
            "FAILED":        "[!!]",
            "CHECKPOINT":    "[CP]",
            "HEALTH_WARN":   "[HL]",
            "WISDOM":        "[WS]",
            "BRANCH_CREATED":"[BR]",
            "EVOLUTION":     "[EV]",
            "USER_QUESTION": "[?]",
        }
        icon = icons.get(event_type, "[--]")
        return f"SODA {icon} {message}"
