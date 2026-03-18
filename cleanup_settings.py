import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

async def cleanup():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client['waifu_bot']
    res = await db['settings'].delete_one({"id": "global"})
    print(f"Deleted global settings: {res.deleted_count}")

if __name__ == "__main__":
    asyncio.run(cleanup())
