# SODA Changelog

## 2026-04-24

### Fixes

**`kernel/orchestrator.py`**
- `run()`, `resume()`, `import_from_code()`: `_notify("DONE")` was unconditional — now emits `DONE` or `FAILED` based on actual `project.state`.
- `open_and_process()`: Fixed crash — `_phase_arch`/`_phase_plan`/`_phase_dev` don't exist; renamed to `_phase_architecture`, `_phase_planning`, `_phase_development`. `_phase_planning()` return value (ExecutionPlan) is now captured and passed to `_phase_development`. `_phase_validation()` result is now captured and passed to `_can_reach_done()` before setting DONE state.

**`ui/server.py`**
- `open_and_process()`: Removed `notify_fn=lambda...` from `SodaOrchestrator()` constructor — constructor doesn't accept that parameter, causing TypeError.

**`kernel/execution/project_runner.py`**
- Added `_kill_process_tree(proc)` using `taskkill /F /T /PID` on Windows to kill child processes (node, uvicorn, python) that survived `proc.kill()`.
- `ProcessHandle.kill()` and `install()` timeout handler now use `_kill_process_tree`.
- `_stream_to_log`: Added 50 MB cap (`_MAX_LOG_BYTES`) to prevent disk overflow from infinite-output processes.

**`kernel/execution/boot_agent.py`**
- All `proc.kill()` calls replaced with `_kill_process_tree(proc)`.

### Architecture

**Claude driver (`kernel/drivers/claude_driver.py`)**
- Already has `cache_control: ephemeral`, `cached_context`, `max_continuations: 2` for Opus truncation.

**Dependency graph (`kernel/dependency_graph.py`)**
- Already uses `sorted()` at topological sort — DFS non-determinism claim in Gemini audit was false.
