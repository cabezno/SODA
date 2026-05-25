import re
with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("claude_driver=self.claude", "gemini_driver=self.gemini")
content = content.replace("claude_driver=self.gemini", "gemini_driver=self.gemini")

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
