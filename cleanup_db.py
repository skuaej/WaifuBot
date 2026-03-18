import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

async def cleanup():
    if not MONGO_URI:
        print("MONGO_URI not found in .env")
        return

    client = AsyncIOMotorClient(MONGO_URI)
    # Most likely database name is 'waifu_bot' or 'test'
    db = client["waifu_bot"]
    
    print(f"Cleaning database: {db.name}")

    # 1. Drop characters collection
    await db.characters.drop()
    print("Dropped 'characters' collection.")

    # 2. Drop captures collection
    await db.captures.drop()
    print("Dropped 'captures' collection.")

    # 3. Clear users' waifus and favorites
    result = await db.users.update_many(
        {},
        {"$set": {"waifus": [], "favorite": None}}
    )
    print(f"Cleared 'waifus' and 'favorite' for {result.modified_count} users.")

    print("\nDatabase cleanup complete! 🧹")

if __name__ == "__main__":
    asyncio.run(cleanup())
