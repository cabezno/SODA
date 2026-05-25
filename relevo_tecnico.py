import asyncio
import os
import sys
import httpx
import socket
from pathlib import Path
from dotenv import load_dotenv

async def check_port(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(('127.0.0.1', port)) == 0
    except:
        return False

async def main():
    load_dotenv()
    print("=== INFORME DE RELEVO TÉCNICO SODA ===")
    
    # 1. Infraestructura Core
    print("\n[1] INFRAESTRUCTURA CORE")
    port_8000 = await check_port(8000)
    print(f"  - Servidor API (Puerto 8000): {'ONLINE' if port_8000 else 'OFFLINE'}")
    
    # 2. Drivers de IA
    print("\n[2] ESTADO DE INTELIGENCIA (DRIVERS)")
    keys = {
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY")
    }
    for k, v in keys.items():
        print(f"  - {k}: {'CONFIGURADA' if v else 'FALTANTE'}")
    
    try:
        from kernel.drivers.gemini_driver import GeminiDriver
        g = GeminiDriver()
        # Test ultra-rápido
        resp = await g.prompt("test", "di ok", max_tokens=5)
        print(f"  - Test Gemini: OK")
    except Exception as e:
        print(f"  - Test Gemini: ERROR ({str(e)[:50]})")

    # 3. Canales de Comunicación
    print("\n[3] CANALES DE COMUNICACIÓN")
    from kernel.communication.telegram_gateway import TelegramGateway
    tg = TelegramGateway()
    print(f"  - Telegram Token: {'PRESENTE' if tg._token else 'FALTANTE'}")
    print(f"  - Telegram ChatID: {tg._chat_id if tg._chat_id else 'NO VINCULADO'}")
    
    # 4. Proyectos y Persistencia
    print("\n[4] PROYECTOS Y PERSISTENCIA")
    projects_dir = Path("projects")
    if projects_dir.exists():
        count = len([d for d in projects_dir.iterdir() if d.is_dir()])
        print(f"  - Total Proyectos: {count}")
    else:
        print("  - Carpeta 'projects': NO ENCONTRADA")

    # 5. Sandbox (Docker)
    print("\n[5] SANDBOX DE EJECUCIÓN")
    try:
        import docker
        client = docker.from_env()
        client.ping()
        print("  - Docker Engine: OPERATIVO")
    except Exception:
        print("  - Docker Engine: NO DISPONIBLE / CERRADO")

    print("\n=== FIN DEL RELEVO ===")

if __name__ == "__main__":
    asyncio.run(main())
