import asyncio
import json
import re
from pathlib import Path
from typing import Optional


class WisdomObservation:
    def __init__(self, obs_type: str, message: str, suggestion: str = ""):
        self.type = obs_type
        self.message = message
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        return {"type": self.type, "message": self.message, "suggestion": self.suggestion}


class WisdomAgent:
    def __init__(self, gemini_driver, context_builder, ai_hub=None, notify_fn: Optional[Callable] = None):
        self.gemini = gemini_driver
        self.builder = context_builder
        self.ai_hub = ai_hub
        self.notify = notify_fn

    def _log(self, msg: str, event_type: str = "LOG"):
        if self.notify:
            self.notify(msg, event_type)
        else:
            print(f"[{event_type}] {msg}")

    async def analyze(
        self,
        description: str,
        skills: list[str],
        profile: str,
        workspace: Optional[Path] = None,
    ) -> list[WisdomObservation]:
        self._log("Iniciando análisis de sabiduría RC3...", "PHASE_START")
        
        # 1. Preparar contexto de tarea
        task_parts = [
            f"PROJECT DESCRIPTION:\n{description}\n\n"
            f"MATCHED PROFILE: {profile}\n"
            f"MATCHED SKILLS: {', '.join(skills) or 'none'}"
        ]
        task = "\n\n".join(task_parts)

        # Si no hay ai_hub, usamos el modo lineal antiguo (fallback)
        if not self.ai_hub:
            payload = self.builder.build_payload("gemini", "wisdom_agent", task)
            raw = (await self.gemini.call(payload["system"], payload["user"])).content
            return self._parse(raw)

        # --- RC3 PROTOCOL: Wisdom Edition ---
        
        # A. GEMINI: Borrador de Observaciones
        self._log("Gemini: Analizando ambigüedades iniciales...", "LOG")
        payload = self.builder.build_payload("gemini", "wisdom_agent", task)
        resp = await self.gemini.call(payload["system"], payload["user"])
        base_obs = resp.content

        # B. CLAUDE: Extensión A (Faltantes de negocio)
        self._log("Claude: Buscando omisiones de lógica y negocio...", "LOG")
        claude_sys = "Eres el Revisor de Requerimientos de SODA. Prohibido borrar. Agrega una <EXTENSION_A> con preguntas o dudas de negocio."
        resp_a = await self.ai_hub.get("claude").call(system_prompt=claude_sys, user_message=f"REQUERIMIENTO:\n{description}\n\nOBSERVACIONES GEMINI:\n{base_obs}")
        ext_a = resp_a.content

        # C. DEEPSEEK: Extensión B (Auditoría Técnica)
        self._log("DeepSeek: Evaluando viabilidad técnica y seguridad...", "LOG")
        deep_sys = "Eres el Auditor Técnico de SODA. Prohibido borrar. Agrega una <EXTENSION_B> con riesgos técnicos o de infraestructura."
        resp_b = await self.ai_hub.get("deepseek").call(system_prompt=deep_sys, user_message=f"REQUERIMIENTO:\n{description}\n\nCONSEJO PREVIO:\n{base_obs}\n{ext_a}")
        ext_b = resp_b.content

        # D. GEMINI: Fusión Maestra de Sabiduría
        self._log("Gemini: Consolidando informe final de sabiduría...", "LOG")
        master_sys = (
            "Eres el Juez de Sabiduría de SODA. Tu misión es unificar el análisis.\n"
            "SALIDA: Un JSON puro con 'observations': [{type, message, suggestion}]."
        )
        master_user = f"REQUERIMIENTOS: {description}\n\nINFORME GEMINI: {base_obs}\n\nEXT_A: {ext_a}\n\nEXT_B: {ext_b}"
        final_resp = await self.gemini.call(system_prompt=master_sys, user_message=master_user, response_format="json")
        
        return self._parse(final_resp.content)

    def _parse(self, text: str) -> list[WisdomObservation]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return []
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return []

        observations = []
        for obs in data.get("observations", []):
            observations.append(WisdomObservation(
                obs_type=obs.get("type", "warning"),
                message=obs.get("message", ""),
                suggestion=obs.get("suggestion", ""),
            ))
        return observations
