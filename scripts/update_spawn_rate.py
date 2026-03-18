from bot.database.mongo import groups_collection
import asyncio
import sys
import os

# Add parent directory to path to allow running as a script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def update_all_spawn_rates():
    print("📈 Updating all group spawn targets to 70...")
    result = await groups_collection.update_many(
        {},
        {"$set": {"spawn_target": 70}}
    )
    print(f"✅ Updated {result.modified_count} groups.")

if __name__ == "__main__":
    asyncio.run(update_all_spawn_rates())
