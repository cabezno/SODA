# Build Infrastructure Checklist — Go

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `go.mod` | Sin esto `go build` no puede resolver módulos; define el module path y la versión de Go |
| `go.sum` | Checksums de dependencias; se genera con `go mod tidy` pero debe commitearse |
| `main.go` O `cmd/server/main.go` | Entry point de la aplicación |
| `.env.example` | Documenta todas las variables de entorno requeridas |
| `.env` | Variables reales en local (nunca commitear) |
| `.gitignore` | Debe excluir el binario compilado, `.env`, `vendor/` (si no se usa vendoring) |
| `Makefile` | Centraliza los comandos comunes: build, run, test, lint |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no compila |
| `.vscode/launch.json` | Sin esto F5 no inicia el debugger con Delve |
| `.vscode/extensions.json` | Recomienda extensión oficial de Go |

## Contenido mínimo de go.mod

```
module github.com/username/myapp

go 1.22

require (
    github.com/gin-gonic/gin v1.10.0
    github.com/joho/godotenv v1.5.1
)
```

## Estructura de carpetas recomendada

```
myapp/
├── cmd/
│   └── server/
│       └── main.go          ← entry point
├── internal/
│   ├── handler/             ← HTTP handlers
│   ├── service/             ← lógica de negocio
│   ├── repository/          ← acceso a datos
│   └── model/               ← structs de dominio
├── pkg/                     ← código reutilizable/exportable
├── config/
│   └── config.go            ← carga de variables de entorno
├── go.mod
├── go.sum
├── Makefile
├── .env.example
└── .gitignore
```

## Contenido mínimo de Makefile

```makefile
.PHONY: build run test lint clean

APP_NAME=myapp
BUILD_DIR=./bin

build:
	go build -o $(BUILD_DIR)/$(APP_NAME) ./cmd/server

run:
	go run ./cmd/server

dev:
	air -c .air.toml

test:
	go test ./... -v -cover

lint:
	golangci-lint run

clean:
	rm -rf $(BUILD_DIR)

tidy:
	go mod tidy
```

## Contenido mínimo de .env.example

```
APP_ENV=development
APP_PORT=8080
DATABASE_URL=postgres://user:password@localhost:5432/mydb?sslmode=disable
JWT_SECRET=changeme_generate_random_32_chars
ALLOWED_ORIGINS=http://localhost:3000
```

## .vscode/tasks.json

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Go: Build",
      "type": "shell",
      "command": "go build -o bin/app ./cmd/server",
      "group": { "kind": "build", "isDefault": true },
      "problemMatcher": ["$go"]
    },
    {
      "label": "Go: Run",
      "type": "shell",
      "command": "go run ./cmd/server",
      "group": "build",
      "presentation": { "reveal": "always", "panel": "dedicated" }
    },
    {
      "label": "Go: Test",
      "type": "shell",
      "command": "go test ./... -v",
      "group": { "kind": "test", "isDefault": true }
    },
    {
      "label": "Go: Mod Tidy",
      "type": "shell",
      "command": "go mod tidy",
      "group": "build"
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
      "name": "Go: Debug server",
      "type": "go",
      "request": "launch",
      "mode": "auto",
      "program": "${workspaceFolder}/cmd/server",
      "env": {},
      "envFile": "${workspaceFolder}/.env",
      "args": []
    }
  ]
}
```

## .vscode/extensions.json

```json
{
  "recommendations": [
    "golang.go",
    "humao.rest-client"
  ]
}
```

## .gitignore mínimo

```
# Binary
bin/
*.exe

# Environment
.env

# Go
vendor/

# IDE
.idea/
```

## Pasos que debe ejecutar el usuario para correr el proyecto

1. Instalar Go >= 1.22 (https://go.dev/dl/)
2. Instalar dependencias: `go mod download`
3. Copiar `.env.example` a `.env` y completar valores reales
4. Correr: `go run ./cmd/server` (o `make run`)
5. Acceder a http://localhost:8080

## Build commands

| Acción | Comando |
|--------|---------|
| Descargar deps | `go mod download` |
| Limpiar deps | `go mod tidy` |
| Build | `go build -o bin/app ./cmd/server` |
| Dev | `go run ./cmd/server` |
| Dev con hot-reload | `air` (requiere `go install github.com/cosmtrek/air@latest`) |
| Tests | `go test ./... -v` |
| Tests con coverage | `go test ./... -cover -coverprofile=coverage.out` |
| Linting | `golangci-lint run` |

## Reglas del auditor (checklist para código generado)

1. **`go.mod` con module path correcto** — el module path debe coincidir con los imports internos del proyecto; si `go.mod` dice `module github.com/user/myapp`, los imports internos deben ser `github.com/user/myapp/internal/...`
2. **Manejo explícito de errores** — nunca `_` para ignorar errores; cada `err` debe chequearse con `if err != nil`
3. **`internal/` para código privado** — código no exportable debe vivir en `internal/`; Go lo hace inaccessible desde fuera del módulo
4. **Structs de config con tags de entorno** — usar `envconfig`, `godotenv` + `os.Getenv()` con valores de fallback; nunca `os.Getenv("KEY")` sin validar que no esté vacío
5. **Graceful shutdown** — el servidor debe capturar `SIGINT`/`SIGTERM` y llamar `server.Shutdown(ctx)` con timeout, no `os.Exit(1)`
6. **`go.sum` commiteado** — no está en `.gitignore`; es necesario para builds reproducibles
7. **Tests en archivos `_test.go`** — Go requiere el sufijo `_test.go`; archivos sin este sufijo no se ejecutan con `go test`

## Errores comunes de generación AI

- `go.mod` con module path `example.com/app` en lugar de un path real — los imports internos quedan incoherentes
- Olvidar `go.sum` o ponerlo en `.gitignore` — el build falla en CI sin el archivo de checksums
- No estructurar en `cmd/` + `internal/` — poner todo en la raíz es válido para proyectos pequeños pero genera problemas de importación circular en proyectos grandes
- Usar `log.Fatal()` en handlers — mata el proceso en lugar de retornar un error HTTP
- No hacer `defer rows.Close()` después de `db.Query()` — memory leak
- Olvidar `context.Context` como primer parámetro en funciones de servicio — imposible cancelar operaciones largas
- Usar `interface{}` en lugar de `any` (Go 1.18+) o tipos concretos
- Hardcodear el puerto en lugar de leerlo de variables de entorno
