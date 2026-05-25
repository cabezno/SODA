import re

with open("kernel/intelligence/conformance_verifier.py", "r", encoding="utf-8") as f:
    content = f.read()

content = re.sub(
    r'def __init__\(self, tracker: Optional\["PerformanceTracker"\] = None, notify_fn=None\) -> None:',
    r'def __init__(self, gemini_driver, tracker: Optional["PerformanceTracker"] = None, notify_fn=None) -> None:',
    content
)

with open("kernel/intelligence/conformance_verifier.py", "w", encoding="utf-8") as f:
    f.write(content)
