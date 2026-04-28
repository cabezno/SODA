# SODA — Development Guide

## Requirements

- Python 3.11.9 (Windows 11 native, NO WSL2)
- Docker Desktop running (npipe Windows, used for syntax validation)
- Ollama running locally with `qwen2.5-coder:7b` pulled

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and fill environment variables
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY, GEMINI_API_KEY, OLLAMA_BASE_URL, TELEGRAM_BOT_TOKEN
```

## Running

```bash
# Start the UI (FastAPI + pywebview)
python ui/server.py

# Or start API only (no desktop window)
uvicorn ui.server:app --reload --port 8000
```

## Tests

```bash
python -m pytest tests/ -v   # 47 tests, ~7s, no API keys or Docker needed
```

- `tests/test_unit.py` — deterministic components (28 tests)
- `tests/test_pipeline.py` — full pipeline with mocked drivers (19 tests)

## Scripts

Utility scripts live in `scripts/`:
- `scripts/soda_snapshot.py` — captures project state snapshot
- `scripts/test_drivers.py` — manual driver smoke tests (requires API keys)

## Project structure

```
kernel/          Core orchestration and agents
  drivers/       AI provider adapters (Claude, Gemini, Ollama)
  execution/     Process runner, boot agent, venv manager
  intelligence/  Context health, goal interpreter, impact analyzer
  lineage/       Branching / workspace versioning
ui/              FastAPI server + Monaco frontend
prompts/         Agent prompt templates by provider/role
skills/base/     Reusable skill bundles (fastapi, sqlite, react, jwt, rest)
profiles/base/   Developer profiles (web_fullstack, backend_api, general_dev)
projects/        Generated project workspaces (gitignored)
tests/           Unit + integration tests
scripts/         Dev utilities
docs/            Architecture and reference docs
```

## Key invariants (don't change without impact analysis)

- `_notify()` timeout=0.05s — fire-and-forget; increasing it blocks the pipeline.
- `load_dotenv()` called explicitly in `server.py` and `orchestrator.py` — required when launched from UI.
- `DockerSandbox` uses `npipe` (Windows) — do not switch to unix socket.
- `dependencias` in `architecture.json` must be module **names** (field `nombre`), not file paths.
