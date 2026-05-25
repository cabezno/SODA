import re
with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("CodeGenerator(self.ollama, self.gemini, self.gemini)", "CodeGenerator(self.ollama, self.gemini)")

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
