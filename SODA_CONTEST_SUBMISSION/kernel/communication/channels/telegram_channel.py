from __future__ import annotations

from kernel.communication.telegram_gateway import TelegramGateway


class TelegramChannel:
    """Thin channel adapter for Telegram transport."""

    def __init__(self):
        self.gateway = TelegramGateway()

    async def send(self, text: str) -> bool:
        return await self.gateway.send(text)
