import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

async def check():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client['waifu_bot']
    
    # 1. Check User ID types
    user_doc = await db['users'].find_one({"waifus": {"$exists": True, "$not": {"$size": 0}}})
    if user_doc:
        uid = user_doc.get("id")
        print(f"User ID: {uid} | Type: {type(uid)}")
    else:
        print("No users with waifus found!")
        
    # 2. Check Global Threshold again
    settings = await db['settings'].find_one({"id": "global"})
    print(f"Global Settings Document: {settings}")

if __name__ == "__main__":
    asyncio.run(check())
