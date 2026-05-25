import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# We need to remove everything from `self._current_phase = "requirements"` down to the old `return project`
pattern = re.compile(r'            self\._current_phase = "requirements".*?        except Exception as e:.*?        return project\n', re.DOTALL)
content = pattern.sub('', content)

# Clean up any leftover syntax errors
content = content.replace('print(f"\\n[ERROR FATAL V2] {error_msg}\\n{_tb.format_exc()}")', 'print(f"\\\\n[ERROR FATAL V2] {error_msg}\\\\n{_tb.format_exc()}")')


with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
