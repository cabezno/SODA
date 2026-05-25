import re
with open("kernel/validators/v2/polyglot_validator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Instead of re.sub we will just do string replacement
idx1 = content.find("        cleaned_lines = []")
idx2 = content.find("        return \"\\n\".join(cleaned_lines)")

patch = """        cleaned_lines = []
        for line in code.splitlines():
            # Let's see if the line starts with a number list pattern (e.g. "1. " or "1.")
            import re
            match = re.match(r'^\\s*\\d+\\.\\s*(.*)', line)
            if match:
                cleaned_lines.append(match.group(1))
            else:
                cleaned_lines.append(line)
\n"""

if idx1 != -1 and idx2 != -1:
    content = content[:idx1] + patch + content[idx2:]

with open("kernel/validators/v2/polyglot_validator.py", "w", encoding="utf-8") as f:
    f.write(content)
