import re

with open("kernel/validators/v2/polyglot_validator.py", "r", encoding="utf-8") as f:
    content = f.read()

patch = """        # 3. Aggressive cleanup for local models that prepend line numbers
        cleaned_lines = []
        for line in code.splitlines():
            # If line is JUST markdown backticks or chatter, ignore it.
            if line.strip().startswith("```"):
                continue
                
            match_num = re.match(r'^\\s*\\d+\\.\\s*(.*)', line)
            if match_num:
                cleaned_lines.append(match_num.group(1))
            else:
                cleaned_lines.append(line)

        # 4. Final safety net: if the very first line is some chatter like "Sure, here is the code:"
        final_code = "\\n".join(cleaned_lines)
        lines = final_code.splitlines()
        start_idx = 0
        for i, line in enumerate(lines):
            s = line.strip()
            # Stop searching and define start block at the first valid Python/JS definition keyword
            if s.startswith(("import ", "from ", "def ", "class ", "@", "const ", "let ", "var ")):
                start_idx = i
                break
        
        return "\\n".join(lines[start_idx:])"""

content = re.sub(
    r'        # 3\. Aggressive cleanup for local models that prepend line numbers.*?        return "\\n"\.join\(cleaned_lines\)',
    patch,
    content,
    flags=re.DOTALL
)

with open("kernel/validators/v2/polyglot_validator.py", "w", encoding="utf-8") as f:
    f.write(content)
