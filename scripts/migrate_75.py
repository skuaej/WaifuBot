from bot.database.mongo import groups_collection
import asyncio
import sys
import os

# Add parent directory to path to allow running as a script
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

async def migrate_to_75():
    """Migrate all groups to the new default spawn target of 75."""
    print("🚀 Starting migration of group spawn targets to 75...")
    result = await groups_collection.update_many(
        {"spawn_target": {"$in": [70, None, 0]}}, # Update if 70, None, or 0
        {"$set": {"spawn_target": 75}}
    )
    print(f"✅ Migration complete! Updated {result.modified_count} groups to target 75.")

if __name__ == "__main__":
    asyncio.run(migrate_to_75())
