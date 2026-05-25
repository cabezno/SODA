import os

for root, _, files in os.walk("kernel"):
    for file in files:
        if not file.endswith(".py"): continue
        path = os.path.join(root, file)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Replace doubled kwargs
        if "gemini_driver=self.gemini,\n            gemini_driver=self.gemini," in content:
            content = content.replace(
                "gemini_driver=self.gemini,\n            gemini_driver=self.gemini,",
                "gemini_driver=self.gemini,"
            )
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed {path}")
            
        if "gemini_driver=self.gemini,\n            gemini_driver=self.gemini,".replace("            ", "        ") in content:
            content = content.replace(
                "gemini_driver=self.gemini,\n        gemini_driver=self.gemini,",
                "gemini_driver=self.gemini,"
            )
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed {path}")

