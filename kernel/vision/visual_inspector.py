from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VisualInspection:
    path: str
    format: str
    size_bytes: int
    valid_image: bool
    ai_analysis: str = ""
    renders_correctly: bool = True
    issues_detected: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)


class VisualInspector:
    """Image inspector — local format check + AI analysis via Gemini Flash vision."""

    ANALYSIS_PROMPT = (
        "You are a visual QA inspector for web applications. "
        "Analyze this screenshot and respond ONLY with valid JSON:\n"
        '{"renders_correctly": true|false, '
        '"visible_errors": ["..."], '
        '"ui_issues": ["..."], '
        '"suggestions": ["..."], '
        '"summary": "one sentence"}'
    )

    def __init__(self, gemini_driver=None):
        self.gemini = gemini_driver

    @staticmethod
    def _detect_format(path: Path) -> str:
        try:
            head = path.read_bytes()[:12]
        except Exception:
            return ""
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if head.startswith(b"\xff\xd8\xff"):
            return "jpeg"
        if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
            return "gif"
        if head.startswith(b"RIFF") and b"WEBP" in head:
            return "webp"
        return ""

    def inspect(self, image_path: Path) -> VisualInspection:
        """Local-only format check (sync)."""
        p = Path(image_path)
        if not p.exists():
            return VisualInspection(path=str(p), format="", size_bytes=0, valid_image=False)
        img_fmt = self._detect_format(p)
        size = p.stat().st_size
        return VisualInspection(path=str(p), format=img_fmt, size_bytes=size, valid_image=bool(img_fmt))

    async def analyze(self, image_path: Path, context: str = "") -> VisualInspection:
        """Full AI analysis: local check + Gemini Flash multimodal vision."""
        result = self.inspect(image_path)
        if not result.valid_image:
            return result

        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return result

        try:
            import httpx
            image_data = Path(image_path).read_bytes()
            b64 = base64.b64encode(image_data).decode()
            mime = "image/png" if result.format == "png" else "image/jpeg"

            context_note = f"\nContext: {context}" if context else ""
            payload = {
                "contents": [{
                    "parts": [
                        {"text": f"{self.ANALYSIS_PROMPT}{context_note}"},
                        {"inline_data": {"mime_type": mime, "data": b64}},
                    ]
                }],
                "generationConfig": {"maxOutputTokens": 512, "temperature": 0.1},
            }
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.0-flash:generateContent?key={api_key}"
            )
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(url, json=payload)

            if r.status_code == 200:
                raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                match = re.search(r"\{.*\}", raw, re.DOTALL)
                parsed: dict = {}
                if match:
                    try:
                        parsed = json.loads(match.group(0))
                    except Exception:
                        pass
                result.renders_correctly = bool(parsed.get("renders_correctly", True))
                result.issues_detected = (
                    parsed.get("visible_errors", []) + parsed.get("ui_issues", [])
                )
                result.suggestions = parsed.get("suggestions", [])
                result.ai_analysis = parsed.get("summary", raw[:200])
        except Exception as e:
            result.ai_analysis = f"AI analysis failed: {e}"

        return result
