## Repository Pattern — Go / database/sql

### Complete template

```go
package repository

import (
	"database/sql"
	"errors"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// ── Domain model ──────────────────────────────────────────────────────────────

type User struct {
	ID        string
	Email     string
	Name      string
	CreatedAt time.Time
}

// ── Interface (storage-agnostic) ──────────────────────────────────────────────

type UserRepository interface {
	FindByID(id string) (*User, error)
	FindByEmail(email string) (*User, error)
	Save(user *User) error
	Delete(id string) error
	FindAll() ([]*User, error)
}

// ── Concrete implementation ───────────────────────────────────────────────────

type SQLiteUserRepository struct {
	db *sql.DB
}

func NewSQLiteUserRepository(dbPath string) (*SQLiteUserRepository, error) {
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, err
	}
	repo := &SQLiteUserRepository{db: db}
	if err := repo.ensureSchema(); err != nil {
		return nil, err
	}
	return repo, nil
}

func (r *SQLiteUserRepository) ensureSchema() error {
	_, err := r.db.Exec(`
		CREATE TABLE IF NOT EXISTS users (
			id         TEXT PRIMARY KEY,
			email      TEXT UNIQUE NOT NULL,
			name       TEXT NOT NULL,
			created_at TEXT NOT NULL
		)
	`)
	return err
}

func (r *SQLiteUserRepository) FindByID(id string) (*User, error) {
	row := r.db.QueryRow("SELECT id, email, name, created_at FROM users WHERE id = ?", id)
	return r.scanUser(row)
}

func (r *SQLiteUserRepository) FindByEmail(email string) (*User, error) {
	row := r.db.QueryRow("SELECT id, email, name, created_at FROM users WHERE email = ?", email)
	return r.scanUser(row)
}

func (r *SQLiteUserRepository) Save(user *User) error {
	_, err := r.db.Exec(
		`INSERT INTO users (id, email, name, created_at) VALUES (?, ?, ?, ?)
		 ON CONFLICT(id) DO UPDATE SET email=excluded.email, name=excluded.name`,
		user.ID, user.Email, user.Name, user.CreatedAt.Format(time.RFC3339),
	)
	return err
}

func (r *SQLiteUserRepository) Delete(id string) error {
	_, err := r.db.Exec("DELETE FROM users WHERE id = ?", id)
	return err
}

func (r *SQLiteUserRepository) FindAll() ([]*User, error) {
	rows, err := r.db.Query("SELECT id, email, name, created_at FROM users ORDER BY created_at")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var users []*User
	for rows.Next() {
		u, err := r.scanUser(rows)
		if err != nil {
			return nil, err
		}
		users = append(users, u)
	}
	return users, rows.Err()
}

func (r *SQLiteUserRepository) scanUser(scanner interface {
	Scan(...any) error
}) (*User, error) {
	var u User
	var createdAt string
	if err := scanner.Scan(&u.ID, &u.Email, &u.Name, &createdAt); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	u.CreatedAt, _ = time.Parse(time.RFC3339, createdAt)
	return &u, nil
}

func (r *SQLiteUserRepository) Close() error {
	return r.db.Close()
}
```

### Dependency injection (main.go)

```go
func main() {
	repo, err := repository.NewSQLiteUserRepository("./app.db")
	if err != nil {
		log.Fatal(err)
	}
	defer repo.Close()

	svc := service.NewUserService(repo)
	handler := handler.NewUserHandler(svc)
	// ...
}
```

### With pgx (PostgreSQL)

```go
import "github.com/jackc/pgx/v5/pgxpool"

type PgUserRepository struct {
	pool *pgxpool.Pool
}

func NewPgUserRepository(connStr string) (*PgUserRepository, error) {
	pool, err := pgxpool.New(context.Background(), connStr)
	if err != nil {
		return nil, err
	}
	return &PgUserRepository{pool: pool}, nil
}

func (r *PgUserRepository) FindByID(ctx context.Context, id string) (*User, error) {
	row := r.pool.QueryRow(ctx, "SELECT id, email, name, created_at FROM users WHERE id=$1", id)
	var u User
	err := row.Scan(&u.ID, &u.Email, &u.Name, &u.CreatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	return &u, err
}
```
