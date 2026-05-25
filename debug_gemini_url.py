import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GEMINI_API_KEY")

async def test_url(url, payload):
    async with httpx.AsyncClient() as client:
        try:
            print(f"Testing URL: {url.split('?')[0]}")
            resp = await client.post(url, json=payload)
            print(f"Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Error: {resp.text[:200]}")
            else:
                print("✅ Success!")
                return True
        except Exception as e:
            print(f"Exception: {e}")
    return False

async def main():
    if not key:
        print("No API Key found.")
        return

    # Pattern 1: v1beta with models/ prefix
    url1 = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    
    payload_no_sys = {
        "contents": [{"parts": [{"text": "hi"}]}]
    }

    print("--- Test: v1beta + gemini-2.0-flash ---")
    await test_url(url1, payload_no_sys)

if __name__ == "__main__":
    asyncio.run(main())
