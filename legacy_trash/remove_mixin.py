import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove import
content = re.sub(r'from kernel\.orchestration\.phase_mixin import PhaseMixin\n', '', content)

# 2. Remove inheritance
content = re.sub(r'class SodaOrchestrator\(PhaseMixin\):', 'class SodaOrchestrator:', content)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
