import re

with open("kernel/orchestration/genesis.py", "r", encoding="utf-8") as f:
    content = f.read()

# Force Gemini 1.5 Pro explicitly for Genesis
content = content.replace(
    '        metadata={"phase": "genesis", "layer": 1}\n    )',
    '        metadata={"phase": "genesis", "layer": 1},\n        model="gemini-2.5-pro"\n    )'
)

with open("kernel/orchestration/genesis.py", "w", encoding="utf-8") as f:
    f.write(content)
    
# Now force Flash for the rest in recursive engine
with open("kernel/orchestration/recursive_engine.py", "r", encoding="utf-8") as f:
    engine_content = f.read()

engine_content = engine_content.replace(
    'response_format="json"\n                )',
    'response_format="json",\n                    model="gemini-2.5-flash"\n                )'
)

with open("kernel/orchestration/recursive_engine.py", "w", encoding="utf-8") as f:
    f.write(engine_content)
