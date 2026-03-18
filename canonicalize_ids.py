import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

async def repair_all():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client['waifu_bot']
    
    print("Normalizing all IDs (removing leading zeros)...")
    
    # 1. Repair Characters Collection
    chars = await db['characters'].find({}).to_list(length=None)
    for c in chars:
        cid = c.get('id')
        if cid and cid.isdigit():
            normalized = str(int(cid))
            if normalized != cid:
                await db['characters'].update_one({"_id": c["_id"]}, {"$set": {"id": normalized}})
                print(f"Normalized char ID: {cid} -> {normalized}")
                
    # 2. Repair Users Collection (waifus list)
    users = await db['users'].find({"waifus": {"$exists": True}}).to_list(length=None)
    for u in users:
        waifus = u.get('waifus', [])
        normalized_waifus = [str(int(wid)) if wid.isdigit() else wid for wid in waifus]
        if normalized_waifus != waifus:
            await db['users'].update_one({"_id": u["_id"]}, {"$set": {"waifus": normalized_waifus}})
            print(f"Normalized waifus for user {u.get('id')}")
            
    # 3. Repair Captures Collection
    captures = await db['captures'].find({}).to_list(length=None)
    for cap in captures:
        cid = cap.get('char_id')
        if cid and cid.isdigit():
            normalized = str(int(cid))
            if normalized != cid:
                await db['captures'].update_one({"_id": cap["_id"]}, {"$set": {"char_id": normalized}})
                print(f"Normalized capture char_id: {cid} -> {normalized}")

    print("Canonicalization complete!")

if __name__ == "__main__":
    asyncio.run(repair_all())
