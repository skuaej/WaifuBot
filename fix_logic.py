import codecs

with codecs.open("bot/modules/collection.py", "r", encoding="utf-8") as f:
    content = f.read()

old_check = """    char_id = char['id']
    rarity = char.get('rarity', 'Common')"""

new_check = """    char_id = char['id']
    norm_id = str(int(char_id)) if str(char_id).isdigit() else str(char_id)
    rarity = char.get('rarity', 'Common')"""

content = content.replace(old_check, new_check)

old_pipeline = """    # 1. Global Top 10
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

new_pipeline = """    # 1. Global Top 10
    global_pipeline = [
        {"$match": {"char_id": norm_id}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    global_results = await captures_collection.aggregate(global_pipeline).to_list(length=10)

    # 2. Local Chat Top 10
    chat_id = update.effective_chat.id
    local_pipeline = [
        {"$match": {"char_id": norm_id, "chat_id": chat_id}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    local_results = await captures_collection.aggregate(local_pipeline).to_list(length=10)
    
    # 3. Total Globally Caught Count (from users' harems)
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

content = content.replace(old_pipeline, new_pipeline)

old_text = """    # BUILD MESSAGE
    text = (
        f"OwO! Check out this character!\\n\\n"
        f"<b>{escape_markdown(char['anime'])}</b>\\n"
        f"{char['id']}: {escape_markdown(char['name'])}\\n"
        f"{stylized_rarity}\\n"
        f"{type_line}\\n"
    )"""

new_text = """    # BUILD MESSAGE
    text = (
        f"OwO! Check out this character!\\n\\n"
        f"<b>{escape_markdown(char['anime'])}</b>\\n"
        f"{char['id']}: {escape_markdown(char['name'])}\\n"
        f"{stylized_rarity}\\n"
        f"{type_line}\\n"
        f"🌐 <b>Globally Caught:</b> {total_global_caught} Times\\n\\n"
    )"""

content = content.replace(old_text, new_text)

# And add the hdelete command at the very end
hdelete_code = """

async def hdelete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    \"\"\"/hdelete ID1, ID2, or range like 1-6 - Let users delete characters from their own harem.\"\"\"
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("Usage: /hdelete <Character IDs> (comma separated or range like 1-6)")
        return

    user_data = await users_collection.find_one({"id": user.id})
    if not user_data or not user_data.get("waifus"):
        await update.message.reply_text("❌ You don't have any waifus to delete!")
        return

    owned_waifus = user_data["waifus"]
    normalized_owned = {str(int(wid)) if str(wid).isdigit() else str(wid) for wid in owned_waifus}
    
    raw_args = " ".join(context.args)
    parts = [p.strip() for p in raw_args.split(",")]
    
    actual_ids_to_delete = []
    
    for part in parts:
        if "-" in part:
            try:
                start_str, end_str = part.split("-")
                start = int(start_str)
                end = int(end_str)
                if end - start > 5000:
                    await update.message.reply_text("❌ Range too large. Max 5000 at a time.")
                    return
                for i in range(start, end + 1):
                    norm_val = str(i)
                    if norm_val in normalized_owned:
                        actual_ids_to_delete.append(norm_val)
            except ValueError:
                pass
        elif part.isdigit():
            norm_val = str(int(part))
            if norm_val in normalized_owned:
                actual_ids_to_delete.append(norm_val)
        else:
            if part in normalized_owned:
                actual_ids_to_delete.append(part)

    if not actual_ids_to_delete:
        await update.message.reply_text("❌ You don't own any characters matching the provided IDs.")
        return

    await users_collection.update_one(
        {"id": user.id},
        {"$pull": {"waifus": {"$in": actual_ids_to_delete}}}
    )
    
    fav_id = user_data.get("favorite")
    if fav_id:
        norm_fav = str(int(fav_id)) if str(fav_id).isdigit() else str(fav_id)
        if norm_fav in actual_ids_to_delete:
            await users_collection.update_one({"id": user.id}, {"$unset": {"favorite": ""}})
            
    await update.message.reply_text(f"✅ Successfully deleted {len(set(actual_ids_to_delete))} unique character(s) from your harem.")
"""

content = content + hdelete_code

with codecs.open("bot/modules/collection.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done!")
