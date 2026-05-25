import re
from pathlib import Path

f = Path("kernel/orchestrator.py")
content = f.read_text(encoding="utf-8")

# 1. Corregir _notify para asegurar que los scripts hablen con la UI
old_notify = """        # Broadcast to WebSocket clients
        try:
            import asyncio as _asyncio
            loop = _asyncio.get_running_loop()
            from ui.websocket_handler import manager as _ws_manager
            loop.create_task(_ws_manager.broadcast(payload))
        except RuntimeError:"""

new_notify = """        # Broadcast to WebSocket clients (Bridge Check)
        is_ui_process = False
        try:
            import asyncio as _asyncio
            loop = _asyncio.get_running_loop()
            from ui.websocket_handler import manager as _ws_manager
            # Solo si hay clientes conectados, asumimos que somos el proceso UI
            if len(_ws_manager.active_connections) > 0:
                loop.create_task(_ws_manager.broadcast(payload))
                is_ui_process = True
        except (RuntimeError, ImportError):
            pass

        # Si no somos el proceso UI o el websocket falló, usamos el puente HTTP
        if not is_ui_process:
            import threading
            def _post():
                try:
                    import requests
                    requests.post(self._ui_url, json=payload, timeout=1.0)
                except Exception: pass
            threading.Thread(target=_post, daemon=True).start()

        try:
            pass # Placeholder para mantener estructura
        except Exception:"""

if old_notify in content:
    content = content.replace(old_notify, new_notify)

# 2. Inyectar auditoría de errores pasados en resume()
resume_audit_target = 'self._notify(f"Reanudando proyecto {project_id}...", "START", {"project_id": project.id})'
resume_audit_replacement = """self._notify(f"Reanudando proyecto {project_id}...", "START", {"project_id": project.id})
        
        # Auditoría de fallos previos (Sugerencia del usuario)
        log_file = project.workspace / "logs" / "event_history.jsonl"
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8") as lf:
                    lines = lf.readlines()
                    last_errors = [json.loads(l) for l in lines if '"type": "ERROR"' in l or '"type": "STEP_ERROR"' in l]
                    if last_errors:
                        last_err = last_errors[-1]
                        self._notify(f"AtenciÃ³n: Detectado fallo previo en este proyecto ({last_err.get('message')}). El Healer estarÃ¡ en alerta mÃ¡xima.", "WARNING")
            except Exception: pass"""

if resume_audit_target in content:
    content = content.replace(resume_audit_target, resume_audit_replacement)

f.write_text(content, encoding="utf-8")
print("Orchestrator: Puente de UI y Auditoría de reanudación activados.")
