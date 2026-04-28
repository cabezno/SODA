# Learnings from cronometro
*2026-04-21*

## Pattern: Decoupling Core Logic from UI
Separating the timer's state management (`CountdownTimerService` using `Stopwatch`) from the presentation layer (`MainForm`) was highly effective. This made the core logic independent of UI framework specifics, improving testability and robustness against UI thread blocking.

## Pattern: Centralized Input Handling Service
Creating a dedicated `InputHandlerService` to process all keyboard and mouse events and translate them into commands (e.g., 'Reset', 'TogglePause') worked very well. It prevents scattering input logic across multiple UI event handlers, making it easier to manage and modify controls.

## Pattern: Service-based UI Effects
Encapsulating the 'Time Out' alert logic, including the screen flashing, into a dedicated `TimeoutAlertService` is a clean pattern. It isolates a purely visual, state-dependent effect from the main form's responsibilities, keeping the orchestrator code cleaner.

## Preference: Modular Architecture over Monolithic Form
The design clearly favors breaking down functionality into discrete, single-responsibility modules (Timer Logic, Input, Alerting) rather than placing all code within the MainForm. This preference for separation of concerns is visible even in a small-scale desktop application.

## Preference: Precision in Timing
The choice to use `System.Diagnostics.Stopwatch` for the core logic, rather than relying solely on a less precise UI timer, indicates a preference for technical accuracy and robustness, actively avoiding common issues like timer drift.

## Preference: Interface-based Dependencies
The presence of interfaces like `ICountdownTimerService` and `ITimeoutAlertService` suggests a preference for programming to abstractions, not concretions. This facilitates dependency injection and testing, even if a full DI container isn't used.

## Knowledge Suggestion
Best practices for creating high-resolution, drift-free timers in .NET desktop applications by combining a standard UI timer (e.g., System.Windows.Forms.Timer for ticks) with System.Diagnostics.Stopwatch for accurate elapsed time measurement.
