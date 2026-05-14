import asyncio
from bot.database.mongo import users_collection, characters_collection, captures_collection

# We need to fix capture.py to use the correct ID for caught_count
import codecs

with codecs.open("bot/modules/capture.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix the update_one to use the original active_char['id'] instead of normalized_id
old_code = """        await asyncio.gather(
            users_collection.update_one(
                {"id": user.id},
                {
                    "$set": {"name": user.first_name, "username": user.username},
                    "$push": {"waifus": normalized_id},
                    "$inc": {"coins": 100} # Award 100 coins for catching
                },
                upsert=True
            ),
            characters_collection.update_one(
                {"id": normalized_id},
                {"$inc": {"caught_count": 1}}
            ),
            captures_collection.insert_one({
                "user_id": user.id,
                "chat_id": chat_id,
                "char_id": normalized_id,
                "timestamp": update.message.date
            })
        )"""

# In capture_cmd, active_char is available. 
# We should use char_data['id'] which is the popped active_char
new_code = """        await asyncio.gather(
            users_collection.update_one(
                {"id": user.id},
                {
                    "$set": {"name": user.first_name, "username": user.username},
                    "$push": {"waifus": char_data['id']}, # Store exact ID
                    "$inc": {"coins": 100} # Award 100 coins for catching
                },
                upsert=True
            ),
            characters_collection.update_one(
                {"id": char_data['id']}, # Use exact ID from database
                {"$inc": {"caught_count": 1}}
            ),
            captures_collection.insert_one({
                "user_id": user.id,
                "chat_id": chat_id,
                "char_id": char_data['id'], # Use exact ID
                "timestamp": update.message.date
            })
        )"""

content = content.replace(old_code, new_code)

with codecs.open("bot/modules/capture.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed capture.py to use exact character IDs for database updates.")
