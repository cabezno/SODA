import asyncio
import json
import re
from typing import Dict, List, Optional, Any, Callable

class RecursivePlannerCouncil:
    """
    IMP-031: Recursive Planning Council (RPC).
    Coordinates a 3-way negotiation to create a granular execution plan for massive tasks.
    
    1. DeepSeek-R1 (Architect): Proposes atomic checklist.
    2. Gemini 3.5 (Critical Auditor): Critiques and adds edge cases.
    3. Claude 3.5 (Structural Reviewer): Critiques and ensures modularity.
    4. DeepSeek-R1 (Master): Synthesizes final plan from critiques.
    """

    def __init__(self, ai_hub, notify_fn: Optional[Callable] = None):
        self.ai_hub = ai_hub
        self.notify = notify_fn

    def _log(self, msg: str, event_type: str = "LOG"):
        if self.notify:
            self.notify(msg, event_type)
        else:
            print(f"[{event_type}] [RPC] {msg}")

    async def negotiate_plan(self, task_desc: str, context: str) -> List[Dict[str, str]]:
        """
        Negotiates a step-by-step execution plan using the Council of Three.
        Returns a list of atomic tasks.
        """
        self._log(f"Iniciando Negociación de Plan para tarea masiva: {task_desc[:50]}...", "PHASE_START")

        async def safe_call(provider: str, sys_p: str, user_m: str) -> str:
            try:
                resp = await self.ai_hub.get(provider).call(system_prompt=sys_p, user_message=user_m, max_tokens=4000)
                return resp.content
            except:
                return await self.ai_hub.call_with_fallback(primary=provider, role="PLANNER", task=f"{sys_p}\n\n{user_m}")

        # 1. DEEPSEEK-R1: DRAFT PLAN
        self._log("DeepSeek-R1 generando borrador de plan atómico...", "LOG")
        ds_sys = (
            "Eres el Arquitecto Jefe de DeepSeek. Tu misión es descomponer una tarea masiva en un PLAN DE ACCIÓN ATÓMICO.\n"
            "REGLAS:\n"
            "1. Cada paso debe ser pequeño (máximo 50 líneas de código).\n"
            "2. Define claramente qué archivos se tocan en cada paso.\n"
            "3. Formato: Una lista numerada de pasos técnicos."
        )
        draft_plan = await safe_call("deepseek", ds_sys, f"TAREA: {task_desc}\n\nCONTEXTO:\n{context}")

        # 2. GEMINI 3.5: CRITICAL FEEDBACK
        self._log("Gemini 3.5 auditando borrador (Riesgos y Omisiones)...", "LOG")
        gemini_sys = (
            "Eres el Auditor de Riesgos de SODA. Revisa el plan propuesto por DeepSeek.\n"
            "Busca: Omisiones de seguridad, falta de tests, o pasos demasiado grandes.\n"
            "SALIDA: Una lista de 'Puntos de Mejora' o 'Correcciones Necesarias'."
        )
        gemini_feedback = await safe_call("gemini", gemini_sys, f"PLAN PROPUESTO:\n{draft_plan}")

        # 3. CLAUDE 3.5: STRUCTURAL FEEDBACK
        self._log("Claude 3.5 auditando borrador (Arquitectura y Modularidad)...", "LOG")
        claude_sys = (
            "Eres el Ingeniero de Estructuras de SODA. Revisa el plan propuesto.\n"
            "Busca: Violaciones de modularidad, nombres de archivos inconsistentes o dependencias circulares.\n"
            "SALIDA: Una lista de sugerencias estructurales."
        )
        claude_feedback = await safe_call("claude", claude_sys, f"PLAN PROPUESTO:\n{draft_plan}")

        # 4. DEEPSEEK-R1: FINAL SYNTHESIS
        self._log("DeepSeek-R1 sintetizando Plan Final Consensuado...", "LOG")
        master_sys = (
            "Eres el Arquitecto Maestro. Has recibido feedback de Gemini (Riesgos) y Claude (Estructura).\n"
            "Tu misión es generar el PLAN DE ACCIÓN FINAL INTEGRADO en formato JSON.\n"
            "FORMATO: [{\"id\": \"paso_1\", \"task\": \"descripción\", \"files\": [\"ruta\"]}, ...]\n"
            "MANDATORIO: Responde ÚNICAMENTE con el JSON puro."
        )
        master_user = (
            f"BORRADOR ORIGINAL:\n{draft_plan}\n\n"
            f"FEEDBACK GEMINI:\n{gemini_feedback}\n\n"
            f"FEEDBACK CLAUDE:\n{claude_feedback}"
        )
        final_json_raw = await safe_call("deepseek", master_sys, master_user)
        
        try:
            match = re.search(r'\[.*\]', final_json_raw, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return [{"id": "error", "task": "Fallo al generar plan JSON", "files": []}]
        except:
            self._log("Error al parsear el plan final del consejo.", "ERROR")
            return [{"id": "fallback", "task": task_desc, "files": []}]
