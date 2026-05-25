"""Edge TTS — reemplaza F5-TTS completamente.

Voces argentinas:
  es-AR-ElenaNeural  — femenina (default)
  es-AR-TomasNeural  — masculina

Otras disponibles:
  es-ES-AlvaroNeural, es-MX-DaliaNeural, etc.

Requiere: pip install edge-tts pydub
          ffmpeg en PATH (para OGG Opus en Telegram)
"""
from __future__ import annotations

import asyncio
import io
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional

# ── Constantes de compatibilidad con el código existente ──────────────────────
VOICES_DIR = Path(__file__).parent / "voices"
VOICES_DIR.mkdir(exist_ok=True)

DEFAULT_VOICE = "es-AR-TomasNeural"

AVAILABLE_VOICES = {
    "es-AR-ElenaNeural": "Argentina — Elena (femenina)",
    "es-AR-TomasNeural": "Argentina — Tomás (masculino)",
    "es-ES-AlvaroNeural": "España — Álvaro (masculino)",
    "es-ES-ElviraNeural": "España — Elvira (femenina)",
    "es-MX-DaliaNeural": "México — Dalia (femenina)",
    "es-MX-JorgeNeural": "México — Jorge (masculino)",
}

# ── Helpers de detección ──────────────────────────────────────────────────────

def is_available() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False


def has_voice() -> bool:
    """Con Edge TTS no se necesita muestra de voz — siempre disponible."""
    return True


def tts_enabled() -> bool:
    """Lee soda_config.json para ver si TTS está habilitado."""
    try:
        import json
        cfg_path = Path(__file__).resolve().parent.parent.parent / "soda_config.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            return bool(cfg.get("tts_enabled", True))
    except Exception:
        pass
    return True


def tts_telegram_enabled() -> bool:
    return tts_enabled() and is_available()


# ── Conversión de audio ───────────────────────────────────────────────────────

def _find_ffmpeg() -> Optional[str]:
    """Devuelve la ruta absoluta a ffmpeg."""
    import shutil
    # Preferir el ffmpeg del proyecto si existe
    project_ffmpeg = Path(__file__).resolve().parent.parent.parent / "ffmpeg.exe"
    if project_ffmpeg.exists():
        return str(project_ffmpeg)
    found = shutil.which("ffmpeg")
    return found


def _mp3_to_wav(mp3_bytes: bytes) -> bytes:
    """Convierte MP3 → WAV usando ffmpeg directamente (evita dependencia de ffprobe)."""
    ffmpeg = _find_ffmpeg() or "ffmpeg"
    proc = subprocess.run(
        [ffmpeg, "-y", "-f", "mp3", "-i", "pipe:0", "-f", "wav", "pipe:1"],
        input=mp3_bytes,
        capture_output=True,
        timeout=30,
    )
    if proc.returncode == 0 and proc.stdout:
        return proc.stdout
    raise RuntimeError(f"ffmpeg mp3→wav falló: {proc.stderr[:200]}")


def wav_to_ogg_opus(wav_bytes: bytes) -> bytes:
    """Convierte WAV → OGG Opus (formato de nota de voz de Telegram)."""
    try:
        ffmpeg = _find_ffmpeg() or "ffmpeg"
        proc = subprocess.run(
            [
                ffmpeg, "-y",
                "-f", "wav", "-i", "pipe:0",
                "-c:a", "libopus", "-b:a", "64k",
                "-f", "ogg", "pipe:1",
            ],
            input=wav_bytes,
            capture_output=True,
            timeout=30,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
    except Exception as e:
        print(f"  [TTS] wav_to_ogg_opus error: {e}")
    return wav_bytes


# ── SSML helpers ──────────────────────────────────────────────────────────────

def _build_ssml(text: str, voice: str, rate: str = "+0%", pitch: str = "+0Hz") -> str:
    """Envuelve el texto en SSML con prosody para énfasis y modulación natural."""
    import xml.sax.saxutils as _xml
    # Escape primero, luego agregar pausas (para que los tags XML no se escapen)
    safe = _xml.escape(text)
    for punct, ms in [("...", "400ms"), (".", "300ms"), (",", "150ms"),
                      ("!", "300ms"), ("?", "300ms"), (";", "200ms"), (":", "150ms")]:
        escaped_punct = _xml.escape(punct)
        safe = safe.replace(escaped_punct, f'{escaped_punct}<break time="{ms}"/>')
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="es-AR">'
        f'<voice name="{voice}">'
        f'<prosody rate="{rate}" pitch="{pitch}">'
        f'{safe}'
        f'</prosody>'
        f'</voice>'
        f'</speak>'
    )


