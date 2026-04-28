"""Voice registration for F5-TTS: saves reference audio (.wav) + transcript (.txt).

Conversion pipeline (in order of preference):
  1. torchaudio + soundfile backend — handles WAV, MP3, FLAC, OGG Vorbis, OGG Opus
     (OGG Opus = what Telegram voice notes send)
  2. ffmpeg subprocess — fallback for M4A/AAC and other exotic containers
     (only attempted if ffmpeg is on PATH)

Output: 16 kHz mono PCM_16 WAV — optimal for F5-TTS reference inference.
"""
from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from pathlib import Path

_TARGET_SR = 16_000  # Hz
_MAX_REF_SECS = 8    # F5-TTS quality degrades with very long refs; 5-8s is ideal

# Formats soundfile can read (no ffmpeg needed)
_SOUNDFILE_EXTS = {
    ".wav", ".flac", ".ogg", ".oga",   # OGG Vorbis & Opus
    ".mp3", ".aiff", ".aif", ".au",
    ".caf", ".rf64", ".sds",
}


def save_reference_voice(
    audio_path: str | Path,
    voice_name: str,
    ref_text: str,
    voices_dir: Path,
) -> Path:
    """Convert any audio to 16 kHz mono WAV and save with transcript."""
    audio_path = Path(audio_path)
    dest_wav = voices_dir / f"{voice_name}.wav"
    dest_txt = voices_dir / f"{voice_name}.txt"

    wav_bytes = _to_wav_16k(audio_path)
    dest_wav.write_bytes(wav_bytes)
    dest_txt.write_text(ref_text.strip(), encoding="utf-8")
    return dest_wav


def _to_wav_16k(src: Path) -> bytes:
    """Load audio from src, resample to 16 kHz mono, return PCM_16 WAV bytes."""
    last_err: Exception | None = None

    # 1. torchaudio via soundfile (handles OGG Opus from Telegram voice notes)
    try:
        return _load_via_torchaudio(src)
    except Exception as e:
        last_err = e
        print(f"  [VoiceCloner] torchaudio load failed for '{src.name}': {e}")

    # 2. ffmpeg subprocess (M4A/AAC and other exotic formats)
    if shutil.which("ffmpeg"):
        try:
            return _load_via_ffmpeg(src)
        except Exception as e:
            last_err = e
            print(f"  [VoiceCloner] ffmpeg fallback failed for '{src.name}': {e}")

    raise RuntimeError(
        f"No se pudo convertir '{src.name}'. "
        f"Formatos admitidos sin ffmpeg: WAV, MP3, OGG, FLAC. "
        f"Para M4A/AAC instalá ffmpeg (choco install ffmpeg). "
        f"Último error: {last_err}"
    )


def _load_via_torchaudio(src: Path) -> bytes:
    import torchaudio  # type: ignore
    import soundfile as sf  # type: ignore

    waveform, sr = torchaudio.load(str(src))

    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    if sr != _TARGET_SR:
        waveform = torchaudio.functional.resample(waveform, sr, _TARGET_SR)

    # Clip to _MAX_REF_SECS so ref_text can accurately cover the whole audio
    max_samples = _MAX_REF_SECS * _TARGET_SR
    if waveform.shape[-1] > max_samples:
        waveform = waveform[..., :max_samples]

    audio_np = waveform.squeeze(0).numpy()
    buf = io.BytesIO()
    sf.write(buf, audio_np, _TARGET_SR, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _load_via_ffmpeg(src: Path) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out:
        out_path = out.name
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(src),
                "-ar", str(_TARGET_SR),
                "-ac", "1",
                "-sample_fmt", "s16",
                out_path,
            ],
            check=True,
            capture_output=True,
        )
        return Path(out_path).read_bytes()
    finally:
        Path(out_path).unlink(missing_ok=True)
