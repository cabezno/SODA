import asyncio
import json
import re
from typing import Dict, List, Optional, Any, Callable

class CouncilAgent:
    """
    SODA Council Agent: Implements the 'llm-council' pattern for high-fidelity consensus.
    Based on Karpathy's llm-council repository.
    
    Stage 1: Opinions (Parallel Generation)
    Stage 2: Blind Peer Review (Anonymized Cross-Review)
    Stage 3: Chairman Synthesis (Final Decision)
    """

    def __init__(self, ai_hub, notify_fn: Optional[Callable] = None):
        self.ai_hub = ai_hub
        self.notify = notify_fn

    def _log(self, msg: str, event_type: str = "LOG"):
        if self.notify:
            self.notify(msg, event_type)
        else:
            print(f"[{event_type}] {msg}")

    async def convene(
        self,
        task: str,
        system_context: str,
        council_members: List[str] = ["gemini", "claude", "deepseek"],
        chairman: str = "gemini",
        response_format: str = "text"
    ) -> str:
        """
        Convenes a council of LLMs to solve a high-stakes task.
        """
        self._log(f"Convocando al Consejo de IAs: {', '.join(council_members)} (Presidente: {chairman})", "PHASE_START")

        # --- STAGE 1: Opinions ---
        self._log("Etapa 1: Generación de opiniones paralelas...", "LOG")
        opinions = await self._get_opinions(task, system_context, council_members)
        
        if len(opinions) <= 1:
            self._log("No hay suficientes opiniones para un consejo. Retornando respuesta única.", "WARNING")
            return list(opinions.values())[0] if opinions else "Error: No se obtuvieron respuestas."

        # --- STAGE 2: Blind Peer Review ---
        self._log("Etapa 2: Revisión ciega por pares (Peer Review)...", "LOG")
        reviews = await self._get_peer_reviews(task, system_context, opinions, council_members)

        # --- STAGE 2.5: Dynamic Refinement (Multi-turn) ---
        self._log("Etapa 2.5: Refinamiento dinámico (Multi-turn)...", "LOG")
        opinions = await self._refine_opinions(task, system_context, opinions, reviews, council_members)

        # --- STAGE 3: Chairman Synthesis ---
        self._log(f"Etapa 3: Síntesis final por el Presidente ({chairman})...", "LOG")
        final_response = await self._synthesize(task, system_context, opinions, reviews, chairman, response_format)

        self._log("Consejo finalizado con éxito.", "SUCCESS")
        return final_response

    async def _get_opinions(self, task: str, system_context: str, members: List[str]) -> Dict[str, str]:
        tasks = []
        valid_members = []
        for m in members:
            driver = self.ai_hub.get(m)
            if driver:
                tasks.append(driver.call(system_prompt=system_context, user_message=task))
                valid_members.append(m)

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        opinions = {}
        for member, resp in zip(valid_members, responses):
            if isinstance(resp, Exception):
                self._log(f"Fallo en opinión de {member}: {resp}", "ERROR")
                continue
            opinions[member] = resp.content
        return opinions

    async def _get_peer_reviews(self, task: str, system_context: str, opinions: Dict[str, str], members: List[str]) -> Dict[str, str]:
        # Anonymize opinions
        anonymized = []
        id_to_member = {}
        for idx, (member, content) in enumerate(opinions.items()):
            label = f"Modelo_{chr(65+idx)}" # Modelo_A, Modelo_B...
            anonymized.append(f"--- INICIO {label} ---\n{content}\n--- FIN {label} ---")
            id_to_member[label] = member

        opinions_block = "\n\n".join(anonymized)
        
        review_sys = (
            "Eres un experto crítico técnico. Se te presentan varias soluciones propuestas para un problema.\n"
            "Tu tarea es evaluar cada una de forma objetiva, identificando aciertos, errores, omisiones o alucinaciones.\n"
            "Ranking: Al final, proporciona un ranking de las soluciones (ej. 1. Modelo_B, 2. Modelo_A).\n"
            "IMPORTANTE: No conoces la identidad de los modelos. Juzga solo por la calidad técnica."
        )
        
        review_user = f"PROBLEMA ORIGINAL: {task}\n\nCONTEXTO: {system_context}\n\nPROPUESTAS:\n{opinions_block}"
        
        tasks = []
        valid_members = []
        for m in members:
            driver = self.ai_hub.get(m)
            if driver:
                tasks.append(driver.call(system_prompt=review_sys, user_message=review_user))
                valid_members.append(m)

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        reviews = {}
        for member, resp in zip(valid_members, responses):
            if isinstance(resp, Exception):
                continue
            reviews[member] = resp.content
        return reviews

    async def _synthesize(
        self, 
        task: str, 
        system_context: str, 
        opinions: Dict[str, str], 
        reviews: Dict[str, str], 
        chairman: str,
        response_format: str
    ) -> str:
        # Build synthesis context
        opinion_block = ""
        for idx, (member, content) in enumerate(opinions.items()):
            label = f"Modelo_{chr(65+idx)}"
            opinion_block += f"--- OPINION {label} (Propuesta por {member}) ---\n{content}\n\n"

        review_block = ""
        for member, content in reviews.items():
            review_block += f"--- REVISIÓN DE {member} ---\n{content}\n\n"

        sys_p = (
            f"Eres el Presidente del Consejo de Expertos (Chairman). Tu objetivo es producir la RESPUESTA FINAL ÓPTIMA.\n"
            f"Se te proporcionan las propuestas de varios expertos y sus críticas mutuas.\n"
            f"Debes filtrar errores, combinar lo mejor de cada propuesta y asegurar que el resultado final sea perfecto.\n"
            f"FORMATO DE SALIDA: {response_format.upper()}.\n"
            "Si el formato es JSON, asegúrate de que sea parseable y no contenga texto extra."
        )
        
        user_msg = (
            f"REQUERIMIENTO ORIGINAL: {task}\n\n"
            f"CONTEXTO DEL SISTEMA: {system_context}\n\n"
            f"OPINIONES DE LOS EXPERTOS:\n{opinion_block}\n"
            f"CRÍTICAS Y RANKINGS:\n{review_block}\n"
            "Genera la solución final definitiva."
        )

        driver = self.ai_hub.get(chairman)
        if not driver:
            # Fallback to the first available member if chairman fails
            driver = self.ai_hub.get(list(opinions.keys())[0])

        resp = await driver.call(
            system_prompt=sys_p, 
            user_message=user_msg, 
            response_format=response_format,
            max_tokens=8192
        )
        return resp.content

    async def _refine_opinions(
        self, 
        task: str, 
        system_context: str, 
        opinions: Dict[str, str], 
        reviews: Dict[str, str], 
        members: List[str]
    ) -> Dict[str, str]:
        """
        Stage 2.5: Models see the reviews and can refine their original opinion.
        """
        refined_opinions = {}
        review_block = "\n\n".join([f"--- REVISIÓN DE {m} ---\n{c}" for m, c in reviews.items()])
        
        tasks = []
        valid_members = []
        
        for m in members:
            original = opinions.get(m)
            if not original: continue
            
            refine_sys = (
                "Se te ha proporcionado una serie de revisiones técnicas sobre tu propuesta y las de otros expertos.\n"
                "Tu objetivo es REFINAR tu propuesta original basándote en las críticas constructivas recibidas.\n"
                "Si tu propuesta original era correcta, mantenla. Si ves errores señalados por otros, corrígelos.\n"
                "MANTÉN EL ANONIMATO. No menciones tu nombre ni el de otros modelos."
            )
            
            refine_user = (
                f"REQUERIMIENTO: {task}\n\n"
                f"TU PROPUESTA ORIGINAL:\n{original}\n\n"
                f"REVISIONES DEL CONSEJO:\n{review_block}\n\n"
                "Genera tu propuesta REFINADA FINAL."
            )
            
            driver = self.ai_hub.get(m)
            if driver:
                tasks.append(driver.call(system_prompt=refine_sys, user_message=refine_user))
                valid_members.append(m)

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for member, resp in zip(valid_members, responses):
            if isinstance(resp, Exception):
                refined_opinions[member] = opinions[member]
                continue
            refined_opinions[member] = resp.content
            
        return refined_opinions
