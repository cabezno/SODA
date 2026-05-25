## Repository Pattern — C# / Entity Framework Core

### Complete template

```csharp
using Microsoft.EntityFrameworkCore;

// ── Domain model ──────────────────────────────────────────────────────────────

public record User
{
    public string Id { get; init; } = Guid.NewGuid().ToString();
    public string Email { get; init; } = string.Empty;
    public string Name { get; init; } = string.Empty;
    public DateTime CreatedAt { get; init; } = DateTime.UtcNow;
}

// ── Interface (storage-agnostic) ──────────────────────────────────────────────

public interface IUserRepository
{
    Task<User?> FindByIdAsync(string id);
    Task<User?> FindByEmailAsync(string email);
    Task SaveAsync(User user);
    Task DeleteAsync(string id);
    Task<IReadOnlyList<User>> FindAllAsync();
}

// ── DbContext ─────────────────────────────────────────────────────────────────

public class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public DbSet<User> Users => Set<User>();

    protected override void OnModelCreating(ModelBuilder model)
    {
        model.Entity<User>(e =>
        {
            e.HasKey(u => u.Id);
            e.HasIndex(u => u.Email).IsUnique();
            e.Property(u => u.Email).IsRequired();
        });
    }
}

// ── Concrete implementation (EF Core) ─────────────────────────────────────────

public class EfUserRepository(AppDbContext db) : IUserRepository
{
    public async Task<User?> FindByIdAsync(string id) =>
        await db.Users.FindAsync(id);

    public async Task<User?> FindByEmailAsync(string email) =>
        await db.Users.FirstOrDefaultAsync(u => u.Email == email);

    public async Task SaveAsync(User user)
    {
        var existing = await db.Users.FindAsync(user.Id);
        if (existing is null)
            db.Users.Add(user);
        else
            db.Entry(existing).CurrentValues.SetValues(user);
        await db.SaveChangesAsync();
    }

    public async Task DeleteAsync(string id)
    {
        var user = await db.Users.FindAsync(id);
        if (user is not null)
        {
            db.Users.Remove(user);
            await db.SaveChangesAsync();
        }
    }

    public async Task<IReadOnlyList<User>> FindAllAsync() =>
        await db.Users.OrderBy(u => u.CreatedAt).ToListAsync();
}
```

### SQLite (no ORM, raw ADO.NET)

```csharp
using Microsoft.Data.Sqlite;

public class SqliteUserRepository : IUserRepository
{
    private readonly string _connectionString;

    public SqliteUserRepository(string dbPath)
    {
        _connectionString = $"Data Source={dbPath}";
        EnsureSchema();
    }

    private void EnsureSchema()
    {
        using var conn = new SqliteConnection(_connectionString);
        conn.Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL, created_at TEXT NOT NULL
            )
        """;
        cmd.ExecuteNonQuery();
    }

    public async Task<User?> FindByIdAsync(string id)
    {
        await using var conn = new SqliteConnection(_connectionString);
        await conn.OpenAsync();
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT id, email, name, created_at FROM users WHERE id = $id";
        cmd.Parameters.AddWithValue("$id", id);
        await using var reader = await cmd.ExecuteReaderAsync();
        return await reader.ReadAsync() ? ReadUser(reader) : null;
    }

    public async Task SaveAsync(User user)
    {
        await using var conn = new SqliteConnection(_connectionString);
        await conn.OpenAsync();
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO users (id, email, name, created_at) VALUES ($id,$email,$name,$ca)
            ON CONFLICT(id) DO UPDATE SET email=excluded.email, name=excluded.name
        """;
        cmd.Parameters.AddWithValue("$id", user.Id);
        cmd.Parameters.AddWithValue("$email", user.Email);
        cmd.Parameters.AddWithValue("$name", user.Name);
        cmd.Parameters.AddWithValue("$ca", user.CreatedAt.ToString("o"));
        await cmd.ExecuteNonQueryAsync();
    }

    private static User ReadUser(SqliteDataReader r) => new()
    {
        Id = r.GetString(0), Email = r.GetString(1),
        Name = r.GetString(2), CreatedAt = DateTime.Parse(r.GetString(3))
    };

    // FindByEmailAsync, DeleteAsync, FindAllAsync follow same pattern
}
```

### Dependency injection (Program.cs)

```csharp
builder.Services.AddDbContext<AppDbContext>(opt =>
    opt.UseSqlite("Data Source=app.db"));

builder.Services.AddScoped<IUserRepository, EfUserRepository>();
// Or for raw ADO.NET:
// builder.Services.AddSingleton<IUserRepository>(_ => new SqliteUserRepository("app.db"));
```
