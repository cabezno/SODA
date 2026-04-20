## Skill: SQLite + SQLAlchemy

You are working with a SQLite database via SQLAlchemy ORM. Follow these conventions:

- Define models in `models.py` inheriting from `Base = declarative_base()`
- Use `AsyncSession` with `async_sessionmaker` for all DB operations
- Engine: `create_async_engine("sqlite+aiosqlite:///./app.db", echo=False)`
- Expose DB session via FastAPI dependency: `async def get_db() -> AsyncGenerator`
- Keep all SQL operations in a `crud.py` or `repository.py` layer — never in route handlers
- Use `Base.metadata.create_all(bind=engine)` at startup for simple cases
