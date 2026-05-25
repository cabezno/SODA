import re

with open("kernel/drivers/gemini_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add response_schema parameter
content = re.sub(
    r'(response_format:\s*str\s*=\s*"text",)',
    r'\1\n        response_schema: dict | None = None,',
    content
)

# Add to gen_config
config_patch = """        if response_format == "json":
            gen_config["responseMimeType"] = "application/json"
            if response_schema is not None:
                gen_config["responseSchema"] = response_schema"""

content = content.replace(
    '        if response_format == "json":\n            gen_config["responseMimeType"] = "application/json"',
    config_patch
)

with open("kernel/drivers/gemini_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
