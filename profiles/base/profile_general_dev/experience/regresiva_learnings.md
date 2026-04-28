# Learnings from regresiva
*2026-04-21*

## Anti-pattern: Architecture-Requirement Mismatch
The generated architecture for a Python-based API monitoring service is completely unrelated to the user's request for a C++ Windows countdown timer. This indicates a critical failure in the generation pipeline, likely triggered by the blueprint API error. The system should have halted instead of generating a nonsensical solution.

## Anti-pattern: Ignoring Core Constraints
The explicit technology (C++) and platform (Windows) requirements were completely ignored. The generated architecture uses Python and is platform-agnostic, failing the most fundamental constraints of the project.

## Anti-pattern: Poor Error Propagation
The blueprint phase failed with a clear 'low credit' error. This fatal error was not handled correctly, leading the subsequent architecture phase to proceed with faulty or no context, resulting in a hallucinated output.

## Preference: Default to Familiar Backend Patterns
When faced with an upstream error or an unfamiliar domain (C++ GUI), the system defaulted to a standard, modular Python backend architecture. This reveals a bias towards a known pattern, even when it's completely inappropriate for the user's request.

## Knowledge Suggestion
Fundamentals of native Windows GUI development in C++ using the Win32 API, including window creation (CreateWindowEx), message loops (GetMessage, DispatchMessage), and handling timers (SetTimer, WM_TIMER).
