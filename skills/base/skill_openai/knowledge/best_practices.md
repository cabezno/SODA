# OpenAI API Best Practices

## Client initialization
```python
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
```

## Chat completion
```python
response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user_message},
    ],
    max_tokens=1024,
    temperature=0.7,
)
reply = response.choices[0].message.content
```

## Streaming response
```python
stream = await client.chat.completions.create(
    model="gpt-4o", messages=messages, stream=True
)
async for chunk in stream:
    delta = chunk.choices[0].delta.content or ""
    yield delta
```

## Embeddings
```python
resp = await client.embeddings.create(
    model="text-embedding-3-small", input=text
)
vector = resp.data[0].embedding
```

## Error handling
```python
import openai

try:
    response = await client.chat.completions.create(...)
except openai.RateLimitError:
    await asyncio.sleep(60)
    # retry
except openai.APIConnectionError as e:
    raise RuntimeError(f"OpenAI connection failed: {e}")
except openai.AuthenticationError:
    raise RuntimeError("Invalid OPENAI_API_KEY")
```

## Cost-aware model selection
- `gpt-4o-mini`: fast, cheap, good for classification/simple tasks
- `gpt-4o`: balanced quality and cost, best for general use
- `o1-mini` / `o1`: reasoning tasks, complex analysis
- Embeddings: `text-embedding-3-small` (cheaper) or `text-embedding-3-large` (better)
