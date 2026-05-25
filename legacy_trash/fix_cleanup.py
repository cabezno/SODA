import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix the active_model error again, because it seems we restored the file and missed this one spot in cleanup_context at the very end of the file.
content = re.sub(
    r'ResourceMonitor\.set_mode\("IDLE", ollama_model=self\.ollama\.active_model or "qwen2\.5-coder:14b"\)',
    r'ResourceMonitor.set_mode("IDLE", ollama_model=self.ollama.model or "qwen2.5-coder:14b")',
    content
)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
