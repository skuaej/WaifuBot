import codecs
import re

with codecs.open("bot/modules/collection.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Define the correct check_cmd function
# I will find the range of the current check_cmd and replace it entirely
start_search = "async def check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):"
end_search = "async def hclaim_cmd"

start_index = content.find(start_search)
end_index = content.find(end_search)

if start_index != -1 and end_index != -1:
    new_check_cmd = """async def check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    \"\"\"/check <id or name> for detailed character stats and top owners.\"\"\"
    if not context.args:
        await update.message.reply_text("Usage: /check <character id or name>")
        return
        
    query = " ".join(context.args).strip()
    
    # Robust ID lookup first
    char = None
    if query.isdigit():
        norm_id = str(int(query))
        regex = re.compile(f"^0*{norm_id}$")
        char = await characters_collection.find_one({"id": regex})
    else:
        char = await characters_collection.find_one({"id": query})
        
    if not char:
        # Fallback to name search
        regex = re.compile(f"^{re.escape(query)}$", re.IGNORECASE)
        char = await characters_collection.find_one({"name": regex})
        
    if not char:
        await update.message.reply_text(f"\\u274c Character not found.")
        return
        
    char_id = char['id']
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
    total_global_caught = sum(u.get('count', 0) for u in users_with_char)
    
    # Handle Type (optional)
    char_type = char.get('type')
    type_line = ""
    if char_type:
        match = re.search(r"\[(\W+)\]", char['name'])
        t_emoji = match.group(1) if match else "\\U0001f4a0"
        type_line = f"\\n{t_emoji}<b><i>{char_type}</i></b>{t_emoji}\\n"

    # BUILD MESSAGE
    globe_emoji = "\\U0001f310" # 🌐
    text = (
        f"OwO! Check out this character!\\n\\n"
        f"<b>{escape_markdown(char['anime'])}</b>\\n"
        f"{char['id']}: {escape_markdown(char['name'])}\\n"
        f"{stylized_rarity}\\n"
        f"{type_line}\\n"
        f"{globe_emoji} <b>Globally Caught:</b> {total_global_caught} Times\\n\\n"
    )

    # Global Top 10 Section
    if global_results:
        text += "\\U0001f30e <b>ɢʟᴏʙᴀʟʟʏ ᴛᴏᴘ 10 ᴄᴀᴛᴄʜᴇʀs</b>\\n"
        for entry in global_results:
            uid = entry["_id"]
            count = entry["count"]
            user_data = await users_collection.find_one({"id": uid})
            if not user_data:
                user_data = await users_collection.find_one({"id": str(uid)})
            
            uname = escape_markdown(user_data.get('name') or user_data.get('first_name') or 'Unknown')
            text += f"\\u27a5 <a href='tg://user?id={uid}'>{uname}</a> (<code>{uid}</code>) x{count}\\n"
        text += "\\n"

    # Local Top 10 Section
    if local_results:
        text += f"\\U0001f396\\ufe0f ᴛᴏᴘ 10 ᴄᴀᴛᴄʜᴇʀs ᴏғ ᴛʜɪs ᴄʜᴀʀᴀᴄᴛᴇʀ ɪɴ ᴛʜɪs ᴄʜᴀᴛ\\n"
        for entry in local_results:
            uid = entry["_id"]
            count = entry["count"]
            user_data = await users_collection.find_one({"id": uid})
            if not user_data:
                user_data = await users_collection.find_one({"id": str(uid)})
            
            uname = escape_markdown(user_data.get('name') or user_data.get('first_name') or 'Unknown')
            text += f"\\u27a5 <a href='tg://user?id={uid}'>{uname}</a> (<code>{uid}</code>) x{count}\\n"
        
    try:
        file_type = char.get('file_type', 'photo')
        if file_type == 'video':
            await update.message.reply_video(video=char['file_id'], caption=text, parse_mode="HTML")
        elif file_type == 'document':
            await update.message.reply_document(document=char['file_id'], caption=text, parse_mode="HTML")
        else:
            await update.message.reply_photo(photo=char['file_id'], caption=text, parse_mode="HTML")
    except Exception as e:
        # Fallback to text-only if file_id is invalid (common after switching bots)
        await update.message.reply_text(
            text + f"\\n\\n\\u26a0\\ufe0f <b>Media Error:</b> The file ID for this character is invalid for the current bot. Please re-upload this character.",
            parse_mode="HTML"
        )

"""
    content = content[:start_index] + new_check_cmd + "\n\n" + content[end_index:]
    
    with codecs.open("bot/modules/collection.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Successfully updated check_cmd with normalized IDs and Globally Caught counter.")
else:
    print("Could not find start or end of check_cmd function.")
