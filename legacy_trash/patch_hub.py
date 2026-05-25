import re

with open("kernel/drivers/provider_hub.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('"claude": ["claude", "gemini", "openai", "ollama"],', '')
content = content.replace('"gemini", "claude"', '"gemini"')
content = content.replace('"claude", ', '')

with open("kernel/drivers/provider_hub.py", "w", encoding="utf-8") as f:
    f.write(content)
