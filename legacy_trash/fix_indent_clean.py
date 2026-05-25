import re
with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("                self.gemini = GeminiDriver()", "        self.gemini = GeminiDriver()")

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
