import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Remove ClaudeDriver and references
content = re.sub(r'from kernel\.drivers\.claude_driver import ClaudeDriver\n', '', content)
content = re.sub(r'self\.claude = ClaudeDriver\(\)\n', '', content)
content = content.replace('self.claude', 'self.gemini')

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
