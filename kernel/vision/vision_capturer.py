from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Capture:
    path: str
    exists: bool
    size_bytes: int
    error: str = ""
    url: str = ""


class VisionCapturer:
    """Screenshot capturer — uses Playwright if available, gracefully skips if not."""

    async def capture_url(
        self,
        url: str,
        output_path: Path,
        viewport: dict | None = None,
        wait_ms: int = 1500,
    ) -> Capture:
        """Take a screenshot of a running web app. Requires playwright installed."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return Capture(
                path=str(output_path), exists=False, size_bytes=0,
                error="playwright not installed — run: pip install playwright && playwright install chromium",
                url=url,
            )

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                if viewport:
                    await page.set_viewport_size(viewport)
                else:
                    await page.set_viewport_size({"width": 1280, "height": 800})
                await page.goto(url, wait_until="networkidle", timeout=20000)
                if wait_ms > 0:
                    import asyncio
                    await asyncio.sleep(wait_ms / 1000)
                await page.screenshot(path=str(output_path), full_page=False)
                await browser.close()
                size = output_path.stat().st_size
                return Capture(path=str(output_path), exists=True, size_bytes=size, url=url)
        except Exception as e:
            return Capture(path=str(output_path), exists=False, size_bytes=0, error=str(e)[:300], url=url)

    async def capture_multiple(
        self, url: str, output_dir: Path, viewports: list[dict] | None = None
    ) -> list[Capture]:
        """Capture desktop + tablet + mobile viewports of a URL."""
        if viewports is None:
            viewports = [
                {"width": 1280, "height": 800},   # desktop
                {"width": 768, "height": 1024},   # tablet
                {"width": 375, "height": 812},    # mobile
            ]
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        captures = []
        for i, vp in enumerate(viewports):
            name = f"screenshot_{vp['width']}x{vp['height']}.png"
            cap = await self.capture_url(url, output_dir / name, viewport=vp)
            captures.append(cap)
        return captures

    def capture(self, image_path: Path) -> Capture:
        """Legacy: metadata check for an existing image file."""
        p = Path(image_path)
        if not p.exists():
            return Capture(path=str(p), exists=False, size_bytes=0)
        return Capture(path=str(p), exists=True, size_bytes=p.stat().st_size)
