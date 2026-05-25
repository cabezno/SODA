import re
with open("kernel/orchestration/layer0_wisdom.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix the duplicate logging issue in Layer 0.
# The UI intercepts USER_QUESTION and already logs/displays it. We shouldn't also log "Detectadas X ambigüedades..." in the exact same format if we are immediately asking them.
# Let's silence some of the internal notify_fn calls to avoid echo.

content = content.replace('            if notify_fn:\n                notify_fn("USER_QUESTION", question)', '            # notify_fn("USER_QUESTION", question) is redundant because ask_user_fn handles the UI echo.')

with open("kernel/orchestration/layer0_wisdom.py", "w", encoding="utf-8") as f:
    f.write(content)
