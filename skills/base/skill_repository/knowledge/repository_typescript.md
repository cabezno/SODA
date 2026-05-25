## Repository Pattern — TypeScript / better-sqlite3

### Complete template

```typescript
import Database from "better-sqlite3";

// ── Domain model ─────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  name: string;
  createdAt: string;
}

// ── Interface (storage-agnostic) ──────────────────────────────────────────────

export interface IUserRepository {
  findById(id: string): User | undefined;
  findByEmail(email: string): User | undefined;
  save(user: User): void;
  delete(id: string): void;
  findAll(): User[];
}

// ── Concrete implementation ───────────────────────────────────────────────────

export class SqliteUserRepository implements IUserRepository {
  private db: Database.Database;

  constructor(dbPath: string) {
    this.db = new Database(dbPath);
    this.ensureSchema();
  }

  private ensureSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL
      )
    `);
  }

  findById(id: string): User | undefined {
    const row = this.db
      .prepare("SELECT * FROM users WHERE id = ?")
      .get(id) as any;
    return row ? this.toModel(row) : undefined;
  }

  findByEmail(email: string): User | undefined {
    const row = this.db
      .prepare("SELECT * FROM users WHERE email = ?")
      .get(email) as any;
    return row ? this.toModel(row) : undefined;
  }

  save(user: User): void {
    this.db
      .prepare(
        `INSERT INTO users (id, email, name, created_at)
         VALUES (@id, @email, @name, @createdAt)
         ON CONFLICT(id) DO UPDATE SET
           email = excluded.email,
           name  = excluded.name`
      )
      .run(user);
  }

  delete(id: string): void {
    this.db.prepare("DELETE FROM users WHERE id = ?").run(id);
  }

  findAll(): User[] {
    return (
      this.db
        .prepare("SELECT * FROM users ORDER BY created_at")
        .all() as any[]
    ).map(this.toModel);
  }

  private toModel(row: any): User {
    return {
      id: row.id,
      email: row.email,
      name: row.name,
      createdAt: row.created_at,
    };
  }
}
```

### With Prisma ORM

```typescript
import { PrismaClient, User as PrismaUser } from "@prisma/client";

export class PrismaUserRepository implements IUserRepository {
  constructor(private prisma: PrismaClient) {}

  async findById(id: string): Promise<User | undefined> {
    const row = await this.prisma.user.findUnique({ where: { id } });
    return row ?? undefined;
  }

  async save(user: User): Promise<void> {
    await this.prisma.user.upsert({
      where: { id: user.id },
      update: { email: user.email, name: user.name },
      create: user,
    });
  }

  async delete(id: string): Promise<void> {
    await this.prisma.user.delete({ where: { id } });
  }

  async findAll(): Promise<User[]> {
    return this.prisma.user.findMany({ orderBy: { createdAt: "asc" } });
  }
}
```

### Dependency injection pattern (Express/Fastify)

```typescript
// Compose at the application entry-point, not inside services
const db = new Database("./app.db");
const userRepo: IUserRepository = new SqliteUserRepository("./app.db");
const userService = new UserService(userRepo);
app.use("/users", createUserRouter(userService));
```
