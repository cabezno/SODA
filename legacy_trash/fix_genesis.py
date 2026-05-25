import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix the missing gemini_driver argument in generate_root_contract call
pattern = re.compile(
    r'generate_root_contract\(\n\s*user_description=project\.description,\n\s*active_skills=project\.skills or \[\],\n\s*notify_fn=notify_wrapper\n\s*\)',
    re.DOTALL
)

replacement = """generate_root_contract(
                user_description=project.description,
                active_skills=project.skills or [],
                gemini_driver=self.gemini,
                notify_fn=notify_wrapper
            )"""

content = pattern.sub(replacement, content)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
