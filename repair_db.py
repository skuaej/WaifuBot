import asyncio
from bot.database.mongo import users_collection, characters_collection

async def repair_stats():
    print("Starting database repair: Syncing caught_count for all characters...")
    
    # Fetch all users and their waifus
    users = await users_collection.find({}, {"waifus": 1}).to_list(length=None)
    
    from collections import Counter
    all_waifus = []
    for u in users:
        all_waifus.extend(u.get("waifus", []))
    
    counts = Counter(all_waifus)
    print(f"Counted {len(counts)} unique character IDs across all harems.")
    
    # Update characters_collection
    batch_size = 100
    ids = list(counts.keys())
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i+batch_size]
        for char_id in batch:
            count = counts[char_id]
            await characters_collection.update_one(
                {"id": char_id},
                {"$set": {"caught_count": count}}
            )
        print(f"Processed {min(i + batch_size, len(ids))}/{len(ids)} characters...")

    print("Database repair completed successfully!")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(repair_stats())
