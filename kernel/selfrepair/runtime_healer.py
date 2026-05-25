"""Runtime Healer Forense Filtrado por Nodo."""
import sys
import traceback
import importlib
import asyncio
import json
import re
from pathlib import Path
from typing import Callable, Any, Optional

class RuntimeHealer:
    def __init__(self, gemini_driver, notify_fn: Callable, workspace: Optional[Path] = None):
        self.gemini = gemini_driver
        self._notify = notify_fn
        self.workspace = workspace
        self.base_dir = Path(__file__).resolve().parent.parent.parent

    def _get_blackbox_evidence(self, phase_name: str) -> str:
        """Extrae evidencia filtrada por la fase y nodo actuales para evitar saturación."""
        if not self.workspace: return ""
        log_dir = self.workspace / "logs"
        if not log_dir.exists(): return ""

        evidence = "### EVIDENCIA FORENSE FILTRADA (BlackBox):\n"
        
        # 1. Filtrar eventos del sistema que coincidan con la fase
        trace_file = log_dir / "system_trace.log"
        if trace_file.exists():
            try:
                all_lines = trace_file.read_text(encoding="utf-8").splitlines()
                # Buscamos líneas que contengan la fase actual en su etiqueta de contexto
                # El formato es: timestamp | LEVEL | [phase][node] | message
                relevant = [l for l in all_lines if f"[{phase_name}]" in l]
                evidence += f"--- Eventos de la fase '{phase_name}' (Últimos 15) ---\n"
                evidence += "\n".join(relevant[-15:]) + "\n\n"
            except Exception: pass

        # 2. Buscar la última comunicación IA que coincida con la fase
        ai_logs = sorted(log_dir.glob("ai_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        for log_path in ai_logs:
            try:
                data = json.loads(log_path.read_text(encoding="utf-8"))
                if data.get("phase") == phase_name:
                    evidence += f"--- Detalle de comunicación IA (Nodo: {data.get('node')}) ---\n"
                    evidence += f"MODELO: {data.get('model')}\n"
                    # Resumen inteligente: si es un error de esquema, mostramos la respuesta completa
                    raw_res = str(data.get('raw_response'))
                    evidence += f"RESPUESTA IA: {raw_res[:3000]} (truncado si excede)\n\n"
                    break # Solo la más reciente de esta fase
            except Exception: continue
            
        return evidence

    async def handle_exception(self, e: Exception, phase_name: str = "General") -> bool:
        if isinstance(e, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)): return False
        self._notify("HEALING_START", f"🔧 [Healer] Reparando fase '{phase_name}' con evidencia filtrada...")
        
        tb_text = "".join(traceback.format_exception(*sys.exc_info()))
        soda_files = set()
        for tb_line in tb_text.splitlines():
            m = re.search(r'File "(.+?(?:kernel|ui)[\\/].+?\.py)"', tb_line)
            if m:
                f = m.group(1)
                if "venv" not in f: soda_files.add(f)
        if not soda_files: return False

        files_content = {f: Path(f).read_text(encoding="utf-8") for f in soda_files if Path(f).exists()}
        evidence = self._get_blackbox_evidence(phase_name)

        ai_response = await self._ask_ai_for_patch(tb_text, files_content, phase_name, evidence)
        patched_files = ai_response.get("files", {})
        if not patched_files: return False

        for fpath, new_content in patched_files.items():
            Path(fpath).write_text(new_content, encoding="utf-8")
            mod_name = "kernel." + Path(fpath).as_posix().split("kernel/")[1].replace(".py", "").replace("/", ".")
            if mod_name in sys.modules: importlib.reload(sys.modules[mod_name])
                    
        return True

    async def _ask_ai_for_patch(self, tb: str, files: dict, phase: str, evidence: str) -> dict:
        msg = f"## FASE: {phase}\n{evidence}\n## TRACEBACK:\n{tb}\n## CÓDIGO:\n"
        for p, c in files.items(): msg += f"### {p}\n{c}\n"
        try:
            resp = await self.gemini.call(system_prompt="Forensic Healer. JSON output only.", user_message=msg, model="gemini-3.1-pro-preview")
            return json.loads(re.search(r'\{.*\}', resp.content, re.DOTALL).group(0))
        except Exception: return {}
