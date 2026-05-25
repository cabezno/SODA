## Skill: Inter-Service Integration

You are implementing a module that communicates with other services via HTTP.

**Rule 1 — Always wrap HTTP calls in a typed client class.**
Never call `requests.get()` or `fetch()` inline in business logic. Create a `ServiceNameClient` class.

**Rule 2 — Define typed request/response models.**
Every API call must have input and output types — no raw dicts flowing through the system.

**Rule 3 — Handle errors at the boundary.**
Catch HTTP errors, timeouts, and connection errors at the client level. Raise domain exceptions, not HTTP exceptions.

**Rule 4 — Set explicit timeouts.**
Every HTTP call must have a timeout. Default: 10s for read, 5s for connect.

**Rule 5 — Retry on transient failures only.**
Retry on 5xx and connection errors. Never retry on 4xx (client error — retrying won't help).

**Rule 6 — Configuration via constructor injection.**
Base URL, API keys, and timeouts are injected at construction — not read from env inside methods.
