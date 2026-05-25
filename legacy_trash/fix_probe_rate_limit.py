import re
with open("kernel/drivers/gemini_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

patch = """                if res.status_code == 429:
                    # Don't abort immediately on rate limit during probe, just move to next model or retry.
                    # Since it's free tier, probing models might hit RPM limit fast.
                    import asyncio
                    print(f"  [Gemini] Probe limit 429 on {model}. Esperando 5s...")
                    await asyncio.sleep(5)
                    continue"""

content = re.sub(
    r'                if res\.status_code == 429:\n\s*return self\._build_response\(\n\s*content="ERROR:RATE_LIMIT: Gemini — cuota agotada al intentar conectar",\n\s*system_prompt=system_prompt,\n\s*user_message=user_message,\n\s*latency_start=t0,\n\s*model_used=model,\n\s*metadata=metadata,\n\s*\)',
    patch, 
    content
)

with open("kernel/drivers/gemini_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
