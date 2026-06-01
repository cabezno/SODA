import asyncio
import json
import re
from typing import Dict, List, Optional, Any, Callable
from kernel.validators.v2.polyglot_validator import PolyglotValidator

class RecursiveCouncilAgent:
    """
    RC3: Recursive Council of Three Agent.
    Implements a sequential, append-only consensus protocol.
    
    1. Gemini (Creator): Generates base.
    2. Claude (Critic 1): Appends Extension A (Cannot modify base).
    3. DeepSeek (Critic 2): Appends Extension B (Reads base + A).
    4. Gemini (Master): Final Merge of base + A + B.
    """

    def __init__(self, ai_hub, notify_fn: Optional[Callable] = None):
        self.ai_hub = ai_hub
        self.notify = notify_fn

    def _log(self, msg: str, event_type: str = "LOG"):
        if self.notify:
            self.notify(msg, event_type)
        else:
            print(f"[{event_type}] {msg}")

    async def execute_chunk(
        self,
        task_desc: str,
        context: str,
        target_files: List[str],
        output_limit: int = 8192,
        schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes the RC3 protocol for a single chunk of work.
        Soporta validación de esquema si se proporciona.
        """
        self._log(f"Iniciando RC3 para chunk: {task_desc[:50]}...", "PHASE_START")

        # --- Helper for Robust Calls ---
        async def safe_call(provider_name: str, sys_p: str, user_m: str, max_t: int = 4096) -> str:
            try:
                resp = await self.ai_hub.get(provider_name).call(system_prompt=sys_p, user_message=user_m, max_tokens=max_t)
                if "ERROR:EXHAUSTED" in resp.content or "API limit reached" in resp.content:
                    raise RuntimeError(f"Proveedor {provider_name} agotado.")
                return resp.content
            except Exception as e:
                self._log(f"Fallo en {provider_name}: {e}. Buscando alternativa...", "WARNING")
                return await self.ai_hub.call_with_fallback(primary=provider_name, role="RC3_Step", task=f"{sys_p}\n\n{user_m}")

        # Configuración de Formato
        if schema:
            format_rule = f"FORMATO OBLIGATORIO: JSON PURO acorde a este esquema:\n{json.dumps(schema, indent=2)}\nREGLA: Responde ÚNICAMENTE con el objeto JSON."
        else:
            format_rule = "FORMATO OBLIGATORIO: <FILE path='...'> código </FILE>.\nREGLA: Entrega el código íntegro sin placeholders."

        # --- 1. CREADOR ---
        self._log("Fase 1: Generando borrador inicial...", "LOG")
        creator_prompt = (
            "Eres el CREADOR de SODA FUSION. Tu misión es generar el contenido para esta sección.\n"
            f"REGLAS:\n1. Usa el CONTEXTO COMPLETO para asegurar integración.\n"
            f"2. {format_rule}\n\n"
            f"CONTEXTO:\n{context}\n\n"
            f"TAREA ACTUAL: {task_desc}\n"
            f"RUTAS (si aplica): {', '.join(target_files)}"
        )
        base_content = await safe_call("gemini", creator_prompt, "Genera el borrador inicial.")

        # --- 2. REVISOR (EXTENSIÓN A) ---
        self._log("Fase 2: Agregando Extensión A (Análisis Crítico)...", "LOG")
        claude_prompt = (
            "Eres el REVISOR ANALÍTICO de SODA. Tu misión es corregir el borrador del Creador.\n"
            "REGLA CRÍTICA: Tienes PROHIBIDO modificar el texto original. Solo puedes proponer mejoras mediante EXTENSIONES.\n"
            "Si algo falta o está mal conectado, descríbelo en el anexo.\n"
            f"FORMATO: <EXTENSION_A> ... </EXTENSION_A>\n\n"
            f"CONTEXTO:\n{context}"
        )
        claude_msg = f"BORRADOR DEL CREADOR:\n{base_content}"
        extension_a = await safe_call("claude", claude_prompt, claude_msg)

        # --- 3. AUDITOR (EXTENSIÓN B) ---
        self._log("Fase 3: Agregando Extensión B (Auditoría Técnica)...", "LOG")
        deepseek_prompt = (
            "Eres el AUDITOR TÉCNICO de SODA. Tu misión es detectar fallos técnicos o de integración.\n"
            "REGLA CRÍTICA: Tienes PROHIBIDO modificar el texto original o la Extensión A. Solo puedes agregar tu propio anexo.\n"
            "FORMATO: <EXTENSION_B> ... </EXTENSION_B>\n\n"
            f"CONTEXTO:\n{context}"
        )
        deepseek_msg = f"BORRADOR:\n{base_content}\n\nEXTENSION A:\n{extension_a}"
        extension_b = await safe_call("deepseek", deepseek_prompt, deepseek_msg)

        # --- 4. JUEZ SUPREMO (ARBITRAJE Y FUSIÓN) ---
        self._log("Fase 4: Juez Supremo realizando Fusión Maestra...", "LOG")
        master_prompt = (
            "Eres el JUEZ SUPREMO de SODA. Tu palabra es la ley de coordinación final.\n"
            "Misión: Decidir la implementación final de esta sección.\n\n"
            "REGLAS DE MANDO:\n"
            "1. Evalúa las extensiones de Claude y DeepSeek.\n"
            f"2. {format_rule}\n\n"
            f"CONTEXTO COMPLETO:\n{context}"
        )
        master_msg = (
            f"BORRADOR ORIGINAL:\n{base_content}\n\n"
            f"EXTENSIÓN CLAUDE (ANEXO A):\n{extension_a}\n\n"
            f"EXTENSIÓN DEEPSEEK (ANEXO B):\n{extension_b}"
        )
        final_content = await safe_call("gemini", master_prompt, master_msg, max_t=output_limit)
        
        # --- RETURN LOGIC ---
        if schema:
            # Si hay esquema, devolvemos el JSON parseado directamente
            match = re.search(r'\{.*\}', final_content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except: pass
            
            # Si el juez falló, intentamos extraer JSON del Creador como último recurso
            match_creator = re.search(r'\{.*\}', base_content, re.DOTALL)
            if match_creator:
                try:
                    return json.loads(match_creator.group(0))
                except: pass

            return {"error": "Failed to parse structured response from RC3"}

        return PolyglotValidator.extract_files(final_content)
