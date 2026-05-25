import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix newline in f-string
content = re.sub(r'print\(f"\n\[ERROR FATAL V2\] \{error_msg\}\n\{_tb\.format_exc\(\)\}"\)', 'print(f"\\n[ERROR FATAL V2] {error_msg}\\n{_tb.format_exc()}")', content)

# Check if it was double escaping
content = re.sub(r'print\(f"\n\[ERROR FATAL V2\]', 'print(f"\\\\n[ERROR FATAL V2]', content)
content = re.sub(r'\{error_msg\}\n\{_tb\.format_exc\(\)\}"\)', '{error_msg}\\\\n{_tb.format_exc()}")', content)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
