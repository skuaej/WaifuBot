import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

async def test_setspawn(val):
    client = AsyncIOMotorClient(MONGO_URI)
    db = client['waifu_bot']
    
    # Simulate /setspawn command
    await db['settings'].update_one(
        {"id": "global"},
        {"$set": {"spawn_threshold": val}},
        upsert=True
    )
    
    # Check
    res = await db['settings'].find_one({"id": "global"})
    print(f"Global settings after simulation: {res}")

if __name__ == "__main__":
    import sys
    val = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    asyncio.run(test_setspawn(val))
