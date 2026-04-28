# SODA — Architecture Reference

## Pipeline

```
CAP → WISDOM → REQ → ARCH → PLAN → DEV → EVOLUTION → DONE
```

| Phase | Agent | Model | Output |
|-------|-------|-------|--------|
| CAP | `skill_matcher` + `profile_matcher` | Gemini Flash | Selected skills + profile |
| WISDOM | `wisdom_agent` | Gemini Flash | Ambiguity report |
| REQ | `requirements_interviewer` | Claude Sonnet | `blueprint.json` |
| ARCH | `global_architect` | Gemini Pro | `architecture.json` |
| PLAN | `dependency_graph.py` | Python (pure) | `ExecutionPlan` (DAG) |
| DEV | `code_generator.py` | Qwen×3 → Claude | Generated files |
| EVOLUTION | `profile_evolution` | Gemini Flash | Updated profile |

## Template System (Blueprints)

SODA utiliza un sistema de plantillas base (Blueprints) para garantizar que cada proyecto parta de una estructura escalable y probada en producción. Estas plantillas se encuentran en `/templates`.

### Categorías de Plantillas:
- **Fullstack:** `fastapi-react` (FastAPI + SQLModel + React + Vite).
- **Backend:** `node-clean-ts` (Node.js + Clean Architecture + TypeScript).
- **Mobile:** `react-native-expo` (Multiplataforma iOS/Android/Web).

### Flujo de Uso:
1. El **Architect** selecciona la plantilla más adecuada según el stack detectado.
2. El sistema clona la estructura base en el workspace del proyecto.
3. El **CodeGenerator** inyecta la lógica de negocio respetando los patrones de la plantilla.

## Code generation escalation

`CodeGenerator` retries Qwen 3 times. On failure escalates to Claude Sonnet. If Claude also fails, saves file with `validated=False` and continues (does not abort pipeline).

## `architecture.json` contract

```json
{
  "modulos": [
    {
      "nombre": "auth_service",
      "descripcion": "...",
      "dependencias": ["user_model", "db_manager"],
      "archivos": ["auth_service.py"]
    }
  ]
}
```

`dependencias` must be exact values of `nombre` from other modules in the array. External libraries and file paths are filtered out by `DependencyGraph` and silently ignored.

## Claude driver — token optimization

`kernel/drivers/claude_driver.py` uses:
- `cache_control: ephemeral` on system prompt blocks
- `max_continuations: 2` for Opus (handles 32k output token hard limit via multi-turn)

## Context health thresholds

| Threshold | Value | Reason |
|-----------|-------|--------|
| `TOKEN_WARN_THRESHOLD` | 80,000 | ~80% of 100k limit |
| `SLOW_CALL_S` | 30s | Qwen normal: 15–25s |
| `ERROR_RATE_WARN` | 0.50 | Avoids false positives during Qwen×3→Claude escalation bursts |
| `ROLLING_WINDOW` | 15 | Smooths escalation bursts |

## Post-generation operations

- **`modify(project, request)`**: GoalInterpreter classifies change → ImpactAnalyzer computes affected modules → BranchManager creates branch if `change_type ∈ {structural, scope, new_module}` AND `requires_regeneration=True`
- **`refound(project)`**: RefoundationEngine resumes project → `run()` with condensed description

## Workspace isolation

`kernel/lineage/branching.py` copies the workspace on structural changes. Branches are named with timestamp + change type and stored under `projects/<project_id>/branches/`.

## Process management (Windows)

`kernel/execution/project_runner.py` uses `taskkill /F /T /PID` to kill child processes (node, uvicorn, python) since `proc.kill()` only kills the cmd.exe shell. Falls back to `proc.kill()` on non-Windows. Log output is capped at 50 MB to prevent disk overflow.
