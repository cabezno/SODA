import json
import os
import re
from pathlib import Path
from datetime import datetime

class TreeExporter:
    """
    Genera el archivo 'arbol.txt' que contiene el mapeo narrativo e hiperdetallado
    de todo el proceso de SODA, incluyendo ventana de contexto y prompts exactos.
    """
    
    @staticmethod
    def generate(workspace: Path):
        log_dir = workspace / "logs"
        events_file = log_dir / "event_history.jsonl"
        meta_file = workspace / "metadata.json"
        tree_file_path = workspace / "arbol.txt"
        
        if not events_file.exists():
            return
            
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {"description": "No description found."}
            
        lines = []
        lines.append("=========================================================================")
        lines.append("                SODA - ÁRBOL DE PROCESOS Y TRAZABILIDAD (V2.1)           ")
        lines.append("=========================================================================\n")
        lines.append(f"Fecha de Generación: {datetime.now().isoformat()}")
        lines.append(f"Proyecto ID: {workspace.name}")
        lines.append(f"Estado de la Ventana: VERIFICACIÓN DE CONTEXTO MÍNIMO AISLADO (CMA) ACTIVA")
        
        lines.append("\n[ SOLICITUD INICIAL DEL USUARIO ]")
        lines.append("-------------------------------------------------------------------------")
        lines.append(meta.get("description", ""))
        lines.append("-------------------------------------------------------------------------\n")
        
        # Leer todos los eventos
        events = []
        with open(events_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        events.append(json.loads(line))
                    except Exception: pass
                    
        # Leer todas las comunicaciones IA
        ai_comms = []
        for file in log_dir.glob("ai_*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    ai_comms.append(json.load(f))
            except Exception: pass
            
        ai_comms.sort(key=lambda x: x.get("timestamp", ""))
        
        current_phase = ""
        current_node = ""
        
        for ev in events:
            phase = ev.get("phase", "")
            node = ev.get("node", "")
            evt_type = ev.get("type", "")
            msg = ev.get("message", "")
            
            if phase != current_phase:
                current_phase = phase
                lines.append(f"\n█████████████████████████████████████████████████████████████████████████")
                lines.append(f"█ FASE: {current_phase.upper()}")
                lines.append(f"█████████████████████████████████████████████████████████████████████████\n")
                
            if node != current_node and node != "GLOBAL":
                current_node = node
                lines.append(f"\n  [ NODO / MÓDULO: {current_node} ]")
                lines.append(f"  =========================================")
            
            # --- ENTREVISTA ---
            if evt_type == "USER_QUESTION":
                lines.append(f"\n  [?] PREGUNTA DE SODA:")
                lines.append(f"      {msg}")
                ans = ev.get("data", {}).get("answer", "")
                if ans:
                    lines.append(f"  [>] RESPUESTA DEL USUARIO: {ans}")
            
            # --- LOGS Y ÉXITOS ---
            elif evt_type in ["LOG", "SUCCESS", "PHASE_START"]:
                lines.append(f"  -> {msg}")
                
            # --- ERRORES Y SANACIÓN ---
            elif evt_type in ["ERROR", "WARNING", "PROVIDER_FAILOVER"]:
                lines.append(f"\n  [!] ALERTA: {msg}")
                if ev.get("data"):
                    lines.append(f"      Contexto Técnico: {json.dumps(ev.get('data'), ensure_ascii=False)}")
                lines.append(f"      (Iniciando protocolo de recuperación automatizada...)\n")
                
            # --- DETALLE DE IA (PROMPTS Y CONTEXTO) ---
            # Buscamos si este evento disparó una llamada de IA
            ev_time = ev.get("timestamp", "")
            # Heurística: Si el mensaje indica que una IA está trabajando o si es una fase de generación/arquitectura
            if any(kw in msg.lower() for kw in ["escribiendo", "analizando", "auditando", "re-evaluando", "generando"]):
                related_comm = next((c for c in ai_comms if c.get("node") == node and c.get("timestamp") >= ev_time), None)
                
                if related_comm:
                    model = related_comm.get("model", "unknown")
                    ctx_status = related_comm.get("context_window_status", "UNKNOWN")
                    tokens_in = related_comm.get("metadata", {}).get("tokens_input", 0)
                    tokens_out = related_comm.get("metadata", {}).get("tokens_output", 0)
                    prompt = related_comm.get("prompt_sent", "")
                    response = related_comm.get("raw_response", "")
                    
                    lines.append(f"\n      ╔════ INTERVENCIÓN TÉCNICA DE IA ══════════════════════════════════")
                    lines.append(f"      ║ IA: {model} ({related_comm.get('provider')})")
                    lines.append(f"      ║ Estado de Ventana: {ctx_status}")
                    lines.append(f"      ║ Consumo Inicial (Contexto): {tokens_in} tokens")
                    lines.append(f"      ║ Consumo Final (Generado): {tokens_out} tokens")
                    lines.append(f"      ║")
                    lines.append(f"      ║ PROMPT ENVIADO:")
                    lines.append(f"      ║ \"{prompt[:1000]}...\"" if len(prompt) > 1000 else f"      ║ {prompt}")
                    lines.append(f"      ║")
                    lines.append(f"      ║ RESPUESTA RECIBIDA:")
                    # Limpiamos markdown para el reporte
                    clean_res = re.sub(r'```.*?```', '[BLOQUE DE CÓDIGO]', response, flags=re.DOTALL)
                    lines.append(f"      ║ \"{clean_res[:1000]}...\"" if len(clean_res) > 1000 else f"      ║ {clean_res}")
                    lines.append(f"      ╚══════════════════════════════════════════════════════════════════\n")
                    
                    ai_comms.remove(related_comm)

        # --- CIERRE ---
        src_dir = workspace / "source"
        if src_dir.exists():
            lines.append("\n\n=========================================================================")
            lines.append("                INVENTARIO DE DESARROLLO FINAL                           ")
            lines.append("=========================================================================\n")
            for f in src_dir.glob("*.*"):
                lines.append(f"  [ARCHIVO] {f.name} ({f.stat().st_size} bytes)")
        
        lines.append("\n================================ FIN DEL REPORTE ================================\n")
        
        with open(tree_file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"[INFO] arbol.txt actualizado con auditoría de contexto.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        TreeExporter.generate(Path(sys.argv[1]))
