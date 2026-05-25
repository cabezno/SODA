import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from kernel.validators.v2.polyglot_validator import PolyglotValidator

class DeepThinkingAnalyzer:
    """
    SODA Deep Thinking Analysis Layer.
    Executes a forensic audit of the project at the end of the pipeline.
    Uses Gemini 2.0 Flash (latest available) for high-context cognitive feedback.
    """

    def __init__(self, ai_hub, notify_fn: Optional[Callable] = None):
        self.ai_hub = ai_hub
        self.notify = notify_fn
        # Prefer Gemini 3.5 Flash for Deep Thinking as requested by the user
        self.model = ai_hub.get("gemini-3.5-flash") or ai_hub.get("gemini")

    def _log(self, msg: str, event_type: str = "LOG"):
        if self.notify:
            self.notify(msg, event_type)
        else:
            print(f"[{event_type}] [DEEP_THINKING] {msg}")

    async def generate_forensic_report(self, project_path: Path, mission_desc: str) -> str:
        """
        Gathers all project artifacts and generates a comprehensive performance and improvement report.
        Includes a loopback to check if previous system improvements were effective.
        Also triggers a Meta-Analysis phase reading the entire kernel source code.
        """
        self._log("Iniciando análisis profundo del proyecto...", "PHASE_START")
        
        # 1. Gather Context
        workspace_context = self._gather_workspace_context(project_path)
        speckit_context = self._gather_speckit_context(project_path)
        logs_context = self._gather_logs_context(project_path)
        
        # COGNITIVE LOOPBACK: Read system improvements to see what was promised
        improvements_path = project_path.parent / ".soda_system_improvements.md"
        system_memory = ""
        if improvements_path.exists():
            system_memory = f"\n--- MEMORIA COGNITIVA (Mejoras Recientes en SODA) ---\n{improvements_path.read_text(encoding='utf-8')}\n"

        # 2. Construct Massive Analysis Prompt
        sys_p = (
            "Eres el Arquitecto Jefe de Auditoría de SODA (Deep Thinking Layer).\n"
            "Tu misión es realizar un análisis FORENSE completo del proyecto que acaba de terminar.\n\n"
            "MANDATORIO (Loopback): Revisa la 'MEMORIA COGNITIVA' proporcionada. "
            "Responde a las preguntas directas que el equipo te hace allí y valida si las mejoras aplicadas están funcionando.\n\n"
            "DEBES ANALIZAR:\n"
            "1. FUNCIONAMIENTO: ¿El código generado cumple realmente con la misión?\n"
            "2. ERRORES Y FRICCIONES: Identifica fallos de coordinación, alucinaciones o redundancias.\n"
            "3. CALIDAD TÉCNICA: Evalúa arquitectura, modularidad y legibilidad.\n"
            "4. MEJORAS: Sugiere acciones concretas para mejorar SODA basándote en este proyecto.\n\n"
            "SALIDA: Un informe Markdown técnico, crítico y honesto."
        )
        
        user_msg = (
            f"MISIÓN ORIGINAL: {mission_desc}\n\n"
            f"{system_memory}\n"
            f"--- ARTEFACTOS GENERADOS ---\n{workspace_context}\n\n"
            f"--- ESPECIFICACIONES Y PLANES (SPEC-KIT) ---\n{speckit_context}\n\n"
            f"--- LOGS DE EJECUCIÓN ---\n{logs_context}\n\n"
            "Genera el informe de Deep Thinking ahora. Sé especialmente estricto con las mejoras de relevo y persistencia."
        )
        
        try:
            # We use a very large max_tokens for the final report
            resp = await self.model.call(system_prompt=sys_p, user_message=user_msg, max_tokens=16000)
            report_content = resp.content
            
            # 3. Persist Report
            report_path = project_path / "SODA_DEEP_THINKING_REPORT.md"
            report_path.write_text(report_content, encoding="utf-8")
            
            self._log(f"Informe de Deep Thinking generado: {report_path.name}", "SUCCESS")
            
            # 4. META-ANALYSIS (Self-Reflection Loop)
            await self._generate_meta_action_plan(project_path, report_content)
            
            return report_content
            
        except Exception as e:
            err_msg = f"Error en capa de Deep Thinking: {e}"
            self._log(err_msg, "ERROR")
            return err_msg

    async def _generate_meta_action_plan(self, project_path: Path, forensic_report: str):
        """
        Deep Research: Reads the FULL SODA kernel source code and generates an Action Plan
        based on the findings of the forensic report.
        """
        self._log("Iniciando META-ANÁLISIS (Deep Research + Deep Thinking)...", "LOG")
        
        # Gather all kernel code
        kernel_path = Path(__file__).resolve().parent.parent
        kernel_code = "--- CÓDIGO FUENTE DE SODA KERNEL ---\n\n"
        
        for p in kernel_path.rglob("*.py"):
            if p.is_file() and "__pycache__" not in str(p):
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    kernel_code += f"### FILE: {p.relative_to(kernel_path)}\n```python\n{content}\n```\n\n"
                except: pass
                
        # Truncate slightly just in case it hits an extreme limit, though Gemini 3.5 Flash handles 1M+ tokens
        kernel_code = kernel_code[:500000]

        sys_p = (
            "Eres Gemini 3.5 Flash actuando como Meta-Ingeniero de SODA.\n"
            "Acabas de generar un Informe Forense detallando los fallos del sistema.\n"
            "Tu misión AHORA es leer TODO el código fuente del núcleo de SODA (Kernel) que se te proporciona.\n"
            "MANDATO DE DEEP RESEARCH:\n"
            "1. Encuentra EXACTAMENTE dónde están las fallas lógicas en el código fuente de SODA.\n"
            "2. Responde a las preguntas del 'SODA SYSTEM IMPROVEMENT TRACKER' (IMP-021, IMP-022, IMP-023).\n"
            "3. Redacta un PLAN DE ACCIÓN PASO A PASO con sugerencias de código MUY CONCRETAS para implementar en el núcleo.\n"
            "SALIDA: Un archivo Markdown 'SODA_ACTION_PLAN.md' con el diseño técnico de las soluciones."
        )
        
        user_msg = (
            f"--- INFORME FORENSE PREVIO ---\n{forensic_report}\n\n"
            f"{kernel_code}\n\n"
            "Ejecuta el Meta-Análisis profundo y genera el Plan de Acción."
        )

        try:
            resp = await self.model.call(system_prompt=sys_p, user_message=user_msg, max_tokens=16384)
            plan_path = project_path / "SODA_ACTION_PLAN.md"
            plan_path.write_text(resp.content, encoding="utf-8")
            self._log(f"Plan de Acción Meta-Evolutivo generado: {plan_path.name}", "SUCCESS")
        except Exception as e:
            self._log(f"Error en Meta-Análisis: {e}", "WARNING")

    def _gather_workspace_context(self, project_path: Path) -> str:
        context = ""
        src_dir = project_path / "source"
        if not src_dir.exists(): return "No se encontró código fuente."
        
        for p in src_dir.rglob("*"):
            if p.is_file() and p.suffix in [".py", ".html", ".js", ".css", ".json"]:
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    context += f"\nFILE: {p.relative_to(project_path)}\nCONTENT:\n{content}\n"
                except: pass
        return context[:50000] # Cap to avoid context overflow if project is huge

    def _gather_speckit_context(self, project_path: Path) -> str:
        context = ""
        files = ["spec.md", "plan.md", "tasks.md", ".specify/constitution.md"]
        for f in files:
            p = project_path / f
            if p.exists():
                context += f"\nFILE: {f}\nCONTENT:\n{p.read_text(encoding='utf-8')}\n"
        
        # Add relay notes
        memory_dir = project_path / ".specify" / "memory"
        if memory_dir.exists():
            for f in memory_dir.glob("relay_*.md"):
                context += f"\nRELAY NOTE: {f.name}\nCONTENT:\n{f.read_text(encoding='utf-8')}\n"
        return context

    def _gather_logs_context(self, project_path: Path) -> str:
        logs_dir = project_path / "logs"
        if not logs_dir.exists(): return "No se encontraron logs."
        
        log_files = sorted(list(logs_dir.glob("ai_GLOBAL_*.json")), reverse=True)[:5]
        context = ""
        for lf in log_files:
            try:
                data = json.loads(lf.read_text(encoding="utf-8"))
                # Filter for relevant events
                for event in data:
                    if event.get("event_type") in ["WARNING", "ERROR", "PHASE_START"]:
                        context += f"[{event.get('timestamp')}] {event.get('event_type')}: {event.get('msg')}\n"
            except: pass
        return context
