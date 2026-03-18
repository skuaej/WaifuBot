from bot.database.mongo import blocks_collection
import asyncio
import sys
import os

# Add parent directory to path to allow running as a script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def clear_all_blocks():
    print("🧹 Clearing all blocks from the database...")
    result = await blocks_collection.delete_many({})
    print(f"✅ Cleared {result.deleted_count} blocks.")

if __name__ == "__main__":
    asyncio.run(clear_all_blocks())
