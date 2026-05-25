## HTTP Client Templates

### Python — httpx async client

```python
import httpx
from dataclasses import dataclass
from typing import Optional


class ServiceError(Exception):
    """Domain exception for inter-service communication failures."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class CreateOrderRequest:
    user_id: str
    items: list[dict]

@dataclass
class CreateOrderResponse:
    order_id: str
    status: str
    total: float


class OrderServiceClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0):
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._timeout = httpx.Timeout(connect=5.0, read=timeout)

    async def create_order(self, req: CreateOrderRequest) -> CreateOrderResponse:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/orders",
                    json={"user_id": req.user_id, "items": req.items},
                    headers=self._headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return CreateOrderResponse(**data)
            except httpx.HTTPStatusError as e:
                raise ServiceError(f"Order service error: {e.response.text}", e.response.status_code)
            except httpx.TimeoutException:
                raise ServiceError("Order service timed out")
            except httpx.RequestError as e:
                raise ServiceError(f"Order service unreachable: {e}")
```

### TypeScript — fetch with typed client

```typescript
export class ServiceError extends Error {
  constructor(message: string, public readonly statusCode?: number) {
    super(message);
  }
}

interface CreateOrderRequest {
  userId: string;
  items: Array<{ productId: string; quantity: number }>;
}

interface CreateOrderResponse {
  orderId: string;
  status: string;
  total: number;
}

export class OrderServiceClient {
  constructor(
    private readonly baseUrl: string,
    private readonly apiKey: string,
    private readonly timeoutMs: number = 10_000
  ) {}

  async createOrder(req: CreateOrderRequest): Promise<CreateOrderResponse> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const resp = await fetch(`${this.baseUrl}/orders`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(req),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const text = await resp.text();
        throw new ServiceError(`Order service error: ${text}`, resp.status);
      }

      return resp.json() as Promise<CreateOrderResponse>;
    } catch (err) {
      if (err instanceof ServiceError) throw err;
      if ((err as Error).name === "AbortError") throw new ServiceError("Order service timed out");
      throw new ServiceError(`Order service unreachable: ${(err as Error).message}`);
    } finally {
      clearTimeout(timer);
    }
  }
}
```

### Retry utility (language-agnostic logic)

```python
import asyncio
from typing import TypeVar, Callable, Awaitable

T = TypeVar("T")

async def with_retry(
    fn: Callable[[], Awaitable[T]],
    max_attempts: int = 3,
    backoff_s: float = 1.0,
    retryable_codes: tuple = (500, 502, 503, 504),
) -> T:
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except ServiceError as e:
            if e.status_code and e.status_code not in retryable_codes:
                raise  # 4xx — do not retry
            last_exc = e
            if attempt < max_attempts - 1:
                await asyncio.sleep(backoff_s * (2 ** attempt))
    raise last_exc
```
