import re

with open("kernel/drivers/gemini_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

patch = """        client = self._get_client()
        target_model = model or self.active_model or self.candidate_models[0]
        
        import asyncio
        for retry_attempt in range(5):
            try:
                response = await client.post(
                    self._url(target_model),
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                if response.status_code == 429 and retry_attempt < 4:
                    if "depleted" in response.text.lower() or "billing" in response.text.lower():
                        # Hard fail
                        content_err = self._classify_http_error(response.status_code, response.text)
                        return self._build_response(content="ERROR:QUOTA_EXHAUSTED: La API de Gemini se ha quedado sin créditos o requiere configuración de facturación.", system_prompt=system_prompt, user_message=user_message, latency_start=t0, model_used=target_model, metadata=metadata)
                    
                    wait_time = 20 * (retry_attempt + 1)
                    print(f"  [Gemini] RATE LIMIT (429) en Capa {metadata.get('layer', 'X') if metadata else 'X'}. Esperando {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                if response.status_code != 200:
                    if response.status_code == 429: # Exhausted all retries
                        return self._build_response(
                            content="ERROR:RATE_LIMIT: Gemini — cuota agotada o demasiadas solicitudes",
                            system_prompt=system_prompt,
                            user_message=user_message,
                            latency_start=t0,
                            model_used=target_model,
                            metadata=metadata,
                        )
                    print(f"  [Gemini] HTTP {response.status_code} — modelo={target_model} — body: {response.text[:400]}")
                    content_err = self._classify_http_error(response.status_code, response.text)
                    return self._build_response(
                        content=content_err,
                        system_prompt=system_prompt,
                        user_message=user_message,
                        latency_start=t0,
                        model_used=target_model,
                        metadata=metadata,
                    )
                break # Success or non-429 error handled above
"""

# Match the old client.post block
pattern = re.compile(r'\s*client = self\._get_client\(\)\n\s*target_model = model or self\.active_model or self\.candidate_models\[0\].*?break # Success or non-429 error handled above\n', re.DOTALL)

content = pattern.sub("\n" + patch, content)

with open("kernel/drivers/gemini_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
