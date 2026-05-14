import codecs
import re

with codecs.open("bot/modules/collection.py", "r", encoding="utf-8") as f:
    content = f.read()

# Helper to replace literal emojis with unicode escapes
def replace_emojis(text):
    # Mapping of common emojis to their unicode escapes
    emoji_to_escape = {
        '🔵': '\\U0001f535',
        '🟣': '\\U0001f7e3',
        '🟠': '\\U0001f7e0',
        '🟡': '\\U0001f7e1',
        '💮': '\\U0001f4ae',
        '⚜️': '\\u269c\\ufe0f',
        '⚡': '\\u26a1',
        '🪞': '\\U0001fa9e',
        '✨': '\\u2728',
        '❌': '\\u274c',
        '☘️': '\\u2618\\ufe0f',
        '🆔': '\\U0001f194',
        '⬅️': '\\u2b05\\ufe0f',
        '➡️': '\\u27a1\\ufe0f',
        '⛩': '\\u26e9',
        '💖': '\\U0001f496',
        '🌎': '\\U0001f30e',
        '🎖️': '\\U0001f396\\ufe0f',
        '➥': '\\u27a5',
        '⚠️': '\\u26a0\\ufe0f',
        '🎁': '\\U0001f381',
        '🏷️': '\\U0001f3f7\\ufe0f',
        '🫧': '\\U0001fae7',
        '⏳': '\\u23f3',
        '👉': '\\ud83d\\udc49',
        '🚀': '\\ud83d\\ude80'
    }
    
    for emoji, escape in emoji_to_escape.items():
        text = text.replace(emoji, escape)
    return text

# Apply emoji replacements globally in the file content
# This might catch literal emojis in comments too, which is fine
content = replace_emojis(content)

# Fix /check logic (if not already fixed by previous run)
old_block = """    char_id = char['id']
    rarity = char.get('rarity', 'Common')
    from bot.utils.formatters import get_stylized_rarity
    stylized_rarity = get_stylized_rarity(rarity)
    
    # 1. Global Top 10
    global_pipeline = [
        {"$match": {"char_id": char_id}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    global_results = await captures_collection.aggregate(global_pipeline).to_list(length=10)

    # 2. Local Chat Top 10
    chat_id = update.effective_chat.id
    local_pipeline = [
        {"$match": {"char_id": char_id, "chat_id": chat_id}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    local_results = await captures_collection.aggregate(local_pipeline).to_list(length=10)"""

if old_block in content:
    new_block = """    char_id = char['id']
    # Normalize ID for robust matching in captures and users collections
    norm_id = str(int(char_id)) if char_id.isdigit() else char_id
    
    rarity = char.get('rarity', 'Common')
    from bot.utils.formatters import get_stylized_rarity
    stylized_rarity = get_stylized_rarity(rarity)
    
    # 1. Global Top 10 (Using normalized ID)
    global_pipeline = [
        {"$match": {"char_id": norm_id}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    global_results = await captures_collection.aggregate(global_pipeline).to_list(length=10)

    # 2. Local Chat Top 10 (Using normalized ID)
    chat_id = update.effective_chat.id
    local_pipeline = [
        {"$match": {"char_id": norm_id, "chat_id": chat_id}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    local_results = await captures_collection.aggregate(local_pipeline).to_list(length=10)
    
    # 3. Total Globally Caught Count (from users' harems for accuracy)
    # This counts every single instance of this character in anyone's collection
    user_pipeline = [
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
    users_with_char = await users_collection.aggregate(user_pipeline).to_list(length=None)
    total_global_caught = sum(u.get('count', 0) for u in users_with_char)"""

    content = content.replace(old_block, new_block)

    # Update the message text construction
    old_text_init = """    # BUILD MESSAGE
    text = (
        f"OwO! Check out this character!\\n\\n"
        f"<b>{escape_markdown(char['anime'])}</b>\\n"
        f"{char['id']}: {escape_markdown(char['name'])}\\n"
        f"{stylized_rarity}\\n"
        f"{type_line}\\n"
    )"""

    new_text_init = """    # BUILD MESSAGE
    # Use Unicode escape sequences for emojis to avoid encoding issues
    globe_emoji = "\\U0001f310" # 🌐
    text = (
        f"OwO! Check out this character!\\n\\n"
        f"<b>{escape_markdown(char['anime'])}</b>\\n"
        f"{char['id']}: {escape_markdown(char['name'])}\\n"
        f"{stylized_rarity}\\n"
        f"{type_line}\\n"
        f"{globe_emoji} <b>Globally Caught:</b> {total_global_caught} Times\\n\\n"
    )"""

    content = content.replace(old_text_init, new_text_init)

with codecs.open("bot/modules/collection.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated collection.py with comprehensive fixes and Unicode escape emojis.")
