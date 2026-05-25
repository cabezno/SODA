import os
import re

root_dir = r"projects/OMEGA-CLOUD-MANAGER/source/backend"

def fix_imports(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Replace 'from .api' with 'from api', etc.
    new_content = re.sub(r'from \.(\w+)', r'from \1', content)
    
    if content != new_content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Fixed imports in: {file_path}")

for root, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith(".py"):
            fix_imports(os.path.join(root, file))
