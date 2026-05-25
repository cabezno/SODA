import re

with open("kernel/drivers/gemini_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add handling for RESOURCE_EXHAUSTED / Depleted Credits
patch = """                if response.status_code == 429 and retry_attempt < 2:
                    if "depleted" in response.text.lower() or "billing" in response.text.lower():
                        # Hard fail, waiting won't help if credits are 0
                        content = self._classify_http_error(response.status_code, response.text)
                        return self._build_response(content="ERROR:QUOTA_EXHAUSTED: La API de Gemini se ha quedado sin créditos o requiere configuración de facturación.", system_prompt=system_prompt, user_message=user_message, latency_start=t0, model_used=target_model, metadata=metadata)
                    print(f"  [Gemini] RATE LIMIT (429). Esperando {15 * (retry_attempt + 1)}s...")"""

content = content.replace("                if response.status_code == 429 and retry_attempt < 2:\n                    print(f\"  [Gemini] RATE LIMIT (429). Esperando {15 * (retry_attempt + 1)}s...\")", patch)

with open("kernel/drivers/gemini_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
