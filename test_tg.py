import os
import asyncio
import httpx
from dotenv import load_dotenv

async def main():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "7349653298")
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": "✅ SODA está ONLINE y escuchando por Telegram."}
        )
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text}")

if __name__ == "__main__":
    asyncio.run(main())
