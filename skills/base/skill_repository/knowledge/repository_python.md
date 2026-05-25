## Repository Pattern — Python / SQLite

### Complete template (sqlite3, no ORM)

```python
from __future__ import annotations
import sqlite3
from dataclasses import dataclass, asdict
from typing import Optional, Protocol
from pathlib import Path


# ── Domain model ─────────────────────────────────────────────────────────────

@dataclass
class User:
    id: str
    email: str
    name: str
    created_at: str


# ── Interface (storage-agnostic) ──────────────────────────────────────────────

class IUserRepository(Protocol):
    def find_by_id(self, user_id: str) -> Optional[User]: ...
    def find_by_email(self, email: str) -> Optional[User]: ...
    def save(self, user: User) -> None: ...
    def delete(self, user_id: str) -> None: ...
    def find_all(self) -> list[User]: ...


# ── Concrete implementation ───────────────────────────────────────────────────

class SqliteUserRepository:
    """SQLite-backed implementation of IUserRepository."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def find_by_id(self, user_id: str) -> Optional[User]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return User(**dict(row)) if row else None

    def find_by_email(self, email: str) -> Optional[User]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
        return User(**dict(row)) if row else None

    def save(self, user: User) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO users (id, email, name, created_at)
                   VALUES (:id, :email, :name, :created_at)
                   ON CONFLICT(id) DO UPDATE SET
                     email=excluded.email,
                     name=excluded.name""",
                asdict(user)
            )

    def delete(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    def find_all(self) -> list[User]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        return [User(**dict(r)) for r in rows]
```

### With SQLAlchemy (async)

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, user_id: str) -> Optional[UserModel]:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        return result.scalar_one_or_none()

    async def save(self, user: UserModel) -> None:
        self._session.add(user)
        await self._session.flush()
```

### Unit of Work (compose multiple repos in one transaction)

```python
class UnitOfWork:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def __enter__(self):
        self._conn = sqlite3.connect(self._db_path)
        self.users = SqliteUserRepository.__new__(SqliteUserRepository)
        self.users._db_path = self._db_path
        return self

    def __exit__(self, exc_type, *_):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()
```
