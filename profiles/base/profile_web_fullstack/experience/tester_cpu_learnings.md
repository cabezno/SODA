# Learnings from tester_cpu
*2026-04-22*

## Pattern: Decoupled Core Logic Modules
Separating the Resource Monitor, Process Manager, and Throttle Engine into distinct modules worked very well. This allows each component to have a single responsibility (e.g., monitor runs in its own thread, manager handles subprocesses) making the system easier to test, maintain, and reason about.

## Pattern: Configuration-Driven Control
Externalizing all key parameters (thresholds, script paths, ports) into a dedicated configuration module (`config.py`, `.env`) is a strong pattern. It allows the core throttling logic to remain generic while enabling easy adaptation of the tool's behavior without code changes.

## Pattern: Resilient Hardware Monitoring
The explicit design choice for the resource monitor to handle the absence of a specific GPU (NVIDIA) and continue functioning is a key pattern for building robust systems tools. This graceful degradation ensures the application remains useful on a wider variety of hardware.

## Anti-pattern: Initial Profile Mismatch
Starting with `profile_web_fullstack` and `skill_react` for a systems-level process management tool was a significant anti-pattern. It created friction and required manual correction, demonstrating the importance of selecting a profile (like backend or systems_engineer) that aligns with the core problem domain, even if a simple web UI is present.

## Preference: Backend-First with a Thin UI
The architecture heavily prioritizes robust, modular backend logic for process control and monitoring. The web interface is treated as a simple 'control panel' and data viewer, rather than a complex Single-Page Application, indicating a preference for solving the core problem in the backend.

## Preference: Standard Python Libraries for System Interaction
There is a clear preference for using standard, battle-tested Python libraries like `subprocess`, `psutil`, and `GPUtil` for direct OS and hardware interaction. This avoids higher-level abstractions, resulting in a self-contained and transparent solution.

## Preference: Event Logging to Plain Text
The decision to log all significant events (process launch, throttling actions, stabilization) to a simple `.txt` file indicates a preference for human-readable, easily parsable, and dependency-free logging for diagnostics and auditing.

## Knowledge Suggestion
Control loop design with hysteresis: When throttling resources, reduce load at a high threshold (e.g., 90% CPU) but only increase load again at a significantly lower threshold (e.g., 75% CPU) to prevent rapid, unstable oscillations around the setpoint.
