import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

async def check():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client['waifu_bot']
    
    block = await db['blocks'].find_one({"user_id": 6804892450})
    print(f"Block status for 6804892450: {block}")
    
    all_blocks = await db['blocks'].find({}).to_list(length=10)
    print(f"Recent blocks: {all_blocks}")

if __name__ == "__main__":
    asyncio.run(check())
