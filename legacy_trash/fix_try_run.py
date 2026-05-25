import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace the leftover try block related to the old V1 resume logic inside run()
pattern = re.compile(r'\n        try:\n            # Reanudar fases según el estado.*?\n            if project\.state\.value in \("idle", "capabilities", "requirements"\):\n', re.DOTALL)
content = pattern.sub('', content)

# I will also check if `import inspect` patch inside `fix_remaining.py` is messing with `resume()` or `run()`
# The traceback mentions line 1565 in `run` which is inside `execute_bottom_up(all_contracts)`.

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
