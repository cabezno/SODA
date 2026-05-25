import re

with open("kernel/orchestration/recursive_engine.py", "r", encoding="utf-8") as f:
    content = f.read()

# I want to inject a file write right after Qwen returns
patch = """            response = await self.ollama.prompt(
                system=system_prompt,
                user=contract.model_dump_json()
            )
            source_code = response.strip()
            
            # --- DEBUG QWEN OUTPUT ---
            try:
                with open(f"DEBUG_QWEN_{contract.contract_id}_ATTEMPT_{attempt+1}.txt", "w", encoding="utf-8") as fdbg:
                    fdbg.write(source_code)
            except Exception:
                pass
            # -------------------------
"""

content = re.sub(
    r'            response = await self\.ollama\.prompt\(\n\s*system=system_prompt,\n\s*user=contract\.model_dump_json\(\)\n\s*\)\n\s*source_code = response\.strip\(\)',
    patch,
    content
)

with open("kernel/orchestration/recursive_engine.py", "w", encoding="utf-8") as f:
    f.write(content)
