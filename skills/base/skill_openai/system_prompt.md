## Skill: OpenAI API

You are building an application that integrates with the OpenAI API. Follow these conventions:

- Use the `openai` Python package (`pip install openai`), import `from openai import AsyncOpenAI`
- Always use the async client (`AsyncOpenAI`) in async contexts; use `OpenAI` only for simple scripts
- Load the API key from environment: `client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))`
- Default model for chat: `gpt-4o` for quality, `gpt-4o-mini` for speed/cost
- Default model for embeddings: `text-embedding-3-small`
- Chat completions: `await client.chat.completions.create(model=..., messages=[...])`
- Streaming: set `stream=True`, iterate `async for chunk in response`
- Function/tool calling: pass `tools=[{"type":"function","function":{...}}]`, check `finish_reason == "tool_calls"`
- Always handle `openai.RateLimitError`, `openai.APIConnectionError` with retry logic
- Store conversation history as a list of `{"role": "user"|"assistant"|"system", "content": "..."}`
- Never hardcode API keys — always use env vars or `.env` via `python-dotenv`
