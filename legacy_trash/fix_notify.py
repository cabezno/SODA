import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

proper_notify = """    def _notify(self, message: str, event_type: str = "LOG", data: Optional[dict] = None) -> None:
        payload = {"event_type": event_type, "message": message, "data": data or {}}
        print(f"[{event_type}] {message}") # Console mirror

        # Broadcast to WebSocket clients
        try:
            import asyncio as _asyncio
            loop = _asyncio.get_running_loop()
            from ui.websocket_handler import manager as _ws_manager
            loop.create_task(_ws_manager.broadcast(payload))
        except RuntimeError:
            # Not inside an async context — send via HTTP in a background thread
            import threading
            def _post():
                try:
                    import requests
                    requests.post(self._ui_url, json=payload, timeout=2.0)
                except Exception:
                    pass
            threading.Thread(target=_post, daemon=True).start()
        except Exception:
            pass

        # Forward key events to Telegram
        if hasattr(self, "telegram") and self.telegram.should_forward(event_type) and self.telegram.is_configured():
            import asyncio as _asyncio
            formatted = self.telegram.format_event(event_type, message, data)
            try:
                loop = _asyncio.get_running_loop()
                loop.create_task(self.telegram.send_event(event_type, formatted, data))
            except RuntimeError:
                import threading
                def _tg_send():
                    try:
                        _asyncio.run(self.telegram.send_event(event_type, formatted, data))
                    except Exception:
                        pass
                threading.Thread(target=_tg_send, daemon=True).start()
            except Exception:
                pass

        # Also call self.notify_fn if provided
        if hasattr(self, "notify_fn") and self.notify_fn:
            try:
                import asyncio
                asyncio.create_task(self.notify_fn(payload))
            except Exception:
                pass
"""

content = re.sub(
    r'    def _notify\(self, message: str, event_type: str = "LOG", data: Optional\[dict\] = None\):.*?(?=    async def _ask_user_clarification)',
    proper_notify + "\n",
    content,
    flags=re.DOTALL
)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
