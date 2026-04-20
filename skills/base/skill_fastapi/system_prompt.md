## Skill: FastAPI

You are building a FastAPI application. Follow these conventions:

- Use `APIRouter` for route grouping, mount routers in `main.py` with prefixes
- All request/response bodies are Pydantic `BaseModel` subclasses
- Use async route handlers (`async def`) throughout
- Dependency injection via `Depends()` for DB sessions, auth, etc.
- Return typed responses — always declare `response_model` on route decorators
- Use `HTTPException` with appropriate status codes, never return raw dicts for errors
- Lifespan events via `@asynccontextmanager` on `app = FastAPI(lifespan=lifespan)`
