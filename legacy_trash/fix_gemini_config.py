import re

with open("kernel/drivers/gemini_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# Completely remove the thinkingConfig to be safe against BAD_REQUEST
patch = """            # Let's completely remove the thinkingConfig to be safe against BAD_REQUEST
            # if "2.5-flash" in (model or self.active_model or ""):
            #     gen_config["thinkingConfig"] = {"thinkingBudget": 0}"""

content = re.sub(r'\s*if "2\.5-flash" in \(model or self\.active_model or ""\):\n\s*gen_config\["thinkingConfig"\] = \{"thinkingBudget": 0\}', patch, content)

with open("kernel/drivers/gemini_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
