import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix TestGenerator signature call in orchestrator
content = re.sub(
    r'        self\.test_generator = TestGenerator\(\n            gemini_driver=self\.gemini,\n',
    r'        self.test_generator = TestGenerator(\n',
    content
)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
