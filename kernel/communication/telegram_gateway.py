import asyncio
import json
import os
import secrets
from pathlib import Path
from typing import Optional

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from kernel.communication.messaging_gateway import MessagingGateway


PAIRING_CODES: dict[str, str] = {}   # code → "pending"
SODA_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "soda_config.json"


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
    def __init__(self):
        self._token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        config = _load_config()
        self._chat_id: Optional[str] = config.get("telegram_chat_id")
        self._bot: Optional[Bot] = Bot(self._token) if self._token else None
        self._app: Optional[Application] = None

    def is_configured(self) -> bool:
        return bool(self._token and self._chat_id)

    async def send(self, message: str, data: Optional[dict] = None) -> bool:
        if not self.is_configured():
            return False
        try:
            await self._bot.send_message(
                chat_id=self._chat_id,
                text=message,
                parse_mode=None,
            )
            return True
        except Exception as e:
            print(f"  [Telegram] Send failed: {e}")
            return False

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
        """Launch the bot in a background thread (blocking loop inside thread)."""
        if not self._token:
            print("  [Telegram] No TELEGRAM_BOT_TOKEN — bot not started.")
            return
        import threading
        t = threading.Thread(target=self._run_bot_sync, daemon=True)
        t.start()

    def _run_bot_sync(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._run_bot())

    async def _run_bot(self):
        self._app = Application.builder().token(self._token).build()
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("pair", self._cmd_pair))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(CommandHandler("projects", self._cmd_projects))
        await self._app.run_polling(stop_signals=None)

    async def _cmd_start(self, update: Update, ctx: ContextTypes):
        await update.message.reply_text(
            "SODA Bot ready.\n"
            "To pair: generate a code in the desktop app, then send /pair <CODE>"
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
        from ui.server import _pipeline_running
        msg = "Pipeline running..." if _pipeline_running else "Idle — ready for a new project."
        await update.message.reply_text(f"SODA Status: {msg}")

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
