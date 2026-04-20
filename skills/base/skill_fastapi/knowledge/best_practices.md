# FastAPI Best Practices

- Split into: `main.py`, `routers/`, `models/`, `schemas/`, `crud/`, `dependencies.py`, `config.py`
- Never put business logic in route handlers — delegate to service/crud layer
- Use `settings = Settings()` from `pydantic-settings` for config, never hardcode
- Enable CORS only for known origins in production
- Always validate path/query parameters via function signatures (FastAPI does it automatically)
- Use background tasks (`BackgroundTasks`) for fire-and-forget work, not asyncio.create_task
