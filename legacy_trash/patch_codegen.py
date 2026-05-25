import re

with open("kernel/code_generator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace __init__ signature
content = re.sub(
    r"def __init__\(self, ollama_driver, claude_driver, gemini_driver=None\):",
    r"def __init__(self, ollama_driver, gemini_driver=None):",
    content
)

# Replace self.claude = claude_driver
content = re.sub(r"\s*self\.claude = claude_driver\n", "\n", content)

# Replace ladder documentation
content = content.replace(
    "L1-L3: Qwen × 3  →  L4-L6: Gemini × 3  →  L7-L9: Claude × 3",
    "L1-L3: Qwen × 3  →  L4-L6: Gemini Flash × 3  →  L7-L9: Gemini Pro × 3"
)

# Replace ladder list
content = content.replace(
    '"claude", "claude", "claude",',
    '"gemini_pro", "gemini_pro", "gemini_pro",'
)

# Reroute _call_claude and _call_claude_haiku to just use _call_gemini basically.
# For simplicity, we just replace the call inside the ladder:
content = content.replace(
    "elif level == \"claude\":",
    "elif level == \"gemini_pro\":"
)
content = content.replace(
    "claude_attempt",
    "gemini_pro_attempt"
)
content = content.replace(
    "_call_claude(",
    "_call_gemini("
)
content = content.replace(
    "[L{attempt_num}/Claude]",
    "[L{attempt_num}/Gemini Pro]"
)
content = content.replace(
    "Claude×3",
    "GeminiPro×3"
)

with open("kernel/code_generator.py", "w", encoding="utf-8") as f:
    f.write(content)
