import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix the missing gemini_driver argument in resolve_ambiguities call
# I will replace the call to include gemini_driver=self.gemini
pattern = re.compile(
    r'resolve_ambiguities\(\n\s*user_prompt=description,\n\s*ask_user_fn=ask_user_wrapper,\n\s*notify_fn=notify_wrapper\n\s*\)',
    re.DOTALL
)

replacement = """resolve_ambiguities(
                user_prompt=description,
                gemini_driver=self.gemini,
                ask_user_fn=ask_user_wrapper,
                notify_fn=notify_wrapper
            )"""

content = pattern.sub(replacement, content)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
