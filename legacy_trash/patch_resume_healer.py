import re
from pathlib import Path

f = Path("kernel/orchestrator.py")
content = f.read_text(encoding="utf-8")

# 1. Setup in resume()
res_setup_target = """\
        try:
            from kernel.intelligence.finops_router import FinopsRouter
            from kernel.orchestration.recursive_engine import SodaRecursiveEngine
            from kernel.core.models_v2 import SodaContract
            from kernel.utils.language_detector import detect_language
            
            profile_name = project.profile or "balanced"
            lineup = FinopsRouter.get_lineup(profile_name)
"""
res_setup_replace = """\
        try:
            from kernel.intelligence.finops_router import FinopsRouter
            from kernel.orchestration.recursive_engine import SodaRecursiveEngine
            from kernel.core.models_v2 import SodaContract
            from kernel.utils.language_detector import detect_language
            from kernel.selfrepair.runtime_healer import RuntimeHealer
            
            profile_name = project.profile or "balanced"
            lineup = FinopsRouter.get_lineup(profile_name)
            healer = RuntimeHealer(self.gemini, notify_wrapper)

            async def _healable(phase_name, fn):
                for attempt in range(1, 4):
                    try:
                        return await fn()
                    except Exception as e:
                        if attempt == 3 or not await healer.handle_exception(e):
                            raise e
                        notify_wrapper("LOG", f"Reintentando {phase_name} tras autoreparación de SODA (Intento {attempt + 1}/3)...")
"""
content = content.replace(res_setup_target, res_setup_replace)

# 2. Branch 1
b1_target = """\
                if atomic_pending:
                    await engine.execute_bottom_up(contracts_pool)
"""
b1_replace = """\
                if atomic_pending:
                    async def _desarrollo():
                        from kernel.orchestration.recursive_engine import SodaRecursiveEngine
                        _engine = SodaRecursiveEngine(gemini_driver=self.gemini, ollama_driver=self.ollama, lineup=lineup, stack_language=lang, notify_fn=notify_wrapper, save_file_fn=save_file_wrapper, workspace=project.workspace, ai_hub=self.ai_hub)
                        return await _engine.execute_bottom_up(contracts_pool)
                    await _healable("Fase de Desarrollo (Resume)", _desarrollo)
"""
content = content.replace(b1_target, b1_replace)

# 3. Branch 2 - Decompose
b2_target_d = """\
                notify_wrapper("PHASE_START", "Fase de Arquitectura: Descomposición Recursiva")
                all_contracts = await engine.decompose_tree(root_contract)
"""
b2_replace_d = """\
                notify_wrapper("PHASE_START", "Fase de Arquitectura: Descomposición Recursiva")
                async def _capa2():
                    from kernel.orchestration.recursive_engine import SodaRecursiveEngine
                    _engine = SodaRecursiveEngine(gemini_driver=self.gemini, ollama_driver=self.ollama, lineup=lineup, stack_language=lang, notify_fn=notify_wrapper, save_file_fn=save_file_wrapper, workspace=project.workspace, ai_hub=self.ai_hub)
                    return await _engine.decompose_tree(root_contract)
                all_contracts = await _healable("Fase de Arquitectura", _capa2)
"""
content = content.replace(b2_target_d, b2_replace_d)

# 4. Branch 2 & 3 - Bottom-Up (match by lines)
# Wait, "await engine.execute_bottom_up(all_contracts)" appears twice more (once in branch 2, once in branch 3)
content = content.replace(
    'await engine.execute_bottom_up(all_contracts)',
    '''async def _desarrollo_all():
                    from kernel.orchestration.recursive_engine import SodaRecursiveEngine
                    _engine = SodaRecursiveEngine(gemini_driver=self.gemini, ollama_driver=self.ollama, lineup=lineup, stack_language=lang, notify_fn=notify_wrapper, save_file_fn=save_file_wrapper, workspace=project.workspace, ai_hub=self.ai_hub)
                    return await _engine.execute_bottom_up(all_contracts)
                await _healable("Fase de Desarrollo", _desarrollo_all)'''
)

f.write_text(content, encoding="utf-8")
print("Orchestrator parcheado (RESUME).")
