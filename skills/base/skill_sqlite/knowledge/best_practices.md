# SQLite + SQLAlchemy Best Practices

- One `AsyncSession` per request — inject via `Depends(get_db)`, never reuse across requests
- Use `select()` from `sqlalchemy` for queries, avoid raw SQL strings
- Always `await session.commit()` after writes, `await session.refresh(obj)` to get DB defaults
- For bulk inserts use `session.add_all([...])` not individual adds
- Add indexes on columns used in WHERE clauses or FK relationships
- SQLite WAL mode improves concurrent read performance: `PRAGMA journal_mode=WAL`
