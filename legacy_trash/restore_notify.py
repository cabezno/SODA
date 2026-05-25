import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Restore the correct _notify method
proper_notify = """    def _notify(self, message: str, event_type: str = "LOG", data: Optional[dict] = None):
        payload = {"event_type": event_type, "message": message, "data": data or {}}
        print(f"[{event_type}] {message}") # Console mirror

        # Broadcast to WebSocket clients
        try:
            import asyncio as _asyncio
            loop = _asyncio.get_running_loop()
            from ui.websocket_handler import manager as _ws_manager
            loop.create_task(_ws_manager.broadcast(payload))
            
            # Send crucial events to Telegram
            if event_type in ("START", "DONE", "PIPELINE_ERROR", "FAILED"):
                if hasattr(self, "telegram"):
                    loop.create_task(self.telegram.send_from_loop(f"SODA [{event_type}]: {message}"))
        except Exception:
            pass

        # Also call self.notify_fn if provided
        if hasattr(self, "notify_fn") and self.notify_fn:
            try:
                import asyncio
                asyncio.create_task(self.notify_fn(payload))
            except Exception:
                pass"""

# Replace the broken _notify
content = re.sub(
    r'    def _notify\(self, message: str, event_type: str = "LOG", data: Optional\[dict\] = None\):\n\s*payload = \{"event_type": event_type, "message": message, "data": data or \{\}\}\n\s*if self\.notify_fn:\n\s*asyncio\.create_task\(self\.notify_fn\(payload\)\)\n\s*else:\n\s*print\(f"\[\{event_type\}\] \{message\}"\)',
    proper_notify,
    content,
    flags=re.DOTALL
)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
