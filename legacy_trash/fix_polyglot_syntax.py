import re

with open("kernel/validators/v2/polyglot_validator.py", "r", encoding="utf-8") as f:
    content = f.read()

# I used a raw string literal `r"""` in Python to define the patch, which caused the literal backslashes `\` to be written into the file.
# Fixing this by replacing `\"\"\"` with standard `"""`.
content = content.replace('\\"\\"\\"', '"""')

with open("kernel/validators/v2/polyglot_validator.py", "w", encoding="utf-8") as f:
    f.write(content)
