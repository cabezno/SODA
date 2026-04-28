# Anthropic Claude API Best Practices

## Client initialization
```python
import os
import anthropic
from dotenv import load_dotenv

load_dotenv()
client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
```

## Basic message
```python
message = await client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system="You are a helpful assistant.",
    messages=[{"role": "user", "content": user_message}],
)
reply = message.content[0].text
```

## Streaming
```python
async with client.messages.stream(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=messages,
) as stream:
    async for text in stream.text_stream:
        yield text
```

## Tool use
```python
tools = [{
    "name": "search_web",
    "description": "Search the web for information",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}]

response = await client.messages.create(
    model="claude-sonnet-4-6", max_tokens=1024,
    tools=tools, messages=messages,
)
if response.stop_reason == "tool_use":
    tool_block = next(b for b in response.content if b.type == "tool_use")
    tool_input = tool_block.input  # dict with tool arguments
```

## Model selection
- `claude-haiku-4-5-20251001`: fastest, cheapest — classification, summaries, simple Q&A
- `claude-sonnet-4-6`: balanced — complex reasoning, code generation, analysis
- `claude-opus-4-7`: most capable — intricate tasks, long documents
