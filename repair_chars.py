import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

async def get_next_char_id(db):
    """Find the highest numeric ID and return next."""
    cursor = db['characters'].find({"id": {"$regex": "^[0-9]+$"}}).sort("id", -1).limit(1)
    async for doc in cursor:
        try:
            return str(int(doc['id']) + 1)
        except:
            pass
    # Fallback if no numeric IDs exist
    count = await db['characters'].count_documents({})
    return str(count + 1)

async def repair():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client['waifu_bot']
    
    print("Starting character repair...")
    
    cursor = db['characters'].find({})
    repaired_all = 0
    async for char in cursor:
        updates = {}
        
        # 1. Fix missing/null rarity
        if not char.get('rarity'):
            updates['rarity'] = 'Common'
            print(f"Fixed rarity for: {char.get('name', 'Unknown')}")
            
        # 2. Fix missing/invalid ID
        if not char.get('id'):
            # This is slow but safe for 14 chars
            new_id = await get_next_char_id(db)
            updates['id'] = new_id
            # Temporarily insert to avoid duplicate IDs in loop if multiple missing
            await db['characters'].update_one({"_id": char["_id"]}, {"$set": {"id": new_id}})
            print(f"Assigned ID {new_id} to: {char.get('name', 'Unknown')}")
            
        # 3. Ensure ID is a string
        elif not isinstance(char.get('id'), str):
            updates['id'] = str(char['id'])
            print(f"Converted ID to string for: {char.get('name', 'Unknown')}")
            
        # 4. Fix missing anime
        if not char.get('anime'):
            updates['anime'] = 'Unknown'
            
        # 5. Fix missing file values
        if not char.get('file_id'):
            updates['file_id'] = 'MISSING'
        if not char.get('file_type'):
            updates['file_type'] = 'photo'
            
        if updates:
            await db['characters'].update_one({"_id": char["_id"]}, {"$set": updates})
            repaired_all += 1
            
    print(f"Repair complete! Total characters repaired: {repaired_all}")

if __name__ == "__main__":
    asyncio.run(repair())
