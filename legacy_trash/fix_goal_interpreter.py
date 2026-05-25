import re

with open("kernel/intelligence/goal_interpreter.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix __init__ signature
content = re.sub(
    r'def __init__\(self, context_builder\):',
    r'def __init__(self, gemini_driver, context_builder):',
    content
)
# Make sure we save gemini_driver to self.gemini
content = re.sub(
    r'self\.builder = context_builder',
    r'self.builder = context_builder\n        self.gemini = gemini_driver',
    content
)

with open("kernel/intelligence/goal_interpreter.py", "w", encoding="utf-8") as f:
    f.write(content)
