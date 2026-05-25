from pathlib import Path
path = Path("kernel/communication/telegram_gateway.py")
content = path.read_text(encoding="utf-8")

old_send = """    async def _send_voice_bytes(self, ogg_bytes: bytes) -> None:
        \"\"\"Upload OGG Opus bytes as a Telegram voice message (sendVoice).\"\"\"
        import httpx
        import io
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.post(
                    f"https://api.telegram.org/bot{self._token}/sendVoice",
                    data={"chat_id": self._chat_id},
                    files={"voice": ("voice.ogg", io.BytesIO(ogg_bytes), "audio/ogg")},
                )
        except Exception as e:
            print(f"  [Telegram] _send_voice_bytes failed: {e}")"""

new_send = """    async def _send_voice_bytes(self, ogg_bytes: bytes) -> None:
        \"\"\"Upload OGG Opus bytes as a Telegram voice message using native bot API.\"\"\"
        import io
        import asyncio
        from telegram.error import TimedOut, NetworkError
        
        for attempt in range(3):
            try:
                # Usar la conexion nativa del bot evita los timeouts SSL de httpx
                await self._app.bot.send_voice(
                    chat_id=self._chat_id,
                    voice=io.BytesIO(ogg_bytes),
                    read_timeout=45,
                    write_timeout=45,
                    connect_timeout=15
                )
                return # Success
            except (TimedOut, NetworkError) as e:
                print(f"  [Telegram] sendVoice timeout (attempt {attempt+1}): {e}")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"  [Telegram] sendVoice error: {e}")
                return
        print("  [Telegram] Fallo critico enviando nota de voz despues de 3 intentos.")"""

if old_send in content:
    content = content.replace(old_send, new_send)
    path.write_text(content, encoding="utf-8")
    print("Metodo de envio de Telegram corregido al nativo.")
else:
    print("No se encontro el bloque old_send en telegram_gateway.py")
