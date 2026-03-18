import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

async def check():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client['waifu_bot']
    
    # Check all users with waifus
    users = await db['users'].find({"waifus": {"$exists": True, "$not": {"$size": 0}}}).to_list(length=10)
    for u in users:
        print(f"User: {u.get('id')} | Waifus: {u.get('waifus')}")

if __name__ == "__main__":
    asyncio.run(check())
