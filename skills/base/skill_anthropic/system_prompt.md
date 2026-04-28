## Skill: Anthropic Claude API

You are building an application that integrates with the Anthropic Claude API. Follow these conventions:

- Use the `anthropic` Python package (`pip install anthropic`), import `import anthropic`
- Always use async client: `client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))`
- Default model: `claude-sonnet-4-6` for quality, `claude-haiku-4-5-20251001` for speed/cost
- Messages API: `await client.messages.create(model=..., max_tokens=..., messages=[...])`
- System prompt goes as `system=` kwarg, NOT inside `messages`
- Streaming: use `async with client.messages.stream(...) as stream:` then `async for text in stream.text_stream`
- Tool use: pass `tools=[{"name": ..., "description": ..., "input_schema": {...}}]`, check `stop_reason == "tool_use"`
- Vision: include `{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":"..."}}` in content list
- Handle `anthropic.RateLimitError`, `anthropic.APIConnectionError`, `anthropic.AuthenticationError`
- Never hardcode API keys — always use env vars or `.env` via `python-dotenv`
