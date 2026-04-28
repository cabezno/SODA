# Learnings from test_informe_final
*2026-04-27*

## Pattern: Stdlib for Simplicity
For simple CLI tools with no complex requirements, relying exclusively on the Python standard library (like `datetime`, `pathlib`) is highly effective. It eliminates dependency management, ensures fast startup, and simplifies distribution.

## Pattern: Sensible Defaults over Configuration
When requirements are minimal, automatically choosing conventional defaults (e.g., log file in the current working directory, ISO-like timestamp format) is a successful pattern. It accelerates development by avoiding unnecessary user configuration for a simple utility.

## Anti-pattern: Mismatched Skill Selection
Applying a highly specialized and irrelevant skill (`skill_finance`) to a general-purpose programming task (Python CLI/File I/O) is a significant anti-pattern. It indicates a failure in the initial capability assessment. The correct domain skill (e.g., `skill_python`) should always be prioritized.

## Preference: Preference for `pathlib`
The automatic selection of `pathlib.Path` for handling the log file path, as noted in the blueprint's assumptions, reveals an implicit preference for modern, object-oriented file system APIs over traditional string-based methods in Python.

## Preference: Zero-Configuration CLI Tools
The design intentionally omitted `argparse` or environment variables based on user confirmation, showing a preference for creating simple, zero-configuration tools that 'just work' out of the box for their core, single purpose.

## Knowledge Suggestion
Add a guideline to the profile: 'For file system path manipulation in Python, prefer the `pathlib` module. It provides an object-oriented interface that is more expressive and less error-prone than using string operations or the `os.path` module, especially for cross-platform compatibility.'
