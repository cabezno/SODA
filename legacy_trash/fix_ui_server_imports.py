import re

with open("ui/server.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace ClaudeDriver with GeminiDriver in imports
content = re.sub(r'from kernel\.drivers\.claude_driver import ClaudeDriver', r'from kernel.drivers.gemini_driver import GeminiDriver', content)

# Replace instantiations
content = content.replace("ClaudeDriver()", "GeminiDriver()")

# Fix the SystemHealer instantiation kwargs
content = content.replace("claude_driver=GeminiDriver()", "gemini_driver=GeminiDriver()")

with open("ui/server.py", "w", encoding="utf-8") as f:
    f.write(content)
