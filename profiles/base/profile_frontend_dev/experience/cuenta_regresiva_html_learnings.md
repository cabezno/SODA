# Learnings from cuenta_regresiva_html
*2026-04-21*

## Pattern: State-Driven Dynamic Styling
For a UI with distinct visual states (running, stopped, time out), using React's state to conditionally apply CSS classes is highly effective. This worked well for changing the timer's color to red on completion, making the logic declarative and easy to follow.

## Pattern: Component Encapsulation for Single-Purpose Tools
Even for a very simple application like a full-screen timer, encapsulating all related logic (time management, controls, display) within a single React component proved efficient. It keeps the scope small and the functionality self-contained.

## Anti-pattern: Architecture-Requirement Mismatch
A severe anti-pattern was observed where the generated architecture (a backend API credit monitor) was completely unrelated to the user's request (a frontend countdown timer). This indicates a critical failure in the initial problem analysis phase that must be corrected.

## Anti-pattern: Ignoring Profile and Skill Context
Proposing a complex, multi-module backend architecture for a developer profile explicitly defined as `profile_frontend_dev` with `skill_react` is a major process flaw. The proposed solution should always align with the active profile's expertise.

## Anti-pattern: Proceeding After Critical Planning Failure
The project continued despite the blueprint generation failing with a clear API error. A failed blueprinting step should be a hard stop, triggering a re-evaluation or user clarification, not a progression with a mismatched and likely nonsensical architecture.

## Preference: Preference for High-Contrast, Minimalist UIs
The explicit requirement for a full-screen, black background with yellow numbers shows a preference for high-visibility, focused user interfaces that eliminate all distractions and present only the essential information.

## Preference: Preference for Declarative State Management
Choosing React for this task, despite its simplicity, indicates a preference for managing UI as a function of state. The timer's behavior (running, paused, finished) is directly tied to state variables, which is a core tenet of the profile's preferred framework.

## Knowledge Suggestion
Best practices for implementing timers in React using `useEffect` and `setInterval`/`setTimeout`, including the use of `useRef` to hold mutable values without re-rendering and ensuring proper cleanup to prevent memory leaks.
