import webview
import threading
import uvicorn
import sys
import os
import time
from ui.server import app

def start_server():
    """Inicia el servidor FastAPI en un hilo separado."""
    print("📡 Iniciando servidor interno de SODA...")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

def run_app():
    # 1. Iniciar el servidor en segundo plano
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # 2. Esperar un momento a que el servidor esté listo
    time.sleep(2)

    # 3. Crear la ventana nativa de SODA
    print("🚀 Abriendo interfaz nativa...")
    window = webview.create_window(
        title="SODA — Software Orchestration & Development Agency",
        url="http://127.0.0.1:8000",
        width=1400,
        height=900,
        resizable=True,
        background_color='#1e1e1e'
    )

    # 4. Iniciar el bucle de la aplicación
    webview.start()

if __name__ == "__main__":
    run_app()