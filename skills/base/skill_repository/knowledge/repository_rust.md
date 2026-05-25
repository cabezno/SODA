## Repository Pattern — Rust / SQLx

### Complete template

```rust
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use sqlx::{FromRow, SqlitePool};
use uuid::Uuid;

// ── Domain model ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, FromRow)]
pub struct User {
    pub id: String,
    pub email: String,
    pub name: String,
    pub created_at: DateTime<Utc>,
}

impl User {
    pub fn new(email: impl Into<String>, name: impl Into<String>) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            email: email.into(),
            name: name.into(),
            created_at: Utc::now(),
        }
    }
}

// ── Interface (storage-agnostic) ──────────────────────────────────────────────

#[async_trait]
pub trait UserRepository: Send + Sync {
    async fn find_by_id(&self, id: &str) -> anyhow::Result<Option<User>>;
    async fn find_by_email(&self, email: &str) -> anyhow::Result<Option<User>>;
    async fn save(&self, user: &User) -> anyhow::Result<()>;
    async fn delete(&self, id: &str) -> anyhow::Result<()>;
    async fn find_all(&self) -> anyhow::Result<Vec<User>>;
}

// ── Concrete implementation ───────────────────────────────────────────────────

pub struct SqliteUserRepository {
    pool: SqlitePool,
}

impl SqliteUserRepository {
    pub async fn new(database_url: &str) -> anyhow::Result<Self> {
        let pool = SqlitePool::connect(database_url).await?;
        let repo = Self { pool };
        repo.ensure_schema().await?;
        Ok(repo)
    }

    async fn ensure_schema(&self) -> anyhow::Result<()> {
        sqlx::query(
            "CREATE TABLE IF NOT EXISTS users (
                id         TEXT PRIMARY KEY,
                email      TEXT UNIQUE NOT NULL,
                name       TEXT NOT NULL,
                created_at TEXT NOT NULL
            )",
        )
        .execute(&self.pool)
        .await?;
        Ok(())
    }
}

#[async_trait]
impl UserRepository for SqliteUserRepository {
    async fn find_by_id(&self, id: &str) -> anyhow::Result<Option<User>> {
        let user = sqlx::query_as::<_, User>(
            "SELECT id, email, name, created_at FROM users WHERE id = ?",
        )
        .bind(id)
        .fetch_optional(&self.pool)
        .await?;
        Ok(user)
    }

    async fn find_by_email(&self, email: &str) -> anyhow::Result<Option<User>> {
        let user = sqlx::query_as::<_, User>(
            "SELECT id, email, name, created_at FROM users WHERE email = ?",
        )
        .bind(email)
        .fetch_optional(&self.pool)
        .await?;
        Ok(user)
    }

    async fn save(&self, user: &User) -> anyhow::Result<()> {
        sqlx::query(
            "INSERT INTO users (id, email, name, created_at) VALUES (?, ?, ?, ?)
             ON CONFLICT(id) DO UPDATE SET email=excluded.email, name=excluded.name",
        )
        .bind(&user.id)
        .bind(&user.email)
        .bind(&user.name)
        .bind(user.created_at.to_rfc3339())
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    async fn delete(&self, id: &str) -> anyhow::Result<()> {
        sqlx::query("DELETE FROM users WHERE id = ?")
            .bind(id)
            .execute(&self.pool)
            .await?;
        Ok(())
    }

    async fn find_all(&self) -> anyhow::Result<Vec<User>> {
        let users = sqlx::query_as::<_, User>(
            "SELECT id, email, name, created_at FROM users ORDER BY created_at",
        )
        .fetch_all(&self.pool)
        .await?;
        Ok(users)
    }
}
```

### Dependency injection (main.rs)

```rust
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let repo: Arc<dyn UserRepository> = Arc::new(
        SqliteUserRepository::new("sqlite://app.db").await?
    );
    let service = UserService::new(repo);
    // pass service to handlers
    Ok(())
}
```

### Cargo.toml dependencies

```toml
[dependencies]
sqlx = { version = "0.7", features = ["sqlite", "runtime-tokio", "chrono"] }
async-trait = "0.1"
tokio = { version = "1", features = ["full"] }
anyhow = "1"
uuid = { version = "1", features = ["v4"] }
chrono = { version = "0.4", features = ["serde"] }
```