# ── Resolución de nombre corto → nombre completo ─────────────────────────────

_SHORT_NAMES: dict[str, str] = {
    "elena": "es-AR-ElenaNeural",
    "tomas": "es-AR-TomasNeural",
    "tomás": "es-AR-TomasNeural",
    "alvaro": "es-ES-AlvaroNeural",
    "álvaro": "es-ES-AlvaroNeural",
    "elvira": "es-ES-ElviraNeural",
    "dalia": "es-MX-DaliaNeural",
    "jorge": "es-MX-JorgeNeural",
}


def _resolve_voice(name: str) -> str:
    """Acepta nombre corto ('tomas') o completo ('es-AR-TomasNeural') y devuelve el completo."""
    if name in AVAILABLE_VOICES:
        return name
    lower = name.lower().strip()
    if lower in _SHORT_NAMES:
        return _SHORT_NAMES[lower]
    return name  # aceptar cualquier nombre Edge TTS válido desconocido


# ── Clase principal ───────────────────────────────────────────────────────────

class KokoroTTS:
    """Singleton TTS usando Edge TTS (Microsoft Neural). Misma API que el F5-TTS anterior."""

    _instance: Optional["KokoroTTS"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._voice = DEFAULT_VOICE
        self._speed = 1.0  # 1.0 = normal

    @classmethod
    def get(cls) -> "KokoroTTS":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    # ── Configuración ─────────────────────────────────────────────────────────

    def set_voice(self, voice_name: str) -> None:
        resolved = _resolve_voice(voice_name)
        self._voice = resolved

    def set_speed(self, speed: float) -> None:
        self._speed = max(0.5, min(2.0, float(speed)))

    def list_voices(self) -> dict:
        custom = [
            p.stem for p in VOICES_DIR.glob("*.wav")
            if p.stem not in AVAILABLE_VOICES
        ]
        return {
            "active": self._voice,
            "current_voice": self._voice,  # backwards-compat
            "speed": self._speed,
            "builtin": list(AVAILABLE_VOICES.keys()),
            "custom": custom,
            "voices": [
                {"name": k, "label": v}
                for k, v in AVAILABLE_VOICES.items()
            ],
            "engine": "edge-tts",
        }

    def delete_voice(self, voice_name: str) -> bool:
        """Elimina una voz clonada. Las voces built-in no se pueden eliminar."""
        if voice_name in AVAILABLE_VOICES:
            return False
        wav = VOICES_DIR / f"{voice_name}.wav"
        txt = VOICES_DIR / f"{voice_name}.txt"
        deleted = False
        if wav.exists():
            wav.unlink()
            deleted = True
        if txt.exists():
            txt.unlink()
            deleted = True
        return deleted

    # ── Generación ────────────────────────────────────────────────────────────

    def _speed_to_rate(self) -> str:
        """Convierte self._speed (0.5–2.0) al formato de rate SSML de Edge TTS."""
        pct = int((self._speed - 1.0) * 100)
        if pct >= 0:
            return f"+{pct}%"
        return f"{pct}%"

    async def generate_wav(
        self,
        text: str,
        voice_name: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> Optional[bytes]:
        """Genera audio WAV para el texto dado. Retorna bytes o None si falla."""
        if not text or not text.strip():
            return None
        try:
            import edge_tts

            voice = voice_name or self._voice
            rate = self._speed_to_rate() if speed is None else (
                f"+{int((speed - 1.0) * 100)}%" if speed >= 1.0
                else f"{int((speed - 1.0) * 100)}%"
            )

            # Generar MP3 en memoria
            mp3_buf = io.BytesIO()
            communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3_buf.write(chunk["data"])

            mp3_bytes = mp3_buf.getvalue()
            if not mp3_bytes:
                print(f"  [TTS] Edge TTS no devolvió audio para: {text[:60]}")
                return None

            return _mp3_to_wav(mp3_bytes)

        except Exception as e:
            print(f"  [TTS] generate_wav error: {e}")
            return None

    async def generate_ogg(
        self,
        text: str,
        voice_name: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> Optional[bytes]:
        """Genera OGG Opus directamente (más eficiente para Telegram)."""
        wav = await self.generate_wav(text, voice_name=voice_name, speed=speed)
        if not wav:
            return None
        return wav_to_ogg_opus(wav)
