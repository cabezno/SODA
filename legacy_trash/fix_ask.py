import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix the method call from ask_user to ask
# The method in UserInteractionGateway is `ask(self, question: str, notify_fn: Callable) -> str`
content = re.sub(
    r'return await gw\.ask_user\(question, options=options\)',
    r'# Omitimos options porque el gateway de SODA V1 solo acepta string.\n        return await gw.ask(question, notify_fn=self._notify)',
    content
)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
