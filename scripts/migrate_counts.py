import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import sys
import os

# Add the project root to sys.path to import bot modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot.config import MONGO_URI
from bot.database.mongo import db, characters_collection, users_collection

async def migrate_caught_counts():
    print("🚀 Starting caught_count migration...")
    
    # 1. Clear existing caught_count (optional, but good for a fresh start)
    await characters_collection.update_many({}, {"$set": {"caught_count": 0}})
    
    # 2. Aggregate all waifus from all users
    # This might take time depending on DB size
    pipeline = [
        {"$project": {"waifus": 1}},
        {"$unwind": "$waifus"},
        {"$group": {"_id": "$waifus", "total": {"$sum": 1}}}
    ]
    
    count = 0
    async for stat in users_collection.aggregate(pipeline, allowDiskUse=True):
        char_id = str(stat["_id"])
        total = stat["total"]
        
        # Update character with its count
        # Handle both string and numeric IDs if they exist
        res = await characters_collection.update_one(
            {"id": char_id},
            {"$set": {"caught_count": total}}
        )
        if res.matched_count == 0 and char_id.isdigit():
             await characters_collection.update_one(
                {"id": int(char_id)},
                {"$set": {"caught_count": total}}
            )
            
        count += 1
        if count % 100 == 0:
            print(f"Processed {count} characters...")

    print(f"✅ Migration complete! {count} characters updated.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(migrate_caught_counts())
