import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

async def check():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client['waifu_bot']
    
    sudos = await db['sudos'].find({}).to_list(length=None)
    print(f"Sudos: {sudos}")
    
    # Check if user 6804892450 is there
    user_sudo = await db['sudos'].find_one({"id": 6804892450})
    print(f"User 6804892450 Sudo State: {user_sudo}")

if __name__ == "__main__":
    asyncio.run(check())
