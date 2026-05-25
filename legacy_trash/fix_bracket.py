import re
with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

pattern = re.compile(
    r'            elif "skill_html" in skills_str or "skill_css" in skills_str:\n\s*lang = "html"\n\s*engine = SodaRecursiveEngine\(\n\s*lang = "html"\n\s*engine = SodaRecursiveEngine\(',
    re.DOTALL
)

replacement = """            elif "skill_html" in skills_str or "skill_css" in skills_str:
                lang = "html"
                
            engine = SodaRecursiveEngine("""

content = pattern.sub(replacement, content)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
