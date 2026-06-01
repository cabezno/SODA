import asyncio
import collections
import json
import os
import queue
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from kernel.communication.messaging_gateway import MessagingGateway
from kernel.communication.user_interaction import get_gateway
from kernel.drivers.gemini_driver import GeminiDriver
from kernel.external.system_actions import SystemActionsExecutor
from kernel.projects.project_manager import ProjectManager


PAIRING_CODES: dict[str, str] = {}   # code → "pending"
_PENDING_VOICE_SAMPLE: set[str] = set()  # chat_ids waiting for a voice reference audio

_IA_TIMEOUT_SECS = 300  # 5 minutes inactivity before asking
_ia_sessions: dict[str, dict] = {}
# chat_id → {"active": bool, "task": asyncio.Task|None, "waiting_close": bool}

# Global driver instance to avoid re-probing on every message (Error 10)
_gemini_chat_driver: Optional[GeminiDriver] = None

def _get_gemini_driver() -> GeminiDriver:
    global _gemini_chat_driver
    if _gemini_chat_driver is None:
        _gemini_chat_driver = GeminiDriver()
    return _gemini_chat_driver


def _split_message(text: str, limit: int = 4096) -> list[str]:
    """Split long text into Telegram-safe chunks without cutting words."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], []
    for line in text.splitlines(keepends=True):
        if sum(len(l) for l in current) + len(line) > limit:
            chunks.append("".join(current))
            current = []
        current.append(line)
    if current:
        chunks.append("".join(current))
    return chunks or [text[:limit]]

# ---------------------------------------------------------------------------
# Global rate-limited send queue (one worker thread, ~20 msg/s, 429 retry)
# ---------------------------------------------------------------------------
_send_queue: queue.Queue = queue.Queue()
_send_worker_started = False
_send_worker_lock = threading.Lock()


def _ensure_send_worker(token: str) -> None:
    """Start the background send-worker once per process."""
    global _send_worker_started
    with _send_worker_lock:
        if _send_worker_started:
            return
        _send_worker_started = True

    def _worker():
        import httpx
        with httpx.Client(timeout=12) as client:
            while True:
                try:
                    chat_id, text = _send_queue.get(timeout=5)
                except queue.Empty:
                    continue
                for attempt in range(4):
                    try:
                        r = client.post(
                            f"https://api.telegram.org/bot{token}/sendMessage",
                            json={"chat_id": chat_id, "text": text[:4096]},
                        )
                        if r.status_code == 429:
                            retry_after = r.json().get("parameters", {}).get("retry_after", 2)
                            time.sleep(float(retry_after))
                            continue
                        break
                    except Exception as e:
                        print(f"  [Telegram] send failed (attempt {attempt+1}): {e}")
                        time.sleep(1.0)
                _send_queue.task_done()
                time.sleep(0.05)  # ~20 msg/s ceiling

    threading.Thread(target=_worker, daemon=True, name="tg-send-worker").start()
SODA_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "soda_config.json"
_PENDING_CREATION: dict[str, dict] = {}  # chat_id → {"step": str, "name": str, "_ts": float}
_PENDING_TTL_SECS = 600  # 10 minutes — stale creation sessions are discarded


def _evict_stale_pending() -> None:
    """Remove _PENDING_CREATION entries older than TTL."""
    now = time.monotonic()
    stale = [cid for cid, v in _PENDING_CREATION.items() if now - v.get("_ts", 0) > _PENDING_TTL_SECS]
    for cid in stale:
        _PENDING_CREATION.pop(cid, None)
_NAME_RE = re.compile(r'^[a-zA-Z0-9_\-]{1,60}$')
_SERVER_URL = "http://127.0.0.1:8000"
_OPEN_TARGET_ALIASES = {
    "proyecto": "open_project",
    "project": "open_project",
    "source": "open_source",
    "codigo": "open_source",
    "archivo": "open_file",
    "file": "open_file",
}


def _sanitize_name(text: str) -> str:
    """Strip invisible/Unicode chars, replace spaces with underscores, keep only valid chars."""
    import unicodedata
    # Remove control/invisible characters
    cleaned = ''.join(c for c in text if unicodedata.category(c)[0] != 'C')
    # Collapse spaces → underscore
    cleaned = re.sub(r'\s+', '_', cleaned.strip())
    # Keep only valid characters
    cleaned = re.sub(r'[^a-zA-Z0-9_\-]', '', cleaned)
    return cleaned[:60]


def _load_config() -> dict:
    if SODA_CONFIG_PATH.exists():
        try:
            return json.loads(SODA_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_config(config: dict):
    SODA_CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


class TelegramGateway(MessagingGateway):
    _HISTORY_MAXLEN = 20  # turns kept per chat (each turn = user + assistant)

    def __init__(self):
        self._token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        config = _load_config()
        self._chat_id: Optional[str] = config.get("telegram_chat_id")
        # Bot instance only used for pairing; send() uses send_from_loop() via httpx
        try:
            self._bot: Optional[Bot] = Bot(self._token) if self._token else None
        except Exception:
            self._bot = None
        self._app: Optional[Application] = None
        # Per-chat conversation history: deque of {"role": ..., "content": ...}
        self._history: dict[str, collections.deque] = collections.defaultdict(
            lambda: collections.deque(maxlen=self._HISTORY_MAXLEN * 2)
        )
        # Deduplicación de preguntas: evita reenviar la misma pregunta activa
        self._last_question_sent: Optional[str] = None

    def is_configured(self) -> bool:
        return bool(self._token and self._chat_id)

    async def send(self, message: str, data: Optional[dict] = None) -> bool:
        # SODA FUSION: Always attempt to speak if configured
        await self.send_from_loop(message)
        if self.is_configured():
             await self._tts_speak(message)
        return True

    async def send_from_loop(self, text: str) -> bool:
        """Enqueue for rate-limited delivery — safe from any event loop context."""
        if not self.is_configured():
            return False
        _ensure_send_worker(self._token)
        # Clean markdown for plain text messages to avoid raw asterisks in some clients
        clean_text = text.replace("**", "").replace("__", "")
        _send_queue.put((self._chat_id, clean_text))
        return True

    async def send_event(self, event_type: str, text: str, data: Optional[dict] = None) -> bool:
        """Send event notification. DONE events include an inline ▶ Ejecutar button.
        Important events now ALWAYS trigger TTS by default in FUSION."""
        if not self.is_configured():
            return False
        
        project_id = (data or {}).get("project_id", "")
        
        if event_type == "DONE" and project_id:
            await self._send_with_play_button(text, project_id)
            await self._tts_speak(f"Misión completada. {text}")
            return True
            
        if event_type == "USER_QUESTION":
            if text == self._last_question_sent:
                return True
            self._last_question_sent = text
            return await self._send_voice_question(text, data)
            
        if event_type in ("PHASE_START", "SUCCESS", "HEALTH_WARN", "ERROR"):
            await self.send_from_loop(text)
            await self._tts_speak(text)
            return True

        self._last_question_sent = None
        return await self.send_from_loop(text)

    async def _send_voice_question(self, text: str, data: Optional[dict] = None) -> bool:
        """Send text + voice note for a USER_QUESTION event."""
        await self.send_from_loop(text)  # always send text first
        try:
            from kernel.tts.kokoro_tts import KokoroTTS, wav_to_ogg_opus, tts_telegram_enabled, is_available, has_voice
            if not tts_telegram_enabled() or not is_available():
                return True
            if not has_voice():
                await self._request_voice_sample()
                return True
            speak_text = (data or {}).get("question") or text
            tts = KokoroTTS.get()
            wav = await tts.generate_wav(speak_text)
            if not wav:
                return True
            ogg = wav_to_ogg_opus(wav)
            await self._send_voice_bytes(ogg)
        except Exception as e:
            print(f"  [Telegram] TTS voice send failed: {e}")
        return True

    async def _tts_speak(self, text: str) -> None:
        """Generate and send a TTS voice note (fire-and-forget helper)."""
        try:
            from kernel.tts.kokoro_tts import KokoroTTS, wav_to_ogg_opus, tts_telegram_enabled, is_available, has_voice
            if not tts_telegram_enabled() or not is_available():
                return
            if not has_voice():
                await self._request_voice_sample()
                return
            wav = await KokoroTTS.get().generate_wav(text)
            if wav:
                await self._send_voice_bytes(wav_to_ogg_opus(wav))
        except Exception as e:
            print(f"  [Telegram] _tts_speak failed: {e}")

    async def _request_voice_sample(self) -> None:
        """Con Edge TTS no se necesita muestra de voz — no-op."""
        pass

    async def _register_voice_sample(self, update: Update, media) -> None:
        """Con Edge TTS no se necesita muestra de voz — informar al usuario."""
        chat_id = str(update.effective_chat.id)
        _PENDING_VOICE_SAMPLE.discard(chat_id)
        await update.message.reply_text(
            "SODA usa Edge TTS (voz neural argentina). "
            "No necesita muestra de voz — ya habla directamente.\n"
            "Podés cambiar la voz con /voz."
        )

    async def _send_voice_bytes(self, ogg_bytes: bytes) -> None:
        """Upload OGG Opus bytes as a Telegram voice message (sendVoice)."""
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
            print(f"  [Telegram] sendVoice failed: {e}")

    async def _send_with_play_button(self, text: str, project_id: str) -> bool:
        """Send a message with an inline keyboard ▶ Ejecutar + 🔧 Auto-Fix buttons."""
        import httpx
        keyboard = {
            "inline_keyboard": [[
                {"text": "▶ Ejecutar", "callback_data": f"play:{project_id}"},
                {"text": "🔧 Auto-Fix", "callback_data": f"autofix:{project_id}"},
            ]]
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{self._token}/sendMessage",
                    json={
                        "chat_id": self._chat_id,
                        "text": text[:4096],
                        "reply_markup": keyboard,
                    },
                )
            return True
        except Exception as e:
            print(f"  [Telegram] send_with_play_button failed: {e}")
            # Fallback to plain message
            return await self.send_from_loop(text)

    # --- Pairing ---

    def generate_pairing_code(self) -> str:
        code = secrets.token_hex(3).upper()   # e.g. "A3F9B2"
        PAIRING_CODES[code] = "pending"
        return code

    def _confirm_pairing(self, code: str, chat_id: str) -> bool:
        if code in PAIRING_CODES:
            self._chat_id = chat_id
            config = _load_config()
            config["telegram_chat_id"] = chat_id
            _save_config(config)
            del PAIRING_CODES[code]
            return True
        return False

    # --- Bot runner ---

    def start_bot(self):
        """Launch the bot and the send-worker in background threads."""
        if not self._token:
            print("  [Telegram] No TELEGRAM_BOT_TOKEN — bot not started.")
            return
        _ensure_send_worker(self._token)
        threading.Thread(target=self._run_bot_sync, daemon=True, name="tg-bot").start()

    def _run_bot_sync(self):
        asyncio.run(self._run_bot())

    async def _run_bot(self):
        self._app = Application.builder().token(self._token).build()
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("pair", self._cmd_pair))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(CommandHandler("projects", self._cmd_projects))
        self._app.add_handler(CommandHandler("crear", self._cmd_crear))
        self._app.add_handler(CommandHandler("abrir", self._cmd_abrir))
        self._app.add_handler(CommandHandler("aprobar", self._cmd_aprobar))
        self._app.add_handler(CommandHandler("rechazar", self._cmd_rechazar))
        self._app.add_handler(CommandHandler("cancel", self._cmd_cancel))
        self._app.add_handler(CommandHandler("fin", self._cmd_fin))
        self._app.add_handler(CommandHandler("terminar", self._cmd_fin))
        self._app.add_handler(CommandHandler("limpiar", self._cmd_limpiar))
        self._app.add_handler(CommandHandler("mas_tiempo", self._cmd_mas_tiempo))
        self._app.add_handler(CommandHandler("voz", self._cmd_voz))
        self._app.add_handler(CommandHandler("ia", self._cmd_ia))
        self._app.add_handler(CommandHandler("reparar", self._cmd_reparar))
        self._app.add_handler(CommandHandler("addskill", self._cmd_addskill))
        self._app.add_handler(CallbackQueryHandler(self._handle_callback))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))
        self._app.add_handler(MessageHandler(filters.VOICE, self._handle_voice))
        self._app.add_handler(MessageHandler(filters.AUDIO, self._handle_audio))
        async with self._app:
            await self._app.start()
            await self._app.updater.start_polling(drop_pending_updates=False)
            # Use a short sleep loop instead of blocking forever — allows clean shutdown
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass

    async def _handle_callback(self, update: Update, ctx: ContextTypes):
        """Handle inline keyboard button presses (▶ Ejecutar / 🔧 Auto-Fix)."""
        query = update.callback_query
        await query.answer()
        chat_id = str(query.from_user.id) if query.from_user else ""
        if chat_id != self._chat_id:
            return

        data = query.data or ""
        if ":" not in data:
            return
        action, project_id = data.split(":", 1)

        if action == "play":
            await self._callback_play(query, project_id)
        elif action == "autofix":
            await self._callback_autofix(query, project_id)

    async def _callback_play(self, query, project_id: str) -> None:
        """▶ Ejecutar — call /api/launch for the given project."""
        import httpx
        if not project_id or project_id in ("undefined", "null", "None"):
            await query.message.reply_text("Error: ID de proyecto inválido. Regenerá el proyecto.")
            return
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"Ejecutando proyecto '{project_id}'...")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"{_SERVER_URL}/api/launch",
                    json={"project_id": project_id},
                )
            data = r.json()
            if data.get("status") == "launched":
                url = data.get("url", "")
                pid = data.get("pid", "?")
                msg = f"Proyecto lanzado (PID {pid})"
                if url:
                    msg += f"\nURL: {url}"
                await query.message.reply_text(msg)
            else:
                err = (
                    data.get("message") or data.get("error")
                    or (str(data)[:200] if data else None)
                    or r.text[:200]
                    or "error desconocido"
                )
                await query.message.reply_text(f"No se pudo ejecutar: {err}")
        except Exception as e:
            await query.message.reply_text(f"Error al conectar con SODA: {e}")

    async def _callback_autofix(self, query, project_id: str) -> None:
        """🔧 Auto-Fix — trigger auto-fix execution for the given project."""
        import httpx
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"Iniciando Auto-Fix para '{project_id}'...\n"
            "Intentará 3 estrategias de ejecución y si fallan, llamará a Gemini CLI."
        )
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"{_SERVER_URL}/api/autofix",
                    json={"project_id": project_id},
                )
            data = r.json()
            if data.get("status") in ("started", "ok"):
                await query.message.reply_text(
                    f"Auto-Fix iniciado. Te avisaré cuando termine."
                )
            else:
                await query.message.reply_text(
                    f"Error al iniciar Auto-Fix: {data.get('message', r.text[:200])}"
                )
        except Exception as e:
            await query.message.reply_text(f"Error al conectar con SODA: {e}")

    async def _cmd_start(self, update: Update, ctx: ContextTypes):
        await update.message.reply_text(
            "BlackMagicBox SODA\n"
            "Sistema de orquestacion y generacion de software.\n\n"
            "COMO CREAR UN PROYECTO:\n"
            "1. Envia /crear nombre_del_proyecto\n"
            "2. Describe que debe hacer la aplicacion (en detalle)\n"
            "3. SODA genera el codigo completo automaticamente\n"
            "4. Recibis notificaciones de cada etapa aqui\n\n"
            "DURANTE EL PIPELINE:\n"
            "- Responde directamente cuando SODA te haga una pregunta\n"
            "- /aprobar — confirmar un checkpoint\n"
            "- /rechazar — rechazar y ajustar\n"
            "- /mas_tiempo — pedir mas tiempo para responder\n\n"
            "COMANDOS DISPONIBLES:\n"
            "  /crear <nombre>           — nuevo proyecto\n"
            "  /status                   — estado del pipeline\n"
            "  /projects                 — ultimos proyectos\n"
            "  /abrir proyecto <id>      — abrir carpeta del proyecto\n"
            "  /abrir source <id>        — abrir carpeta de codigo\n"
            "  /abrir archivo <id> <ruta>— abrir un archivo\n"
            "  /aprobar                  — aprobar checkpoint/pregunta\n"
            "  /rechazar                 — rechazar checkpoint/pregunta\n"
            "  /cancel                   — cancelar operacion en curso\n"
            "  /mas_tiempo               — extender 15 min el timeout\n"
            "  /voz                      — registrar muestra de voz para TTS\n"
            "  /addskill <url> [lang]    — importar skill desde skills.sh\n"
            "  /ia                       — abrir sesion interactiva con Qwen\n"
            "  /reparar [etapa] [--aplicar] — autoreparacion del sistema\n"
            "  /pair <CODE>              — vincular este chat\n\n"
            "Tambien podes escribirme libremente para consultar sobre "
            "tus proyectos o sobre como usar SODA."
        )

    async def _cmd_pair(self, update: Update, ctx: ContextTypes):
        args = ctx.args
        if not args:
            await update.message.reply_text("Usage: /pair <CODE>")
            return
        code = args[0].upper()
        chat_id = str(update.effective_chat.id)
        if self._confirm_pairing(code, chat_id):
            await update.message.reply_text("Paired successfully. SODA notifications will arrive here.")
        else:
            await update.message.reply_text("Invalid or expired code.")

    async def _cmd_status(self, update: Update, ctx: ContextTypes):
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            return
        from ui.server import _pipeline_running
        lines = ["SODA Status"]
        lines.append("Pipeline en ejecución..." if _pipeline_running else "Idle — listo para un nuevo proyecto.")

        # Enrich with contract-level status if an active project exists
        try:
            import httpx
            r = httpx.get(f"{_SERVER_URL}/api/projects", timeout=2)
            if r.status_code == 200:
                projects = r.json().get("projects", [])
                if projects:
                    latest = projects[0]
                    pid = latest.get("id", "")
                    r2 = httpx.get(f"{_SERVER_URL}/api/project/{pid}/status", timeout=2)
                    if r2.status_code == 200:
                        s = r2.json()
                        lines.append(f"\nProyecto: {pid}")
                        lines.append(f"Estado: {s.get('state', '?')}")
                        lines.append(f"Descripción: {s.get('description', '')[:80]}")
                        contracts = s.get("contracts", {})
                        if contracts:
                            lines.append("Contratos: " + ", ".join(f"{k}={v}" for k, v in contracts.items()))
                        lines.append(f"Archivos generados: {len(s.get('source_files', []))}")
                        pending = s.get("pending_count", 0)
                        if pending:
                            lines.append(f"Pendientes: {pending}")
        except Exception:
            pass

        await update.message.reply_text("\n".join(lines))

    async def _cmd_mas_tiempo(self, update: Update, ctx: ContextTypes):
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            return
        from kernel.communication.user_interaction import get_gateway
        gw = get_gateway()
        if gw.extend():
            await update.message.reply_text("Timeout extendido 15 minutos más. Tomá tu tiempo.")
        else:
            await update.message.reply_text("No hay ninguna pregunta esperando respuesta.")

    async def _cmd_cancel(self, update: Update, ctx: ContextTypes):
        chat_id = str(update.effective_chat.id)
        if chat_id in _PENDING_CREATION:
            del _PENDING_CREATION[chat_id]
            await update.message.reply_text("Operación cancelada.")
        else:
            await update.message.reply_text("No hay ninguna operación pendiente.")

    async def _cmd_fin(self, update: Update, ctx: ContextTypes):
        """Termina explícitamente la sesión/pregunta activa del pipeline."""
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            return
        # Cancel any pending project creation
        cancelled_creation = chat_id in _PENDING_CREATION
        if cancelled_creation:
            del _PENDING_CREATION[chat_id]
        # Resolve any waiting pipeline question
        gw = get_gateway()
        if gw.is_waiting:
            gw.answer("")
            await update.message.reply_text(
                "Sesión terminada. El pipeline continuará sin respuesta."
            )
        elif cancelled_creation:
            await update.message.reply_text("Creación de proyecto cancelada.")
        else:
            await update.message.reply_text("No hay ninguna sesión activa en este momento.")

    async def _cmd_crear(self, update: Update, ctx: ContextTypes):
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            await update.message.reply_text("No autorizado. Vinculá primero con /pair.")
            return

        from ui.server import _pipeline_running
        if _pipeline_running:
            await update.message.reply_text("El pipeline ya está en ejecución. Esperá a que termine.")
            return

        _evict_stale_pending()

        # If a name was given inline, try to use it; otherwise ask for it.
        if ctx.args:
            name = _sanitize_name(" ".join(ctx.args))
            if _NAME_RE.match(name):
                _PENDING_CREATION[chat_id] = {"step": "awaiting_description", "name": name, "_ts": time.monotonic()}
                await update.message.reply_text(
                    f"Proyecto: {name}\n\nDescribí qué debe hacer la aplicación:"
                )
                return

        # Ask for name interactively
        _PENDING_CREATION[chat_id] = {"step": "awaiting_name", "_ts": time.monotonic()}
        await update.message.reply_text(
            "¿Cómo se llama el proyecto?\n"
            "(solo letras, números, _ y -, sin espacios ni tildes — máx. 60 caracteres)"
        )

    @staticmethod
    def _parse_open_command_args(args: list[str]) -> tuple[str, dict]:
        if not args:
            raise ValueError("Uso: /abrir proyecto <id> | /abrir source <id> | /abrir archivo <id> <ruta_relativa>")

        target_kind = _OPEN_TARGET_ALIASES.get(args[0].strip().lower())
        if not target_kind:
            raise ValueError("Destino inválido. Usá proyecto, source o archivo.")

        if target_kind in {"open_project", "open_source"}:
            if len(args) != 2:
                raise ValueError("Ese comando requiere exactamente un project_id.")
            return target_kind, {"project_id": args[1].strip()}

        if len(args) < 3:
            raise ValueError("Uso: /abrir archivo <project_id> <ruta_relativa>")
        return target_kind, {
            "project_id": args[1].strip(),
            "relative_path": " ".join(args[2:]).strip(),
        }

    async def _cmd_abrir(self, update: Update, ctx: ContextTypes):
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            await update.message.reply_text("No autorizado. Vinculá primero con /pair.")
            return

        try:
            action, params = self._parse_open_command_args(ctx.args)
            executor = SystemActionsExecutor(ProjectManager(Path(__file__).resolve().parent.parent.parent))
            result = executor.execute(action, params)
            await update.message.reply_text(f"Acción ejecutada: {result.message}\n{result.target}")
        except Exception as e:
            await update.message.reply_text(str(e))

    @staticmethod
    def _resolve_pending_answer(answer_text: str, success_message: str) -> str:
        gw = get_gateway()
        if not gw.is_waiting:
            return "No hay ninguna pregunta pendiente."
        gw.answer(answer_text)
        return success_message

    async def _cmd_aprobar(self, update: Update, ctx: ContextTypes):
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            await update.message.reply_text("No autorizado. Vinculá primero con /pair.")
            return
        await update.message.reply_text(
            self._resolve_pending_answer("si", "Aprobación enviada. El pipeline continúa.")
        )

    async def _cmd_rechazar(self, update: Update, ctx: ContextTypes):
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            await update.message.reply_text("No autorizado. Vinculá primero con /pair.")
            return
        await update.message.reply_text(
            self._resolve_pending_answer("no", "Rechazo enviado. El pipeline continúa.")
        )

    def _build_system_prompt(self) -> str:
        """Build a rich system prompt with current SODA context."""
        from kernel.projects.project_manager import ProjectManager as PM
        base = Path(__file__).resolve().parent.parent.parent

        # Recent projects
        project_lines = []
        try:
            pm = PM(base)
            recent = pm.list_projects()[-5:] if hasattr(pm, "list_projects") else []
            for p in recent:
                pid = p.get("project_id", "?")
                state = p.get("state", "?")
                desc = (p.get("description") or "")[:80]
                project_lines.append(f"  - {pid} [{state}]: {desc}")
        except Exception:
            pass

        # Active pipeline state + project details
        pipeline_status = "idle"
        active_project_block = ""
        try:
            from ui.server import _pipeline_running, _active_orchestrator
            if _pipeline_running and _active_orchestrator:
                phase = getattr(_active_orchestrator, "_current_phase", "?")
                pipeline_status = f"ejecutando (fase: {phase})"
                proj = getattr(_active_orchestrator, "_active_project", None)
                if proj:
                    pid = getattr(proj, "id", "?")
                    desc = (getattr(proj, "description", "") or "")[:200]
                    skills = getattr(proj, "skills", []) or []
                    profile = getattr(proj, "profile", "") or ""
                    mods = []
                    arch = getattr(proj, "architecture", None)
                    if arch and isinstance(arch, dict):
                        mods = [m.get("nombre", "") for m in arch.get("modulos", [])]
                    active_project_block = (
                        f"\nPROYECTO ACTIVO: {pid} (fase: {phase})\n"
                        f"  Descripcion: {desc}\n"
                        f"  Skills: {', '.join(skills) or 'ninguno'}\n"
                        f"  Perfil: {profile or 'ninguno'}\n"
                        f"  Modulos: {', '.join(mods) or 'aun no generados'}\n"
                    )
        except Exception:
            pass

        # Pending question
        pending_q = ""
        try:
            gw = get_gateway()
            if gw.is_waiting:
                pending_q = f"\nHay una pregunta pendiente esperando respuesta: \"{gw.current_question}\""
        except Exception:
            pass

        ctx_block = ""
        if project_lines:
            ctx_block = "\nProyectos recientes:\n" + "\n".join(project_lines)

        return (
            "Sos SODA, el asistente de BlackMagicBox — sistema de orquestación y generación "
            "automática de software. Tenés personalidad: sos directo, técnico y útil. "
            "Podés hablar de arquitectura, código, bugs, tecnologías, o cualquier tema técnico. "
            "También ayudás a gestionar proyectos SODA.\n\n"
            "COMANDOS QUE PODÉS MENCIONAR AL USUARIO:\n"
            "  /crear <nombre>   — nuevo proyecto\n"
            "  /status           — estado del pipeline\n"
            "  /projects         — últimos proyectos\n"
            "  /aprobar          — aprobar checkpoint\n"
            "  /rechazar         — rechazar checkpoint\n"
            "  /limpiar          — borrar historial del chat\n\n"
            f"ESTADO ACTUAL: pipeline {pipeline_status}{active_project_block}{pending_q}"
            f"{ctx_block}\n\n"
            "Respondé en español, de forma natural y conversacional. "
            "Podés hacer preguntas de vuelta si necesitás más contexto. "
            "Cuando describas código o comandos usá bloques de código Markdown."
        )

    async def _chat_with_ai(self, chat_id: str, message: str) -> str:
        """Multi-turn AI chat with conversation history."""
        try:
            from kernel.drivers.gemini_driver import GeminiDriver
            system = self._build_system_prompt()
            history = self._history[chat_id]
            
            # Add current user message to history
            history.append({"role": "user", "content": message})
            
            # Formatear el historial para el driver que solo acepta un string plano
            formatted_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
            
            gemini = _get_gemini_driver()
            response = await gemini.call(
                system_prompt=system, 
                user_message=formatted_history, 
                max_tokens=1024
            )
            
            reply_text = response.content
            if reply_text:
                history.append({"role": "assistant", "content": reply_text})
            return reply_text or "No pude generar una respuesta."
        except Exception as e:
            return f"Error al procesar tu mensaje: {e}"

    async def _cmd_limpiar(self, update: Update, ctx: ContextTypes):
        """Clear conversation history for this chat."""
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            return
        self._history[chat_id].clear()
        await update.message.reply_text("Historial borrado. Empezamos de cero.")

    # ── /ia — Qwen interactive session ──────────────────────────────────

    async def _cmd_ia(self, update: Update, ctx: ContextTypes):
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            await update.message.reply_text("No autorizado. Vincula primero con /pair.")
            return
        session = _ia_sessions.get(chat_id, {})
        if session.get("active"):
            await update.message.reply_text(
                "La sesion IA ya esta activa. Preguntame lo que quieras.\n"
                "Se cierra sola tras 5 minutos sin actividad."
            )
            return
        _ia_sessions[chat_id] = {"active": True, "task": None, "waiting_close": False}
        self._ia_history: dict = getattr(self, "_ia_history", {})
        self._ia_history[chat_id] = collections.deque(maxlen=20)
        self._ia_reset_timer(chat_id)
        await update.message.reply_text(
            "Sesion IA abierta con Qwen.\n\n"
            "Podés preguntarme sobre:\n"
            "  - Funcionamiento de SODA\n"
            "  - Estado de proyectos y archivos\n"
            "  - Sugerencias de arquitectura o codigo\n"
            "  - Cualquier consulta tecnica\n\n"
            "La sesion se cierra automaticamente a los 5 minutos sin actividad.\n"
            "Para volver a abrir usa /ia"
        )
        await self._tts_speak(
            "Sesion IA abierta. Preguntame lo que necesites sobre SODA o tus proyectos."
        )

    def _ia_reset_timer(self, chat_id: str) -> None:
        session = _ia_sessions.get(chat_id)
        if not session:
            return
        if session.get("task") and not session["task"].done():
            session["task"].cancel()
        session["waiting_close"] = False
        session["task"] = asyncio.create_task(self._ia_timeout(chat_id))

    async def _ia_timeout(self, chat_id: str) -> None:
        await asyncio.sleep(_IA_TIMEOUT_SECS)
        session = _ia_sessions.get(chat_id)
        if not session or not session.get("active"):
            return
        if not session.get("waiting_close"):
            session["waiting_close"] = True
            session["task"] = asyncio.create_task(self._ia_timeout(chat_id))
            await self.send_from_loop(
                "Tenes alguna otra consulta? Si no respondo en 5 minutos cierro la sesion automaticamente."
            )
            await self._tts_speak("Tienes alguna otra consulta?")
        else:
            session["active"] = False
            session["task"] = None
            ia_hist = getattr(self, "_ia_history", {})
            ia_hist.pop(chat_id, None)
            await self.send_from_loop(
                "Sesion IA cerrada. Podes volver a abrirla cuando quieras con /ia"
            )
            await self._tts_speak("Sesion IA cerrada.")

    async def _chat_with_qwen(self, chat_id: str, message: str) -> str:
        """Multi-turn Qwen chat using full message history."""
        try:
            import ollama as _ollama
            from kernel.drivers.ollama_driver import OllamaDriver, PREFERRED_MODELS
            driver = OllamaDriver()
            model = await driver._get_model()
            system = self._build_system_prompt()
            if not hasattr(self, "_ia_history"):
                self._ia_history = {}
            if chat_id not in self._ia_history:
                self._ia_history[chat_id] = collections.deque(maxlen=20)
            history = self._ia_history[chat_id]
            history.append({"role": "user", "content": message})
            messages = [{"role": "system", "content": system}] + list(history)
            client = _ollama.AsyncClient(host=driver.host)
            resp = await asyncio.wait_for(
                client.chat(model=model, messages=messages),
                timeout=120,
            )
            content = resp["message"]["content"]
            history.append({"role": "assistant", "content": content})
            return content or "No pude generar una respuesta."
        except asyncio.TimeoutError:
            return "Qwen no respondio a tiempo. Intenta de nuevo."
        except Exception as e:
            return f"Error con Qwen: {e}"

    async def _handle_pending_creation(self, chat_id: str, text: str, update: Update) -> bool:
        """Handle the project creation wizard steps. Returns True if handled."""
        if chat_id not in _PENDING_CREATION:
            return False
        state = _PENDING_CREATION[chat_id]

        if state["step"] == "awaiting_name":
            name = _sanitize_name(text)
            if not _NAME_RE.match(name):
                await update.message.reply_text(
                    f"'{text[:40]}' no es valido.\n"
                    "Usa solo letras, numeros, _ y - (sin espacios ni tildes).\n"
                    "Ejemplo: MiTiendaOnline\n\n/cancel para cancelar."
                )
                return True
            _PENDING_CREATION[chat_id] = {"step": "awaiting_description", "name": name, "_ts": time.monotonic()}
            await update.message.reply_text(
                f"Proyecto: {name}\n\nDescribi que debe hacer la aplicacion:"
            )
            return True

        if state["step"] == "awaiting_description":
            _PENDING_CREATION[chat_id] = {
                "step": "awaiting_temperature",
                "name": state["name"],
                "description": text,
                "_ts": time.monotonic(),
            }
            await update.message.reply_text(
                "Elegí la temperatura de Copilot:\n\n"
                "🟢 baja  — 1 pasada máximo. Rápido y económico.\n"
                "🟡 media — 3 pasadas máximo. Calidad equilibrada. (recomendado)\n"
                "🔴 alta  — todas las necesarias. Máxima calidad, más lento y costoso en tokens.\n\n"
                "Respondé: baja, media o alta"
            )
            return True

        if state["step"] == "awaiting_temperature":
            temp = text.strip().lower()
            if temp not in ("baja", "media", "alta"):
                await update.message.reply_text("Opción inválida. Respondé con: baja, media o alta")
                return True
            _PENDING_CREATION.pop(chat_id)
            await self._launch_pipeline(update, state["name"], state["description"], temp)
            return True

        return False

    async def _route_text(self, chat_id: str, text: str, update: Update) -> None:
        """Shared routing for both text and transcribed voice messages."""
        # 1. Project creation wizard
        if await self._handle_pending_creation(chat_id, text, update):
            return
        # 2. Pending pipeline question
        gw = get_gateway()
        if gw.is_waiting:
            gw.answer(text)
            await update.message.reply_text("Respuesta recibida. El pipeline continua.")
            return
        # 3. Active /ia Qwen session
        if _ia_sessions.get(chat_id, {}).get("active"):
            self._ia_reset_timer(chat_id)
            await update.message.chat.send_action("typing")
            response = await self._chat_with_qwen(chat_id, text)
            for chunk in _split_message(response):
                await update.message.reply_text(chunk)
            await self._tts_speak(response)
            return
        # 4. Free AI chat with Gemini + TTS reply
        await update.message.chat.send_action("typing")
        response = await self._chat_with_ai(chat_id, text)
        for chunk in _split_message(response):
            await update.message.reply_text(chunk, parse_mode="Markdown")
        await self._tts_speak(response)

    async def _handle_text(self, update: Update, ctx: ContextTypes):
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            return
        text = (update.message.text or "").strip()
        if not text:
            return
        await self._route_text(chat_id, text, update)

    async def _cmd_voz(self, update: Update, ctx: ContextTypes):
        """Gestión de voces Edge TTS. Uso: /voz | /voz <nombre> | /voz muestra <nombre>"""
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            await update.message.reply_text("No autorizado. Vinculá primero con /pair.")
            return

        from kernel.tts.kokoro_tts import KokoroTTS, AVAILABLE_VOICES, wav_to_ogg_opus
        args = (ctx.args or [])

        SAMPLE_TEXT = "Hola, soy SODA. Tu asistente de desarrollo de software con inteligencia artificial."

        # /voz muestra <nombre>  →  escuchar sin cambiar
        if len(args) >= 2 and args[0].lower() in ("muestra", "sample", "preview"):
            voice = args[1].strip()
            label = AVAILABLE_VOICES.get(voice, voice)
            await update.message.reply_text(f"Generando muestra de: {label}...")
            try:
                wav = await KokoroTTS.get().generate_wav(SAMPLE_TEXT, voice_name=voice)
                if wav:
                    await self._send_voice_bytes(wav_to_ogg_opus(wav))
                else:
                    await update.message.reply_text("No se pudo generar la muestra.")
            except Exception as e:
                await update.message.reply_text(f"Error: {e}")
            return

        # /voz <nombre>  →  cambiar y escuchar muestra
        if args:
            voice = args[0].strip()
            label = AVAILABLE_VOICES.get(voice, voice)
            try:
                KokoroTTS.get().set_voice(voice)
                await update.message.reply_text(f"Voz cambiada a: {label}")
                wav = await KokoroTTS.get().generate_wav(SAMPLE_TEXT)
                if wav:
                    await self._send_voice_bytes(wav_to_ogg_opus(wav))
            except Exception as e:
                await update.message.reply_text(f"Error: {e}")
            return

        # /voz  →  listar voces + muestra de la voz actual
        current = KokoroTTS.get()._voice
        lines = [f"Voz actual: {AVAILABLE_VOICES.get(current, current)}\n\nVoces disponibles:"]
        for name, label in AVAILABLE_VOICES.items():
            marker = " ◀ activa" if name == current else ""
            lines.append(f"  /voz {name}  — {label}{marker}")
        lines.append("\nPara escuchar sin cambiar: /voz muestra <nombre>")
        await update.message.reply_text("\n".join(lines))
        # Enviar muestra de la voz actual
        try:
            wav = await KokoroTTS.get().generate_wav(SAMPLE_TEXT)
            if wav:
                await self._send_voice_bytes(wav_to_ogg_opus(wav))
        except Exception as e:
            print(f"  [TTS] muestra de voz actual falló: {e}")

    async def _safe_reply(self, update: Update, text: str, **kwargs):
        """Send a reply with a basic retry on timeout."""
        for attempt in range(2):
            try:
                return await update.message.reply_text(text, **kwargs)
            except Exception as e:
                if "Timed out" in str(e) and attempt == 0:
                    await asyncio.sleep(1)
                    continue
                print(f"  [Telegram] _safe_reply failed: {e}")
                break

    async def _handle_voice(self, update: Update, ctx: ContextTypes):
        """Transcribe an incoming voice message and route through shared _route_text."""
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            return
        # Voice sample registration takes priority
        if chat_id in _PENDING_VOICE_SAMPLE:
            await self._register_voice_sample(update, update.message.voice)
            return
        try:
            from kernel.stt.whisper_stt import WhisperSTT, is_available as stt_available
            if not stt_available():
                await self._safe_reply(update, "STT no disponible — revisá los logs del servidor.")
                return
            await update.message.chat.send_action("typing")
            voice_file = await update.message.voice.get_file()
            ogg_bytes = await voice_file.download_as_bytearray()
            text = WhisperSTT.get().transcribe_bytes(bytes(ogg_bytes), "ogg")
            if not text:
                await self._safe_reply(update, "No pude entender el audio. Intentá de nuevo.")
                return
            await self._safe_reply(update, f'Entendí: "{text}"')
            await self._route_text(chat_id, text, update)
        except Exception as e:
            print(f"  [Telegram] _handle_voice error: {e}")
            await self._safe_reply(update, f"Error al procesar audio: {e}")

    async def _handle_audio(self, update: Update, ctx: ContextTypes):
        """Handle uploaded audio files — used for voice sample registration."""
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            return
        if chat_id in _PENDING_VOICE_SAMPLE:
            await self._register_voice_sample(update, update.message.audio)
        else:
            await update.message.reply_text(
                "Recibí un audio. Si querés registrarlo como muestra de voz usá /voz primero."
            )

    async def _launch_pipeline(
        self, update: Update, name: str, description: str, temperature: str = "media"
    ):
        """POST to local /api/run to start the pipeline."""
        import httpx
        labels = {"baja": "1 pasada", "media": "3 pasadas", "alta": "ilimitado"}
        await update.message.reply_text(
            f"Iniciando proyecto '{name}'...\n"
            f"Temperatura Copilot: {temperature} ({labels.get(temperature, temperature)})\n"
            f"{description[:120]}"
        )
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{_SERVER_URL}/api/run",
                    json={"project_name": name, "description": description,
                          "copilot_temperature": temperature},
                    timeout=10,
                )
            data = r.json()
            if data.get("status") == "started":
                await update.message.reply_text(
                    "Pipeline iniciado. Te aviso cuando termine."
                )
            elif data.get("status") == "busy":
                await update.message.reply_text("El pipeline ya está en ejecución.")
            else:
                await update.message.reply_text(
                    f"Error al iniciar: {data.get('message', r.text[:200])}"
                )
        except Exception as e:
            await update.message.reply_text(f"No se pudo conectar con SODA: {e}")

    async def _cmd_reparar(self, update: Update, ctx: ContextTypes):
        """Launch a self-repair cycle. /reparar [etapa1 etapa2 ...] [--aplicar]"""
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            await update.message.reply_text("No autorizado.")
            return

        args = ctx.args or []
        apply_fixes = "--aplicar" in args
        stages = [a for a in args if not a.startswith("--")] or None

        stage_msg = f"etapas: {', '.join(stages)}" if stages else "todas las etapas"
        apply_msg = " + APLICAR correcciones" if apply_fixes else " (solo informe, sin cambios)"
        await update.message.reply_text(
            f"AutoReparacion iniciada — {stage_msg}{apply_msg}.\n"
            f"El backup se crea automaticamente antes de cualquier cambio.\n"
            f"Te aviso cuando termine."
        )

        import httpx
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{_SERVER_URL}/api/selfrepair/run",
                    json={"stages": stages, "apply_fixes": apply_fixes, "label": "telegram"},
                )
        except Exception as e:
            await update.message.reply_text(f"Error al iniciar autoreparacion: {e}")

    async def _cmd_addskill(self, update: Update, ctx: ContextTypes):
        """
        Import a community skill from a skills.sh URL.
        Usage: /addskill <url> [lang]
        Example: /addskill https://raw.githubusercontent.com/.../SKILL.md typescript
        """
        chat_id = str(update.effective_chat.id)
        if chat_id != self._chat_id:
            return

        args = ctx.args or []
        if not args:
            await update.message.reply_text(
                "Uso: /addskill <url> [lang]\n"
                "Ejemplo: /addskill https://raw.githubusercontent.com/.../SKILL.md python"
            )
            return

        url = args[0]
        target_lang = args[1] if len(args) > 1 else "python"
        await update.message.reply_text(f"Importando skill desde:\n{url}\nIdioma: {target_lang}")

        import httpx
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{_SERVER_URL}/api/skills/add",
                    json={"url": url, "target_lang": target_lang},
                )
            data = r.json()
            if data.get("status") == "ok":
                issues = data.get("quality", {}).get("issues", [])
                quality_note = (" Advertencias: " + "; ".join(issues)) if issues else " Sin problemas de calidad."
                await update.message.reply_text(
                    f"Skill importada: {data['skill_name']}{quality_note}"
                )
            else:
                await update.message.reply_text(f"Error: {data.get('message', 'desconocido')}")
        except Exception as e:
            await update.message.reply_text(f"Error al importar skill: {e}")

    async def _cmd_projects(self, update: Update, ctx: ContextTypes):
        from pathlib import Path
        from kernel.lineage.project_lineage import ProjectLineage
        base = Path(__file__).resolve().parent.parent.parent
        lineage = ProjectLineage(base)
        history = lineage.get_history(limit=5)
        if not history:
            await update.message.reply_text("No projects yet.")
            return
        lines = ["Recent projects:"]
        for p in history:
            state = p.get("state", "?")
            desc = p.get("description", "")[:60]
            lines.append(f"- [{state}] {p['project_id']}: {desc}")
        await update.message.reply_text("\n".join(lines))
