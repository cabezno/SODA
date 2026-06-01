import asyncio
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

class LiaisonAgent:
    """
    SODA Liaison Agent (The CLI/Chat Interlocutor).
    Maintains session memory, interprets intent, and bridges chat to orchestrator actions.
    """
    def __init__(
        self, 
        gemini_driver, 
        ai_hub=None, 
        workspace: Optional[Path] = None,
        notify_fn: Optional[Callable] = None,
        orchestrator=None
    ):
        self.gemini = gemini_driver
        self.ai_hub = ai_hub
        self.workspace = workspace
        self.notify = notify_fn or (lambda msg, ev, data: None)
        self.orch = orchestrator
        self.history_file = None
        if workspace:
            self.history_file = workspace / ".soda_chat_history.json"

    def _load_history(self) -> List[Dict[str, str]]:
        if self.history_file and self.history_file.exists():
            try:
                return json.loads(self.history_file.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save_history(self, history: List[Dict[str, str]]):
        if self.history_file:
            # Keep only last 20 messages to prevent context bloat
            if len(history) > 20:
                history = history[-20:]
            self.history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")

    async def chat(self, user_message: str, project_meta: Dict[str, Any]) -> str:
        """Processes a user message, maintains history, and returns the AI response."""
        history = self._load_history()
        
        # 1. Intent Analysis & Command Extraction
        command = self._parse_command(user_message)
        if command:
            return f"COMMAND_DETECTED: {command}"

        # 2. Build Context (Blueprint + Architecture + History)
        context = self._build_context(project_meta, history)
        
        # 3. Call AI (with Deep Thinking if requested or if complex)
        self.notify("SODA está pensando...", "CHAT_THINKING")
        
        system_prompt = (
            "Eres el Liaison Agent de SODA (Software Orchestration & Development Agency).\n"
            "Tu misión es ayudar al usuario a definir, iterar y construir proyectos de software.\n"
            "Eres técnico, proactivo y mantienes el contexto de la conversación.\n"
            "Si el usuario parece listo para construir, sugiere el comando /build.\n"
            "Si la solicitud es compleja, razona paso a paso."
        )

        # Try to query GBrain for relevant info on the user message
        gbrain_ctx = ""
        if self.orch and hasattr(self.orch, "gbrain") and self.orch.gbrain.is_available():
            try:
                gbrain_ctx = self.orch.gbrain.get_rag_context(user_message)
            except Exception:
                pass

        # Usar Gemini Pro para el chat por su gran ventana de contexto
        try:
            user_msg_with_brain = f"{context}\n\n{gbrain_ctx}\n\nUSER: {user_message}" if gbrain_ctx else f"{context}\n\nUSER: {user_message}"
            response = await self.gemini.call(
                system_prompt=system_prompt,
                user_message=user_msg_with_brain,
                model="gemini-3.5-flash"
            )
            ai_content = response.content
        except Exception as e:
            ai_content = f"Error en la comunicación con la IA: {str(e)}"

        # 4. Update History
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": ai_content})
        self._save_history(history)

        return ai_content

    def _parse_command(self, message: str) -> Optional[str]:
        if message.startswith("/"):
            return message.split()[0].lower()
        return None

    def _build_context(self, meta: Dict[str, Any], history: List[Dict[str, str]]) -> str:
        blueprint = json.dumps(meta.get("blueprint", {}), indent=2)
        arch = json.dumps(meta.get("architecture", {}), indent=2)
        
        hist_str = ""
        for h in history:
            hist_str += f"{h['role'].upper()}: {h['content']}\n"

        return (
            f"--- CONTEXTO DEL PROYECTO ---\n"
            f"BLUEPRINT ACTUAL: {blueprint}\n"
            f"ARQUITECTURA ACTUAL: {arch}\n\n"
            f"--- HISTORIAL DE CONVERSACIÓN ---\n"
            f"{hist_str}"
        )

    async def extract_hardened_description(self) -> str:
        """
        Consolida el historial de chat en una descripción técnica detallada
        para ser usada por el motor de construcción (OMEGA).
        """
        history = self._load_history()
        if not history:
            return ""

        self.notify("SODA está consolidando los requerimientos de la charla...", "CHAT_CONSOLIDATING")
        
        hist_str = ""
        for h in history:
            hist_str += f"{h['role'].upper()}: {h['content']}\n"

        system_prompt = (
            "Eres el Analista de Requerimientos de SODA.\n"
            "Tu tarea es leer una conversación entre un usuario y SODA y generar "
            "una descripción técnica UNIFICADA y DETALLADA para construir el software.\n"
            "Elimina la charla social, quédate solo con las decisiones técnicas, stack, "
            "funcionalidades y arquitectura decididas.\n"
            "SALIDA: Una descripción técnica en Markdown lista para ser procesada."
        )

        try:
            # FASE CRÍTICA: Usamos Claude 3 Opus para garantizar precisión arquitectónica
            # Si no está disponible, el ai_hub hará el fallback a Gemini Pro automáticamente.
            consolidator = self.ai_hub.get("claude") if self.ai_hub else self.gemini
            model_name = "claude-3-opus-latest" if self.ai_hub else "gemini-3.5-flash"

            response = await consolidator.call(
                system_prompt=system_prompt,
                user_message=f"HISTORIAL DE CHAT:\n{hist_str}",
                model=model_name
            )
            return response.content
        except Exception:
            # Fallback a la última descripción conocida
            return history[-1]["content"] if history else ""

    async def extract_blueprint_update(self, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Analiza la historia para extraer cambios sugeridos al blueprint."""
        # TODO: Implementar lógica de extracción con Claude para precisión quirúrgica
        pass
