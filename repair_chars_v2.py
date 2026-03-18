import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

async def repair():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client['waifu_bot']
    
    print(f"Connected to DB: {db.name}")
    count = await db['characters'].count_documents({})
    print(f"Total characters in collection: {count}")
    
    cursor = db['characters'].find({})
    repaired_all = 0
    async for char in cursor:
        print(f"Checking char: {char.get('name')} | id: {char.get('id')} | rarity: {char.get('rarity')}")
        updates = {}
        if not char.get('rarity'): updates['rarity'] = 'Common'
        if not char.get('id'): updates['id'] = 'FIXED_' + str(repaired_all) # Test simple ID
        
        if updates:
            print(f"  -> Applying updates: {updates}")
            res = await db['characters'].update_one({"_id": char["_id"]}, {"$set": updates})
            print(f"  -> Modified count: {res.modified_count}")
            repaired_all += 1
            
    print(f"Total repaired: {repaired_all}")

if __name__ == "__main__":
    asyncio.run(repair())
