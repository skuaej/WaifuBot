import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def check():
    uri = os.getenv('MONGO_URI')
    print(f"Connecting to: {uri}")
    client = AsyncIOMotorClient(uri)
    db = client['waifu_bot']
    
    c_count = await db.characters.count_documents({})
    u_count = await db.users.count_documents({})
    
    print(f"Total Characters: {c_count}")
    print(f"Total Users: {u_count}")
    
    # Check for ID 9 specifically
    char_9 = await db.characters.find_one({'id': '9'})
    print(f"ID '9' found: {char_9 is not None}")
    if char_9:
        print(f"Name for ID 9: {char_9.get('name')}")
    
    # Check for any padded IDs
    cursor = db.characters.find({'id': {'$regex': '^0+'}})
    padded_ids = []
    async for char in cursor:
        padded_ids.append(char['id'])
    
    print(f"Padded IDs found: {len(padded_ids)}")
    if padded_ids:
        print(f"Sample padded IDs: {padded_ids[:5]}")
        
    # Check if there's any user with ID or first_name
    sample_user = await db.users.find_one({})
    print(f"Sample User: {sample_user}")

if __name__ == '__main__':
    asyncio.run(check())
