import os, re

for root, _, files in os.walk("kernel"):
    for file in files:
        if not file.endswith(".py"): continue
        path = os.path.join(root, file)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            
        new_content = re.sub(r"gemini_driver\s*=\s*None,\s*gemini_driver\s*=\s*None", "gemini_driver=None", content)
        new_content = re.sub(r"gemini_driver,\s*gemini_driver=None", "gemini_driver=None", new_content)
        new_content = re.sub(r"gemini_driver,\s*gemini_driver", "gemini_driver", new_content)
        
        if new_content != content:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Fixed def in {path}")
