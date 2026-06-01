"""SODA launcher — starts FastAPI server then opens the UI.

Usage:
    python -m ui.launcher            # pywebview native window (default)
    python -m ui.launcher --browser  # system default browser
"""
from __future__ import annotations

import sys
import os
import threading
import time
import urllib.request


def _generate_bmb_icon() -> str | None:
    """Generate bmb_icon.ico next to this file and return its path."""
    icon_path = os.path.join(os.path.dirname(__file__), "bmb_icon.ico")
    if os.path.exists(icon_path):
        return icon_path
    try:
        from PIL import Image, ImageDraw, ImageFont

        def _make_frame(size: int) -> Image.Image:
            img = Image.new("RGBA", (size, size), (22, 22, 22, 255))
            draw = ImageDraw.Draw(img)
            gold = (200, 160, 60, 255)
            text = "BMB"
            font = None
            for font_file in [
                "C:/Windows/Fonts/arialbd.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/seguibl.ttf",
            ]:
                try:
                    font = ImageFont.truetype(font_file, max(int(size * 0.42), 7))
                    break
                except Exception:
                    continue
            if font:
                bbox = draw.textbbox((0, 0), text, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text(((size - tw) // 2, (size - th) // 2 - bbox[1]), text,
                          fill=gold, font=font)
            else:
                draw.text((2, 2), "B", fill=gold)
            return img

        base = _make_frame(256)
        base.save(
            icon_path,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
        return icon_path
    except Exception as e:
        print(f"[BMB] Could not generate icon: {e}")
        return None


def _apply_window_icon(icon_path: str, title: str) -> None:
    """Set the Win32 window icon via ctypes (replaces the Python.exe logo)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            return
        LR_LOADFROMFILE = 0x0010
        IMAGE_ICON = 1
        WM_SETICON = 0x0080
        path_w = str(icon_path)
        for size, kind in ((16, 0), (32, 1)):
            hicon = user32.LoadImageW(None, path_w, IMAGE_ICON, size, size, LR_LOADFROMFILE)
            if hicon:
                user32.SendMessageW(hwnd, WM_SETICON, kind, hicon)
    except Exception as e:
        print(f"[BMB] Could not apply window icon: {e}")

# Ensure project root is on sys.path when running as a module
if __package__ in (None, ""):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Fix Windows console encoding so special chars don't crash
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SERVER_HOST = "0.0.0.0"       # bind to all interfaces so LAN devices can connect
SERVER_PORT = 8000
SERVER_URL  = f"http://127.0.0.1:{SERVER_PORT}"  # local webview still uses loopback
WINDOW_TITLE = "BlackMagicBox Soda"

# -----------------------------------------------------------------------
# Server
# -----------------------------------------------------------------------

def _start_server() -> None:
    try:
        import uvicorn
        import socket
        
        # [IMP-040] Verificamos si el puerto está ocupado
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((SERVER_HOST, SERVER_PORT)) == 0:
                print(f"[SODA] Puerto {SERVER_PORT} ocupado. Activando Health Warden (Auto-Kill)...")
                if sys.platform == "win32":
                    os.system(f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :{SERVER_PORT}\') do taskkill /F /PID %a 2>nul')
                else:
                    os.system(f"fuser -k {SERVER_PORT}/tcp")
                time.sleep(2) # Esperar liberación

        os.environ.setdefault("SODA_PORT", str(SERVER_PORT))
        from ui.server import app
        uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="warning")
    except Exception as e:
        print(f"[SODA] Server error: {e}")


def _wait_for_server(timeout: float = 30.0) -> bool:
    """Poll /api/health until server is ready or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{SERVER_PORT}/api/health", timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


# -----------------------------------------------------------------------
# UI modes
# -----------------------------------------------------------------------

def _open_browser() -> None:
    import webbrowser
    print(f"[SODA] Opening browser: {SERVER_URL}")
    webbrowser.open(SERVER_URL)
    print("[SODA] Server running. Close this window to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[SODA] Stopped.")


def _open_webview() -> None:
    try:
        import webview
    except ImportError:
        print("[SODA] pywebview not installed.")
        print("[SODA]   Install: pip install pywebview")
        print("[SODA]   Falling back to browser...")
        _open_browser()
        return

    # pywebview 6.x removed __version__ — use importlib.metadata instead
    try:
        import importlib.metadata
        wv_ver = importlib.metadata.version("pywebview")
    except Exception:
        wv_ver = "?"
    print(f"[SODA] Opening native window (pywebview {wv_ver})...")

    # Determine best renderer for the platform
    gui = None
    if sys.platform == "win32":
        gui = "edgechromium"   # Edge Chromium — full WebSocket + JS support on Windows

    # Persistent storage so Edge doesn't lose session data on restart
    storage_path = os.path.join(os.path.dirname(__file__), "..", ".webview_cache")
    os.makedirs(storage_path, exist_ok=True)

    icon_path = _generate_bmb_icon()

    try:
        window = webview.create_window(
            title=WINDOW_TITLE,
            url=SERVER_URL,
            width=1440,
            height=920,
            min_size=(900, 600),
            resizable=True,
            background_color="#1e1e1e",
            text_select=True,
            easy_drag=False,   # prevent accidental window drag when clicking UI elements
        )

        if icon_path and sys.platform == "win32":
            def _on_shown():
                time.sleep(0.15)  # let the Win32 window fully initialize
                _apply_window_icon(icon_path, WINDOW_TITLE)
            window.events.shown += _on_shown

        webview.start(
            gui=gui,
            debug=False,
            private_mode=False,  # allow WebSockets & localStorage to work normally
            storage_path=os.path.abspath(storage_path),
        )
    except Exception as e:
        print(f"[SODA] pywebview failed: {e}")
        print("[SODA] Falling back to browser...")
        _open_browser()


# -----------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------

def run_app(use_browser: bool = False) -> None:
    print(f"[SODA] Starting server at {SERVER_URL} ...")

    t = threading.Thread(target=_start_server, daemon=True)
    t.start()

    ready = _wait_for_server(timeout=30.0)
    if not ready:
        print("[SODA] Server did not respond in 30s — check for errors above.")
        return
    print("[SODA] Server ready.")

    if use_browser:
        _open_browser()
    else:
        _open_webview()


if __name__ == "__main__":
    use_browser = "--browser" in sys.argv
    run_app(use_browser=use_browser)
