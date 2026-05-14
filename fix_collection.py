import re

with open("bot/modules/collection.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix emojis I messed up
replacements = {
    "ðŸŒ ": "🌐",
    "ðŸ’ ": "💫",
    "âš ï¸ ": "⚠️",
    "ðŸŽ–ï¸ ": "🏅",
    "á´›á´ á´˜ 10 á´„á´€á´›á´„Êœá´‡Ê€s á´ Ò“ á´›ÊœÉªs á´„Êœá´€Ê€á´€á´„á´›á´‡Ê€ ÉªÉ´ á´›ÊœÉªs á´„Êœá´€á´›": "TOP 10 CATCHERS IN THIS CHAT",
    "É¢ÊŸá´ Ê™á´€ÊŸÊŸÊ  á´›á´ á´˜ 10 á´„á´€á´›á´„Êœá´‡Ê€s": "GLOBALLY TOP 10 CATCHERS",
    "âž¥": "➥",
    "ðŸ”µ": "🔵",
    "ðŸŸ£": "🟣",
    "ðŸŸ ": "🟠",
    "ðŸŸ¡": "🟡",
    "ðŸ’®": "💮",
    "âšœï¸ ": "⚜️",
    "âš¡": "⚡",
    "ðŸªž": "🪞",
    "âœ✨": "✨",
    "â˜˜ï¸ ": "🌿",
    "ðŸ†”": "🆔",
    "â Œ": "❌",
    "ðŸ‘‰": "👉",
    "ðŸš€": "🚀",
    "ðŸŽ ": "🎁",
    "ðŸ ·ï¸ ": "🏷️",
    "ðŸ«§": "🫧",
    "â ³": "⏳",
    "ðŸ †": "🏆",
    "ðŸ“ ": "📊"
}

for k, v in replacements.items():
    content = content.replace(k, v)

# Update check_cmd to use users_collection for total_global_caught
old_check = """    # 3. Total Globally Caught Count
    total_global_caught = await captures_collection.count_documents({"char_id": norm_id})"""

new_check = """    # 3. Total Globally Caught Count (from users' harems)
    pipeline = [
        {"$match": {"waifus": {"$in": [norm_id, char_id]}}},
        {"$project": {
            "count": {
                "$size": {
                    "$filter": {
                        "input": {"$ifNull": ["$waifus", []]},
                        "as": "w",
                        "cond": {"$in": ["$$w", [norm_id, char_id]]}
                    }
                }
            }
        }}
    ]
    users_with_char = await users_collection.aggregate(pipeline).to_list(length=None)
    total_global_caught = sum(u.get('count', 0) for u in users_with_char)"""

content = content.replace(old_check, new_check)

with open("bot/modules/collection.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed!")
