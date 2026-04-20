# General Dev Code Conventions

- Prefer stdlib over third-party when functionality is equivalent
- CLI tools use `argparse` or `click` — always include `--help`
- Scripts have a `main()` function guarded by `if __name__ == "__main__"`
- Log with `logging` module, not print statements (except quick scripts)
- Type hints on all function signatures
- Keep functions under 30 lines — extract helpers liberally
