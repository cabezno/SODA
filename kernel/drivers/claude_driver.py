import os
import anthropic

class ClaudeDriver:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = "claude-sonnet-4-6"

    async def prompt(self, system: str, user: str):
        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": user}]
            )
            return message.content[0].text
        except Exception as e:
            return f"Error en Claude Driver: {str(e)}"