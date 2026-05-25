import re

files = [
    "kernel/intelligence/impact_analyzer.py",
    "kernel/intelligence/refoundation.py"
]

for filepath in files:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    content = re.sub(
        r'def __init__\(self, context_builder\):',
        r'def __init__(self, gemini_driver, context_builder):',
        content
    )
    content = re.sub(
        r'self\.builder = context_builder',
        r'self.builder = context_builder\n        self.gemini = gemini_driver',
        content
    )
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
