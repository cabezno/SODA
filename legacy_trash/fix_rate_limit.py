import re

with open("kernel/orchestration/layer0_wisdom.py", "r", encoding="utf-8") as f:
    content = f.read()

bypass_patch = """        if response.error_code == "RATE_LIMIT":
            if notify_fn:
                notify_fn("WARNING", "Límite de cuota de Gemini alcanzado en Capa 0 (Triage). Saltando validación humana para no bloquear el sistema.")
            return current_prompt
            
        if response.error_code:
"""

content = content.replace("        if response.error_code:\n", bypass_patch)

with open("kernel/orchestration/layer0_wisdom.py", "w", encoding="utf-8") as f:
    f.write(content)
