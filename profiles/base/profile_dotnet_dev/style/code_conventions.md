# .NET Developer Code Conventions

- PascalCase for everything public; camelCase with underscore prefix for private fields (`_service`)
- Record types for DTOs; classes for entities with EF Core
- Repository pattern optional for simple projects; service layer always present
- Use `IOptions<T>` for configuration binding — never read config directly in business logic
- Global exception handling with middleware; problem details format (RFC 7807)
- XML docs on public API methods; Swagger/OpenAPI auto-generated
