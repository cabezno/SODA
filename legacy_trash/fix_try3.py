import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix the orphaned `try:` at the end
pattern = re.compile(r'        try:\n            # Determine which phases are already complete.*?await self\._phase_wisdom\(project\)\n\n\nif __name__', re.DOTALL)

content = pattern.sub('if __name__', content)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
