import re
with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix remaining kwargs issues globally
content = re.sub(r',\s*gemini_driver=self\.gemini', '', content)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
