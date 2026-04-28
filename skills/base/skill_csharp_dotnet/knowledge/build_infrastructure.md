# Build Infrastructure Checklist — C# ASP.NET Core

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `MyApp.csproj` | Sin el archivo de proyecto, `dotnet build` no puede compilar nada |
| `Program.cs` | Entry point con el Web Application builder; en .NET 6+ reemplaza `Startup.cs` |
| `appsettings.json` | Configuración base de la aplicación |
| `appsettings.Development.json` | Configuración de desarrollo (no sube a producción) |
| `Properties/launchSettings.json` | Sin esto `dotnet run` no sabe en qué puerto arrancar; F5 en VS Code tampoco |
| `.env.example` O `secrets.json.example` | Documenta qué secretos configurar con `dotnet user-secrets` |
| `.gitignore` | Debe excluir `bin/`, `obj/`, `*.user`, `.env`, `secrets.json` |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no compila |
| `.vscode/launch.json` | Sin esto F5 no lanza el debugger C# |
| `.vscode/extensions.json` | Recomienda C# Dev Kit |

## Contenido mínimo de MyApp.csproj

```xml
<Project Sdk="Microsoft.NET.Sdk.Web">

  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <RootNamespace>MyApp</RootNamespace>
    <AssemblyName>MyApp</AssemblyName>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.AspNetCore.OpenApi" Version="8.0.0" />
    <PackageReference Include="Swashbuckle.AspNetCore" Version="6.6.2" />
  </ItemGroup>

</Project>
```

## Contenido mínimo de Program.cs (.NET 8)

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();
app.UseAuthorization();
app.MapControllers();

app.Run();
```

## Contenido de appsettings.json

```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning"
    }
  },
  "AllowedHosts": "*",
  "ConnectionStrings": {
    "DefaultConnection": ""
  }
}
```

## Contenido de appsettings.Development.json

```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Debug",
      "Microsoft.AspNetCore": "Information"
    }
  },
  "ConnectionStrings": {
    "DefaultConnection": "Server=(localdb)\\mssqllocaldb;Database=MyAppDev;Trusted_Connection=true"
  }
}
```

## Contenido de Properties/launchSettings.json

```json
{
  "profiles": {
    "http": {
      "commandName": "Project",
      "dotnetRunMessages": true,
      "launchBrowser": true,
      "launchUrl": "swagger",
      "applicationUrl": "http://localhost:5000",
      "environmentVariables": {
        "ASPNETCORE_ENVIRONMENT": "Development"
      }
    },
    "https": {
      "commandName": "Project",
      "dotnetRunMessages": true,
      "launchBrowser": true,
      "launchUrl": "swagger",
      "applicationUrl": "https://localhost:7000;http://localhost:5000",
      "environmentVariables": {
        "ASPNETCORE_ENVIRONMENT": "Development"
      }
    }
  }
}
```

## .vscode/tasks.json

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "dotnet: build",
      "command": "dotnet",
      "type": "process",
      "args": ["build", "${workspaceFolder}/MyApp.csproj", "/property:GenerateFullPaths=true", "/consoleloggerparameters:NoSummary"],
      "problemMatcher": "$msCompile",
      "group": { "kind": "build", "isDefault": true }
    },
    {
      "label": "dotnet: watch run",
      "command": "dotnet",
      "type": "process",
      "args": ["watch", "run", "--project", "${workspaceFolder}/MyApp.csproj"],
      "problemMatcher": "$msCompile",
      "group": "build",
      "presentation": { "reveal": "always", "panel": "dedicated" }
    },
    {
      "label": "dotnet: test",
      "command": "dotnet",
      "type": "process",
      "args": ["test"],
      "problemMatcher": "$msCompile",
      "group": { "kind": "test", "isDefault": true }
    }
  ]
}
```

## .vscode/launch.json

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": ".NET: Launch (http)",
      "type": "coreclr",
      "request": "launch",
      "preLaunchTask": "dotnet: build",
      "program": "${workspaceFolder}/bin/Debug/net8.0/MyApp.dll",
      "args": [],
      "cwd": "${workspaceFolder}",
      "stopAtEntry": false,
      "serverReadyAction": {
        "action": "openExternally",
        "pattern": "\\bNow listening on:\\s+(https?://\\S+)"
      },
      "env": {
        "ASPNETCORE_ENVIRONMENT": "Development"
      }
    }
  ]
}
```

## .vscode/extensions.json

```json
{
  "recommendations": [
    "ms-dotnettools.csdevkit",
    "ms-dotnettools.csharp",
    "ms-dotnettools.vscode-dotnet-runtime",
    "humao.rest-client"
  ]
}
```

## Pasos que debe ejecutar el usuario para correr el proyecto

1. Instalar .NET 8 SDK (https://dotnet.microsoft.com/download)
2. Restaurar paquetes: `dotnet restore`
3. Configurar secretos: `dotnet user-secrets init && dotnet user-secrets set "ConnectionStrings:DefaultConnection" "..."`
4. Correr: `dotnet run` o en modo watch: `dotnet watch run`
5. Abrir Swagger: https://localhost:7000/swagger

## Build commands

| Acción | Comando |
|--------|---------|
| Restaurar | `dotnet restore` |
| Compilar | `dotnet build` |
| Dev server | `dotnet run` |
| Dev con hot-reload | `dotnet watch run` |
| Producción | `dotnet publish -c Release -o ./publish` |
| Tests | `dotnet test` |
| Tests con coverage | `dotnet test /p:CollectCoverage=true` |

## Reglas del auditor (checklist para código generado)

1. **`TargetFramework` actualizado** — usar `net8.0`; no generar proyectos con `net6.0` o `net7.0` salvo requerimiento explícito
2. **`Properties/launchSettings.json` presente** — sin él `dotnet run` usa puerto aleatorio y F5 no funciona
3. **`Nullable enable` en `.csproj`** — el modo nullable debe estar activado; todos los tipos de referencia que pueden ser null deben declararse con `?`
4. **Dependency Injection en `Program.cs`** — todos los servicios registrados en `builder.Services`; nunca instanciar servicios directamente con `new` en controllers
5. **`appsettings.Development.json` para secretos de dev** — connection strings y API keys nunca en `appsettings.json` base
6. **Controllers con `[ApiController]` y `[Route]`** — ambos atributos son obligatorios para que el routing funcione correctamente y la validación automática funcione
7. **`.csproj` con nombre correcto** — el archivo `.csproj` debe coincidir con el nombre del proyecto/namespace; `dotnet run` busca por nombre

## Errores comunes de generación AI

- Generar `Startup.cs` (patrón de .NET 5 y anteriores) — en .NET 6+ todo va en `Program.cs`
- Olvidar `Properties/launchSettings.json` — el usuario no sabe cómo arrancar y el puerto es aleatorio
- Nombre del `.csproj` que no coincide con el namespace raíz — confunde al compilador y a los imports
- No incluir `SwaggerGen` + `UseSwagger()` — los desarrolladores no tienen forma de probar la API
- Usar `var config = new ConfigurationBuilder()` manual en lugar de `builder.Configuration`
- Olvidar `app.UseAuthorization()` antes de `app.MapControllers()` — los endpoints con `[Authorize]` devuelven 404
- No separar `appsettings.json` de `appsettings.Development.json` — secretos de dev suben al repositorio
- Generar connection strings hardcodeadas en código en lugar de leerlas de `IConfiguration`
