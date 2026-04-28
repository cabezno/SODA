"""Whisper STT service — singleton, lazy-loaded, thread-safe.

Uses faster-whisper for efficient local transcription.
Model is downloaded on first use and cached by faster-whisper.
"""
from __future__ import annotations

import io
import threading
from pathlib import Path
from typing import Optional


_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "soda_config.json"


def _read_cfg() -> dict:
    import json
    try:
        if _CONFIG_PATH.exists():
            return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


class WhisperSTT:
    """Singleton faster-whisper transcription service."""

    _instance: Optional["WhisperSTT"] = None
    _cls_lock = threading.Lock()

    def __init__(self):
        self._model = None
        self._model_lock = threading.Lock()
        cfg = _read_cfg()
        self._model_size: str = cfg.get("stt_model", "base")
        self._language: Optional[str] = cfg.get("stt_language") or None  # None = auto-detect

    @classmethod
    def get(cls) -> "WhisperSTT":
        if cls._instance is None:
            with cls._cls_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel  # type: ignore
        # Use CUDA if available, else CPU with int8 quantisation for speed
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
        compute = "float16" if device == "cuda" else "int8"
        print(f"  [STT] Loading Whisper '{self._model_size}' on {device} ({compute})…")
        self._model = WhisperModel(self._model_size, device=device, compute_type=compute)
        print("  [STT] Whisper ready.")

    def transcribe_bytes(self, audio_bytes: bytes, audio_format: str = "ogg") -> str:
        """Transcribe audio bytes (any format ffmpeg supports). Returns text."""
        wav = _to_wav_bytes(audio_bytes, audio_format)
        return self._transcribe_wav(wav)

    def transcribe_file(self, path: str | Path) -> str:
        """Transcribe an audio file on disk."""
        with self._model_lock:
            self._ensure_model()
            segments, _ = self._model.transcribe(
                str(path),
                language=self._language,
                beam_size=5,
                vad_filter=True,
            )
            return " ".join(s.text.strip() for s in segments).strip()

    def _transcribe_wav(self, wav_bytes: bytes) -> str:
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            tmp = f.name
        try:
            return self.transcribe_file(tmp)
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass


def _to_wav_bytes(data: bytes, fmt: str) -> bytes:
    """Convert any audio format to 16kHz mono WAV via ffmpeg subprocess."""
    import subprocess, tempfile, os
    with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as fin:
        fin.write(data)
        in_path = fin.name
    out_path = in_path + ".wav"
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", in_path,
                "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
                out_path,
            ],
            check=True,
            capture_output=True,
        )
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        for p in (in_path, out_path):
            try:
                os.unlink(p)
            except OSError:
                pass


def is_available() -> bool:
    try:
        import faster_whisper  # noqa: F401  # type: ignore
        return True
    except Exception as e:
        print(f"  [STT] faster-whisper not available: {e}")
        return False
