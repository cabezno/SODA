# Build Infrastructure Checklist — Rust (Axum / Actix-web)

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `Cargo.toml` | Sin esto `cargo` no puede compilar ni resolver dependencias |
| `Cargo.lock` | Debe commitearse en aplicaciones (no en librerías); garantiza builds reproducibles |
| `src/main.rs` | Entry point de la aplicación |
| `.env.example` | Documenta todas las variables de entorno requeridas |
| `.env` | Variables reales en local (nunca commitear) |
| `.gitignore` | Debe excluir `target/`, `.env` |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no compila |
| `.vscode/launch.json` | Sin esto F5 no inicia el debugger con CodeLLDB |
| `.vscode/extensions.json` | Recomienda rust-analyzer y CodeLLDB |

## Contenido mínimo de Cargo.toml (Axum)

```toml
[package]
name = "my-rust-app"
version = "0.1.0"
edition = "2021"

[[bin]]
name = "server"
path = "src/main.rs"

[dependencies]
axum = { version = "0.7", features = ["macros"] }
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
dotenvy = "0.15"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
thiserror = "1"
anyhow = "1"

[dev-dependencies]
axum-test = "14"
tokio-test = "0.4"

[profile.release]
opt-level = 3
lto = true
codegen-units = 1
```

## Contenido mínimo de Cargo.toml (Actix-web)

```toml
[package]
name = "my-actix-app"
version = "0.1.0"
edition = "2021"

[dependencies]
actix-web = "4"
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
dotenvy = "0.15"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
thiserror = "1"
```

## Estructura de carpetas recomendada

```
my-rust-app/
├── src/
│   ├── main.rs              ← entry point, tokio runtime, server setup
│   ├── routes/
│   │   ├── mod.rs
│   │   └── health.rs
│   ├── handlers/
│   │   ├── mod.rs
│   │   └── items.rs
│   ├── models/
│   │   ├── mod.rs
│   │   └── item.rs
│   ├── errors.rs            ← tipos de error con thiserror
│   └── config.rs            ← carga de config desde env
├── tests/                   ← integration tests
├── Cargo.toml
├── Cargo.lock
├── .env.example
└── .gitignore
```

## Contenido mínimo de .env.example

```
RUST_LOG=debug
APP_HOST=0.0.0.0
APP_PORT=8080
DATABASE_URL=postgres://user:password@localhost:5432/mydb
JWT_SECRET=changeme_generate_random_32_chars
```

## .vscode/tasks.json

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Cargo: Build",
      "type": "shell",
      "command": "cargo build",
      "group": { "kind": "build", "isDefault": true },
      "problemMatcher": ["$rustc"]
    },
    {
      "label": "Cargo: Run",
      "type": "shell",
      "command": "cargo run",
      "group": "build",
      "presentation": { "reveal": "always", "panel": "dedicated" }
    },
    {
      "label": "Cargo: Test",
      "type": "shell",
      "command": "cargo test",
      "group": { "kind": "test", "isDefault": true }
    },
    {
      "label": "Cargo: Clippy",
      "type": "shell",
      "command": "cargo clippy -- -D warnings",
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
      "type": "lldb",
      "request": "launch",
      "name": "Rust: Debug server",
      "cargo": {
        "args": ["build", "--bin=server"],
        "filter": { "name": "server", "kind": "bin" }
      },
      "args": [],
      "cwd": "${workspaceFolder}",
      "env": { "RUST_LOG": "debug" }
    }
  ]
}
```

## .vscode/extensions.json

```json
{
  "recommendations": [
    "rust-lang.rust-analyzer",
    "vadimcn.vscode-lldb",
    "serayuzgur.crates",
    "humao.rest-client"
  ]
}
```

## Pasos que debe ejecutar el usuario para correr el proyecto

1. Instalar Rust via rustup: https://rustup.rs/
2. Copiar `.env.example` a `.env` y completar valores reales
3. Compilar y correr: `cargo run`
4. Para producción: `cargo build --release && ./target/release/server`

## Build commands

| Acción | Comando |
|--------|---------|
| Compilar debug | `cargo build` |
| Compilar release | `cargo build --release` |
| Dev run | `cargo run` |
| Prod run | `./target/release/server` |
| Tests | `cargo test` |
| Tests con output | `cargo test -- --nocapture` |
| Linting | `cargo clippy -- -D warnings` |
| Formatear | `cargo fmt` |
| Ver docs | `cargo doc --open` |

## Reglas del auditor (checklist para código generado)

1. **`Cargo.lock` commiteado** — para aplicaciones (no librerías) el lock file garantiza builds reproducibles; no debe estar en `.gitignore`
2. **`#[tokio::main]` en `main.rs`** — obligatorio para usar `await` en main; sin esto el compilador rechaza funciones async en el entry point
3. **Sin `.unwrap()` en paths de producción** — usar `?` con tipos `Result<T, E>` o `anyhow::Result`; `.unwrap()` solo en tests o en datos que son genuinamente imposibles de fallar
4. **Tipos de error con `thiserror`** — errores de dominio deben implementar `std::error::Error` via `#[derive(Error)]`
5. **`Serialize` + `Deserialize` en structs de API** — todo struct que va en request/response body necesita `#[derive(Serialize, Deserialize)]`
6. **Módulos declarados con `mod`** — crear un archivo `handlers/items.rs` no es suficiente; debe existir `mod items;` en `handlers/mod.rs`
7. **`dotenvy::dotenv().ok()` al inicio de `main`** — llamado antes de cualquier `std::env::var()`

## Errores comunes de generación AI

- Olvidar `edition = "2021"` en `Cargo.toml` — la edición 2015 tiene sintaxis diferente para módulos
- No declarar submódulos con `mod` — el compilador no encuentra archivos que no estén explícitamente declarados
- Usar `.unwrap()` en `main.rs` al leer variables de entorno — el server pánica en lugar de dar error descriptivo
- Olvidar `features = ["full"]` en `tokio` — sin esto falta el runtime multi-thread y macros como `#[tokio::main]`
- `Cargo.lock` en `.gitignore` — rompe reproducibilidad de builds
- Usar `String` donde `&str` es suficiente — clones innecesarios
- Olvidar `axum::Router::new()` con `.route()` para cada endpoint — las rutas no registradas devuelven 404 silencioso
- No incluir `tracing-subscriber` inicializado en main — logs no aparecen aunque se usen macros `tracing::info!()`
