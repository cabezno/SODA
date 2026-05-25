import re

with open("kernel/intelligence/architect.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace f"something
# something" with f"""something
# something"""

content = re.sub(r'(p[1-4]_user\s*=\s*)f"([^"]+)"', r'\1f"""\2"""', content)
content = re.sub(r'(user_message\s*=\s*)f"([^"]+)"', r'\1f"""\2"""', content)

with open("kernel/intelligence/architect.py", "w", encoding="utf-8") as f:
    f.write(content)
