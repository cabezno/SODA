import re

with open("kernel/security/security_reviewer.py", "r", encoding="utf-8") as f:
    content = f.read()

content = re.sub(
    r'def __init__\(self, context_builder=None, notify_fn=None\):',
    r'def __init__(self, gemini_driver=None, context_builder=None, notify_fn=None):\n        self.gemini = gemini_driver',
    content
)

with open("kernel/security/security_reviewer.py", "w", encoding="utf-8") as f:
    f.write(content)
