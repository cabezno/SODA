import re

with open("kernel/validators/v2/polyglot_validator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add sql, sh, bash, json support to the regex
content = re.sub(
    r'```\(\?:python\|ts\|js\|go\|rust\|cpp\|csharp\|php\|html\|css\)\?',
    r'```(?:python|ts|js|go|rust|cpp|csharp|php|html|css|sql|sh|bash|json)?',
    content
)

# Fix AST validator without raw strings that break re.sub
idx1 = content.find('        if language.lower() == "python" or language.lower() == "py":')
idx2 = content.find('        else:')

patch = """        if language.lower() == "python" or language.lower() == "py":
            # Smart check: if it looks like SQL (CREATE TABLE, INSERT), skip Python AST
            import re
            if re.search(r'^\\s*(CREATE TABLE|INSERT INTO|SELECT |UPDATE |DELETE |-- )', clean_code, re.IGNORECASE):
                return clean_code
            try:
                import ast
                ast.parse(clean_code)
            except SyntaxError as e:
                raise ValueError(f"AUDITORÍA AST FALLIDA: Error de sintaxis en línea {e.lineno}: {e.msg}")
"""

if idx1 != -1 and idx2 != -1:
    content = content[:idx1] + patch + content[idx2:]

with open("kernel/validators/v2/polyglot_validator.py", "w", encoding="utf-8") as f:
    f.write(content)
