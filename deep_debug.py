import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

async def deep_debug():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client['waifu_bot']
    
    # 1. Check Global Settings
    settings = await db['settings'].find_one({"id": "global"})
    print(f"Global Settings: {settings}")
    
    # 2. Check User 6804892450 (the one who said it doesn't show)
    # Actually I should check all users who might have grabbed
    users = await db['users'].find({"waifus": {"$exists": True, "$not": {"$size": 0}}}).to_list(length=10)
    for u in users:
        uid = u.get('id')
        waifus = u.get('waifus', [])
        hmode = u.get('hmode', 'Default')
        print(f"User {uid} | waifus: {waifus} | hmode: {hmode}")
        
        # Check if characters exist
        for wid in waifus:
            char = await db['characters'].find_one({"id": wid})
            print(f"  - Searching for char ID '{wid}': {'FOUND' if char else 'NOT FOUND'}")
            if char:
                print(f"    - Char: {char.get('name')} | rarity: {char.get('rarity')}")
                
    # 3. Check Groups for Spawn State
    groups = await db['groups'].find({}).to_list(length=10)
    for g in groups:
         print(f"Group {g.get('id')} | count: {g.get('message_count')} | target: {g.get('spawn_target')}")

if __name__ == "__main__":
    asyncio.run(deep_debug())
