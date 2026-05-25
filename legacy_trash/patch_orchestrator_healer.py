import re
from pathlib import Path

f = Path("kernel/orchestrator.py")
content = f.read_text(encoding="utf-8")

run_target = """\
        try:
            from kernel.intelligence.finops_router import FinopsRouter
            profile_name = project.profile
            lineup = FinopsRouter.get_lineup(profile_name)

            # --- CAPA 0: WISDOM ---
"""
run_replacement = """\
        try:
            from kernel.intelligence.finops_router import FinopsRouter
            from kernel.selfrepair.runtime_healer import RuntimeHealer
            from kernel.utils.language_detector import detect_language
            
            profile_name = project.profile
            lineup = FinopsRouter.get_lineup(profile_name)
            lang = detect_language(project.skills or [])
            healer = RuntimeHealer(self.gemini, notify_wrapper)

            async def _healable(phase_name, fn):
                for attempt in range(1, 4):
                    try:
                        return await fn()
                    except Exception as e:
                        if attempt == 3 or not await healer.handle_exception(e):
                            raise e
                        notify_wrapper("LOG", f"Reintentando {phase_name} tras autoreparación de SODA (Intento {attempt + 1}/3)...")

            # --- CAPA 0: WISDOM ---
"""
content = content.replace(run_target, run_replacement)

c0_target = """\
            final_description = await resolve_ambiguities(
                user_prompt=description,
                gemini_driver=self.gemini,
                ask_user_fn=ask_user_wrapper,
                notify_fn=notify_wrapper,
                model_name=lineup.layer0_wisdom
            )
"""
c0_replacement = """\
            async def _capa0():
                from kernel.orchestration.layer0_wisdom import resolve_ambiguities
                return await resolve_ambiguities(
                    user_prompt=description,
                    gemini_driver=self.gemini,
                    ask_user_fn=ask_user_wrapper,
                    notify_fn=notify_wrapper,
                    model_name=lineup.layer0_wisdom
                )
            final_description = await _healable("Capa 0: Análisis", _capa0)
"""
content = content.replace(c0_target, c0_replacement)

c1_target = """\
            root_contract = await generate_root_contract(
                user_description=project.description,
                active_skills=project.skills or [],
                gemini_driver=self.gemini,
                notify_fn=notify_wrapper,
                ai_hub=self.ai_hub
            )
"""
c1_replacement = """\
            async def _capa1():
                from kernel.orchestration.genesis import generate_root_contract
                return await generate_root_contract(
                    user_description=project.description,
                    active_skills=project.skills or [],
                    gemini_driver=self.gemini,
                    notify_fn=notify_wrapper,
                    ai_hub=self.ai_hub
                )
            root_contract = await _healable("Capa 1: Génesis", _capa1)
"""
content = content.replace(c1_target, c1_replacement)

c2_target = """\
            notify_wrapper("PHASE_START", "Fase de Arquitectura: Descomposición Recursiva")
            all_contracts = await engine.decompose_tree(root_contract)
"""
c2_replacement = """\
            notify_wrapper("PHASE_START", "Fase de Arquitectura: Descomposición Recursiva")
            async def _capa2():
                from kernel.orchestration.recursive_engine import SodaRecursiveEngine
                _engine = SodaRecursiveEngine(
                    gemini_driver=self.gemini,
                    ollama_driver=self.ollama,
                    lineup=lineup,
                    stack_language=lang,
                    notify_fn=notify_wrapper,
                    save_file_fn=save_file_wrapper,
                    workspace=project.workspace,
                    ai_hub=self.ai_hub
                )
                return await _engine.decompose_tree(root_contract)
            all_contracts = await _healable("Fase de Arquitectura", _capa2)
"""
content = content.replace(c2_target, c2_replacement)

bu_target = """\
            notify_wrapper("PHASE_START", "Fase de Desarrollo: Ejecución Bottom-Up Concurrente")
            await engine.execute_bottom_up(all_contracts)
"""
bu_replacement = """\
            notify_wrapper("PHASE_START", "Fase de Desarrollo: Ejecución Bottom-Up Concurrente")
            async def _desarrollo():
                from kernel.orchestration.recursive_engine import SodaRecursiveEngine
                _engine = SodaRecursiveEngine(
                    gemini_driver=self.gemini,
                    ollama_driver=self.ollama,
                    lineup=lineup,
                    stack_language=lang,
                    notify_fn=notify_wrapper,
                    save_file_fn=save_file_wrapper,
                    workspace=project.workspace,
                    ai_hub=self.ai_hub
                )
                return await _engine.execute_bottom_up(all_contracts)
            await _healable("Fase de Desarrollo", _desarrollo)
"""
content = content.replace(bu_target, bu_replacement)

f.write_text(content, encoding="utf-8")
print("Orchestrator parcheado (RUN).")
