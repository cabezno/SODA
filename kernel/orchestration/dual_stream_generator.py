import asyncio
import re
import json
from typing import Dict, List, Callable, Optional
from pathlib import Path

class DualStreamGenerator:
    """
    Implementa la arquitectura Actor-Crítico (Dual-Stream) para generación de código de alta fidelidad.
    Stream A (Actor): Genera fragmentos de código.
    Stream B (Crítico): Evalúa y ajusta en tiempo real (Cross-Attention algorítmico).
    """
    def __init__(self, ai_hub, notify_fn: Callable, workspace: Optional[Path] = None):
        self.ai_hub = ai_hub
        self._notify = notify_fn
        self.workspace = workspace

    async def generate(
        self,
        contract,
        generated_code_map: Dict[str, str],
        actual_lang: str,
        skill_knowledge: str = "",
        is_frontend: bool = False,
        frontend_output_names: List[str] = None,
        qa_fn: Callable = None,
        stream_a_model: str = "gemini-3-flash-preview",
        stream_b_model: str = "deepseek-chat"
    ) -> Dict[str, str]:
        self._notify("LOG", f"  [DualStream] Activando Actor-Crítico para '{contract.contract_id}' (A={stream_a_model} / B={stream_b_model}, rondas=3)")
        
        # Estado del desarrollo compartido
        current_files: Dict[str, str] = {}
        history_a = []
        history_b = []
        
        # 1. Preparar contexto de dependencias
        dep_ctx = ""
        if contract.dependencies:
            for dep_id in contract.dependencies:
                if dep_id in generated_code_map:
                    dep_ctx += f"\n--- DEPENDENCY {dep_id} ---\n{generated_code_map[dep_id][:1000]}\n"

        for round_idx in range(1, 4):
            self._notify("LOG", f"  [DualStream] ── Ronda {round_idx}/3 ──")
            
            # --- STREAM A: EL ACTOR (Generador) ---
            sys_a = (
                f"You are Stream A: The Coder. Your goal is to implement the contract in {actual_lang}.\n"
                "You must use the <FILE path='...'>...</FILE> protocol for every file.\n"
                "REGLA: No generes esqueletos. Implementación completa."
            )
            if history_b:
                sys_a += f"\n\nCRITICAL FEEDBACK FROM STREAM B (ADJUST YOUR CODE):\n{history_b[-1]}"
            
            user_a = f"CONTRACT:\n{contract.model_dump_json()}\n\nDEPENDENCIES:\n{dep_ctx}"
            
            driver_a = self.ai_hub.get(stream_a_model)
            resp_a = await driver_a.call(system_prompt=sys_a, user_message=user_a, metadata={"phase": "DualStream-A", "node": contract.contract_id})
            
            from kernel.validators.v2.polyglot_validator import PolyglotValidator
            new_files = PolyglotValidator.extract_files(resp_a.content)
            current_files.update(new_files)
            
            # --- STREAM B: EL CRÍTICO (Cross-Attention) ---
            sys_b = (
                "You are Stream B: The Technical Judge. Perform Cross-Attention between the CONTRACT and the GENERATED CODE.\n"
                "Verify: 1. Naming consistency. 2. Implementation completeness. 3. Contract output symbols.\n"
                "If it's perfect, respond with 'APPROVE'. Otherwise, list exact technical adjustments needed."
            )
            
            code_summary = "\n".join([f"FILE: {p}\n{c}" for p, c in current_files.items()])
            user_b = f"CONTRACT:\n{contract.model_dump_json()}\n\nGENERATED_CODE:\n{code_summary}"
            
            driver_b = self.ai_hub.get(stream_b_model)
            resp_b = await driver_b.call(system_prompt=sys_b, user_message=user_b, metadata={"phase": "DualStream-B", "node": contract.contract_id})
            
            feedback_b = resp_b.content.strip()
            history_b.append(feedback_b)
            
            if "APPROVE" in feedback_b.upper():
                # Validacion final de QA para asegurar que no se nos escape nada
                # QA round espera un solo string, unimos archivos para auditoria funcional
                combined_code = "\n\n".join(current_files.values())
                approved, qa_err = await qa_fn(contract, combined_code, actual_lang)
                if approved:
                    self._notify("SUCCESS", f"  [DualStream] Stream A aprobado en ronda {round_idx}.")
                    return current_files
                else:
                    history_b.append(f"QA Failed: {qa_err}")
            else:
                self._notify("LOG", f"  [DualStream] Stream B propuso ajustes (ronda {round_idx}).")

        # Si agotamos rondas, intentamos un merge final o lanzamos error
        if current_files:
            return current_files
        raise RuntimeError("DualStream exhausted all rounds without valid approval.")
