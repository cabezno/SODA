## Skill: Repository Pattern

You are implementing a data-access module. Apply the Repository pattern strictly:

**Rule 1 — Always create two artifacts:**
1. An **interface** (protocol / abstract class / interface) defining the contract: `IUserRepository`, `IProductRepository`
2. A **concrete implementation** bound to the actual storage: `SqliteUserRepository`, `PostgresUserRepository`

**Rule 2 — NEVER use in-memory Maps/dicts as permanent storage.**
`new Map<string, User>()` or `users: dict = {}` are only valid for caches or tests — never as the primary data store.

**Rule 3 — Keep the interface storage-agnostic.**
The interface must not import or reference any database library. Only the concrete class does.

**Rule 4 — Name the interface methods by operation, not by technology:**
- ✓ `find_by_id`, `save`, `delete`, `find_all`, `find_by_email`
- ✗ `execute_query`, `run_sql`, `fetch_rows`

**Rule 5 — Constructor injection.**
The concrete class receives the DB connection/session in `__init__`. Do not use globals or singletons.

```python
# Correct structure (Python)
class IUserRepository(Protocol):
    def find_by_id(self, user_id: str) -> Optional[User]: ...
    def save(self, user: User) -> None: ...
    def delete(self, user_id: str) -> None: ...
    def find_all(self) -> list[User]: ...

class SqliteUserRepository:
    def __init__(self, db_path: str): ...
    def find_by_id(self, user_id: str) -> Optional[User]: ...
    # ... all interface methods implemented
```
