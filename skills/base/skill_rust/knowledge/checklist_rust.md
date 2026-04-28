# Rust Code Review Checklist

## Ownership & Memory
- [ ] No unnecessary `.clone()` calls — pass references where possible
- [ ] Lifetimes annotated correctly when inference fails
- [ ] No use of `unsafe` without documented justification
- [ ] `Arc<Mutex<T>>` used only when shared mutable state is truly needed

## Error Handling
- [ ] All `Result` and `Option` handled — no `.unwrap()` in production paths
- [ ] Custom error types defined with `thiserror::Error`
- [ ] `?` operator used consistently in async functions

## Async / Concurrency
- [ ] `#[tokio::main]` on entry point
- [ ] No blocking calls inside async functions (use `tokio::task::spawn_blocking`)
- [ ] Tasks joined or their errors handled — no fire-and-forget panics

## Project Structure
- [ ] `Cargo.toml` present with correct `[package]` and `[dependencies]`
- [ ] `src/main.rs` or `src/lib.rs` present as crate root
- [ ] Modules declared with `mod` in parent, not just file creation

## API / Web
- [ ] Routes registered on the Router/App
- [ ] Request/response types implement `serde::Serialize` + `serde::Deserialize`
- [ ] `/health` endpoint returning 200 OK exists
