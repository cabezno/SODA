import re

with open("kernel/drivers/gemini_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# Let's add an automatic backoff directly in the driver so ALL layers benefit.
backoff_patch = """        # Auto-backoff for Rate Limits (429)
        max_driver_retries = 3
        for drv_attempt in range(max_driver_retries):
            try:
                response = await client.post(
                    self._url(target_model),
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                if response.status_code == 429:
                    if drv_attempt < max_driver_retries - 1:
                        await asyncio.sleep(10 * (drv_attempt + 1))
                        continue
                if response.status_code != 200:
                    content = self._classify_http_error(response.status_code, response.text)
                    return self._build_response(content=content, system_prompt=system_prompt, user_message=user_message, latency_start=t0, model_used=target_model, metadata=metadata)
                break
            except httpx.ConnectError:
                return self._build_response(content="ERROR:CONNECTION: Gemini — sin conexión a internet", system_prompt=system_prompt, user_message=user_message, latency_start=t0, model_used=target_model, metadata=metadata)
            except httpx.TimeoutException:
                if drv_attempt < max_driver_retries - 1:
                    continue
                return self._build_response(content="ERROR:TIMEOUT: Gemini — tiempo de espera agotado (>120s)", system_prompt=system_prompt, user_message=user_message, latency_start=t0, model_used=target_model, metadata=metadata)
"""

# I need to match the existing try/except block in the driver.
# The original code looks like:
#         try:
#             response = await client.post(
#                 self._url(target_model),
#                 headers={"Content-Type": "application/json"},
#                 json=payload,
#             )
#             if response.status_code != 200:
#                 print(...)
#                 return self._build_response(...)
#             
#             res_json = response.json()
#         except httpx...

# We'll just replace the client.post block with a small sleep if status == 429.
