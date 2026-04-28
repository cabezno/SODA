# Learnings from cronos
*2026-04-21*

## Pattern: Separation of Logic and UI via Interfaces
The architecture correctly isolates the time-management logic (TimerEngine) from the presentation layer (UI Module). Using an interface (ITimerEvents.h) for communication allows the UI to react to events without being tightly coupled to the timer's implementation. This makes the core logic reusable and easier to test.

## Pattern: Event-Driven UI Updates
The design relies on the TimerEngine to push state changes (tick, state change for blinking) to the UI. This is highly effective for GUI applications as it avoids inefficient polling from the UI thread and ensures the display is updated immediately when the state changes.

## Pattern: Dedicated Initialization Module
Having a specific 'Infraestructura y Arranque' module to handle WinMain, the message loop, and the initial wiring of the UI and Logic modules is a clean pattern. It separates the application's setup and boilerplate from its core operational logic.

## Preference: Preference for Native APIs
The architecture implies a direct use of the Windows API (Win32/GDI for rendering) instead of a cross-platform framework like Qt or wxWidgets. This indicates a preference for minimal dependencies, maximum control, and performance, even if it requires more boilerplate code for window management.

## Preference: State Management in Core Logic
The design centralizes all state (current time, special conditions like 'last 2 seconds') within the TimerEngine. The UI is a passive renderer of this state, which is a robust pattern for preventing synchronization issues and keeping the UI layer simple.

## Preference: Modularization by Responsibility
The codebase is clearly segmented into modules based on their high-level responsibility: Logic, UI, and Application Core. This preference for strict functional decomposition leads to a more organized and maintainable project structure.

## Knowledge Suggestion
Windows GDI/GDI+ for custom 2D graphics rendering. Specifically, techniques for managing Device Contexts (HDC), creating and selecting fonts (HFONT), and implementing double-buffering to achieve smooth, flicker-free animations like the requested blinking text effect.
