import re

with open("kernel/orchestration/genesis.py", "r", encoding="utf-8") as f:
    content = f.read()

# Force Gemini 1.5 Pro (confirmed ID)
content = content.replace(
    'model="gemini-2.5-pro"',
    'model="gemini-1.5-pro"'
)

with open("kernel/orchestration/genesis.py", "w", encoding="utf-8") as f:
    f.write(content)
    
# Force Flash 1.5 for the rest
with open("kernel/orchestration/recursive_engine.py", "r", encoding="utf-8") as f:
    engine_content = f.read()

engine_content = engine_content.replace(
    'model="gemini-2.5-flash"',
    'model="gemini-1.5-flash"'
)

with open("kernel/orchestration/recursive_engine.py", "w", encoding="utf-8") as f:
    f.write(engine_content)
