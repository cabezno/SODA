import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GEMINI_API_KEY")

async def list_models():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                models = resp.json().get('models', [])
                print(f"Found {len(models)} models.")
                for m in models[:10]:
                    print(f" - {m['name']}")
            else:
                print(f"Error: {resp.text}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())
