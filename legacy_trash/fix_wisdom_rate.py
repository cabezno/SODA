import re

with open("kernel/orchestration/layer0_wisdom.py", "r", encoding="utf-8") as f:
    content = f.read()

patch = """        if response.error_code == "RATE_LIMIT":
            if notify_fn:
                notify_fn("WARNING", "Límite de cuota alcanzado. Procediendo con el pipeline asumiendo requerimientos claros.")
            return current_prompt

        if response.error_code:"""

content = re.sub(r'\s*if response\.error_code == "RATE_LIMIT":.*?(?=\n\s*if response\.error_code:)', '', content, flags=re.DOTALL) # clean old patch if any
content = content.replace("        if response.error_code:", patch)

with open("kernel/orchestration/layer0_wisdom.py", "w", encoding="utf-8") as f:
    f.write(content)
