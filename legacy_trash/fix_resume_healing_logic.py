import re
from pathlib import Path

f = Path("kernel/orchestrator.py")
content = f.read_text(encoding="utf-8")

# Corregir el bloque resume() para incluir _healable en Capa 0 y Capa 1
# Buscamos la sección de Capa 0 en resume()
c0_target = """\
                from kernel.orchestration.layer0_wisdom import resolve_ambiguities
                final_description = await resolve_ambiguities(
                    user_prompt=project.description,
                    gemini_driver=self.gemini,
                    ask_user_fn=ask_user_wrapper,
                    notify_fn=notify_wrapper,
                    model_name=lineup.layer0_wisdom
                )
"""
c0_replacement = """\
                async def _capa0_res():
                    from kernel.orchestration.layer0_wisdom import resolve_ambiguities
                    return await resolve_ambiguities(
                        user_prompt=project.description,
                        gemini_driver=self.gemini,
                        ask_user_fn=ask_user_wrapper,
                        notify_fn=notify_wrapper,
                        model_name=lineup.layer0_wisdom
                    )
                final_description = await _healable("Capa 0: Análisis", _capa0_res)
"""

# Corregir Capa 1 en resume()
c1_target = """\
                from kernel.orchestration.genesis import generate_root_contract
                root_contract = await generate_root_contract(
                    user_description=project.description,
                    active_skills=project.skills or [],
                    gemini_driver=self.gemini,
                    notify_fn=notify_wrapper,
                    ai_hub=self.ai_hub
                )
"""
c1_replacement = """\
                async def _capa1_res():
                    from kernel.orchestration.genesis import generate_root_contract
                    return await generate_root_contract(
                        user_description=project.description,
                        active_skills=project.skills or [],
                        gemini_driver=self.gemini,
                        notify_fn=notify_wrapper,
                        ai_hub=self.ai_hub
                    )
                root_contract = await _healable("Capa 1: Génesis", _capa1_res)
"""

if c0_target in content:
    content = content.replace(c0_target, c0_replacement)
    print("Capa 0 (Resume) corregida.")

if c1_target in content:
    content = content.replace(c1_target, c1_replacement)
    print("Capa 1 (Resume) corregida.")

f.write_text(content, encoding="utf-8")
