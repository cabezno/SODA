import re

with open("ui/server.py", "r", encoding="utf-8") as f:
    content = f.read()

import_patch = """            from kernel.orchestration.recursive_engine import SodaRecursiveEngine
            from kernel.drivers.gemini_driver import GeminiDriver
            from kernel.drivers.ollama_driver import OllamaDriver
            import asyncio
            from kernel.core.models_v2 import SodaContract, ContractInterface, DynamicPersona
            
            # --- SODA V2 INJECTION ---
            if "v2" in description.lower():
                root_contract = SodaContract(
                    contract_id="root",
                    level=0,
                    title="V2 System Root",
                    description=description,
                    is_atomic=False,
                    dynamic_persona=DynamicPersona(target_role="System Architect", required_skills=[]),
                    interface=ContractInterface()
                )
                engine = SodaRecursiveEngine(GeminiDriver(), OllamaDriver())
                pool = await engine.decompose_tree(root_contract)
                code_map = await engine.execute_bottom_up(pool)
                await _telegram.send_from_loop(f"✅ V2 Pipeline completado con {len(code_map)} módulos atómicos.")
                _pipeline_running = False
                return
            # -------------------------
"""

content = content.replace("            orchestrator = SodaOrchestrator(copilot_temperature=copilot_temperature)", import_patch + "\n            orchestrator = SodaOrchestrator(copilot_temperature=copilot_temperature)")

with open("ui/server.py", "w", encoding="utf-8") as f:
    f.write(content)
