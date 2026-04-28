## Skill: C# .NET 8

You are building a C# .NET 8 application. Follow these conventions:

### CRITICAL — project file
**Every .NET project MUST include a `.csproj` file as the very first file in `archivos_principales`.**
Without it `dotnet run` cannot execute.

- **Console app**: `<OutputType>Exe</OutputType>`, `<TargetFramework>net8.0</TargetFramework>`
- **WinForms app**: `<OutputType>WinExe</OutputType>`, `<TargetFramework>net8.0-windows</TargetFramework>`, `<UseWindowsForms>true</UseWindowsForms>`
- **Web API**: `<TargetFramework>net8.0</TargetFramework>` (no OutputType needed)
- Always add `<Nullable>enable</Nullable>` and `<ImplicitUsings>enable</ImplicitUsings>`
- NuGet packages → `<PackageReference Include="..." Version="..."/>`

### Architecture
- Use minimal API (`app.MapGet/Post/Put/Delete`) for simple projects; Controllers for complex ones
- Entity Framework Core for data access; `DbContext` in `Data/AppDbContext.cs`
- Use `record` types for DTOs (immutable by default)
- Dependency injection via constructor; register services in `Program.cs`
- `appsettings.json` and `appsettings.Development.json` for configuration
- Async all the way: `async Task<IActionResult>` or `async Task<T>`
- `ILogger<T>` for logging, never `Console.Write`
- `dotnet run` to start; `dotnet build` to compile
