from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ExternalToolDefinition:
    key: str
    name: str
    provider: str
    category: str
    auth: str
    description: str
    capabilities: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["capabilities"] = list(self.capabilities)
        return data


class ExternalToolRegistry:
    """Closed catalog of external APIs and services SODA can reason about."""

    def __init__(self):
        self._tools = {
            tool.key: tool
            for tool in (
                ExternalToolDefinition(
                    key="google_calendar",
                    name="Google Calendar",
                    provider="Google",
                    category="productivity",
                    auth="oauth2",
                    description="Calendar events, availability, and reminders.",
                    capabilities=("calendar.read", "calendar.write", "scheduling"),
                ),
                ExternalToolDefinition(
                    key="github",
                    name="GitHub",
                    provider="GitHub",
                    category="developer",
                    auth="token",
                    description="Repositories, issues, pull requests, and automation hooks.",
                    capabilities=("repo.read", "repo.write", "issues", "pull_requests"),
                ),
                ExternalToolDefinition(
                    key="telegram_bot",
                    name="Telegram Bot API",
                    provider="Telegram",
                    category="communication",
                    auth="bot_token",
                    description="Bot messaging, notifications, and command workflows.",
                    capabilities=("messaging", "notifications", "bot_commands"),
                ),
            )
        }

    def list_tools(self, category: str | None = None, capability: str | None = None) -> list[dict]:
        tools = list(self._tools.values())
        if category:
            normalized = category.strip().lower()
            tools = [tool for tool in tools if tool.category.lower() == normalized]
        if capability:
            normalized = capability.strip().lower()
            tools = [
                tool for tool in tools
                if any(item.lower() == normalized for item in tool.capabilities)
            ]
        return [tool.to_dict() for tool in sorted(tools, key=lambda item: item.key)]

    def get_tool(self, key: str) -> dict:
        normalized = (key or "").strip().lower()
        if normalized not in self._tools:
            raise KeyError(f"Unknown external tool: {key}")
        return self._tools[normalized].to_dict()