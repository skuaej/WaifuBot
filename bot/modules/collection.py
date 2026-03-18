from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.mongo import users_collection, characters_collection, captures_collection
from bot.utils.formatters import escape_markdown
import re
import random
import math

async def get_harem_page(user_id: int, page: int, target_user_name: str) -> tuple:
    user_data = await users_collection.find_one({"id": user_id})
    if not user_data or not user_data.get("waifus"):
        return "❌ You haven't caught any waifus yet!", None, None

    waifu_ids = user_data["waifus"]
    hmode = user_data.get("hmode", "Default")
    
    # Normalize all IDs for counting and display
    normalized_waifu_ids = [str(int(wid)) if wid.isdigit() else wid for wid in waifu_ids]
    
    from collections import Counter
    counts = Counter(normalized_waifu_ids)
    # Unique normalized IDs owned by the user
    normalized_owned_ids = list(counts.keys())
    
    # Fetch character data
    cursor = characters_collection.find({"id": {"$in": normalized_owned_ids}})
    char_map = {}
    async for char in cursor:
        char_map[char["id"]] = char
        
    # Ensure they exist in database
    normalized_owned_ids = [wid for wid in normalized_owned_ids if wid in char_map]
            
    emoji_map = {
        "Common": "🔵", "Uncommon": "🟣", "Rare": "🟠", 
        "Legendary": "🟡", "Mystical": "💮", "Divine": "⚜️",
        "Crossverse": "⚡", "Supreme": "🤍", "Cataphract": "✨"
    }

    # Filter based on hmode if it's a specific rarity
    if hmode in emoji_map:
        normalized_owned_ids = [wid for wid in normalized_owned_ids if char_map[wid].get("rarity", "Common") == hmode]
    
    if not normalized_owned_ids:
        return f"❌ You don't have any characters matching the selected rarity filter ({hmode}).", None, None

    # Sort characters: first by anime, then by ID
    normalized_owned_ids.sort(key=lambda x: (char_map[x]['anime'], int(x) if x.isdigit() else x))
    
    ITEMS_PER_PAGE = 10
    total_items = len(normalized_owned_ids)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    if page < 1: page = 1
    if page > total_pages: page = total_pages
    
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_ids = normalized_owned_ids[start_idx:end_idx]
    
    # Group page characters by anime for display
    text = f"<b>{escape_markdown(target_user_name)}</b>'s Recent Waifus - Page: {page}/{total_pages}\n"
    
    for wid in page_ids:
        char = char_map[wid]
        r_emoji = emoji_map.get(char.get('rarity', 'Common'), '💮')
        char_count = counts.get(wid, 1)
        
        # Find total collected in this anime
        collected_in_anime = len([x for x in normalized_owned_ids if char_map[x]['anime'] == char['anime']])
        # Find total existing in this anime
        total_in_db = await characters_collection.count_documents({"anime": char['anime']})
        
        text += (
            f"\n☘️ <b>Name:</b> {escape_markdown(char['name'])} (x{char_count})\n"
            f"🆔 <b>ID:</b> <code>{char['id']}</code>\n"
            f"{r_emoji} <b>Rarity:</b> {char.get('rarity', 'Common')}\n"
            f"⚜️ <b>Anime:</b> {escape_markdown(char['anime'])} ({collected_in_anime}/{total_in_db})\n"
        )

    # Grab Display Image
    fav_id = user_data.get("favorite")
    if fav_id:
        fav_norm = str(int(fav_id)) if fav_id.isdigit() else fav_id
    else:
        fav_norm = None
        
    if fav_norm and fav_norm in char_map:
        display_char = char_map[fav_norm]
    elif page_ids:
        display_char = char_map[random.choice(page_ids)]
    else:
        display_char = char_map[random.choice(normalized_owned_ids)]

    # Inline Keyboard for pagination
    keyboard = []
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Back", callback_data=f"harem_page_{user_id}_{page-1}"))
    
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"harem_page_{user_id}_{page+1}"))
    
    if nav_row:
        keyboard.append(nav_row)
        
    keyboard.append([InlineKeyboardButton(f"⛩ CHARACTERS ({total_items})", switch_inline_query_current_chat=f"harem.{user_id} ")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    return text, display_char, reply_markup

async def harem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows user's collected waifus."""
    user = update.effective_user
    text, display_char, reply_markup = await get_harem_page(user.id, 1, user.first_name)
    
    if display_char is None:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
        return

    file_type = display_char.get('file_type', 'photo')
    if file_type == 'video':
        await update.message.reply_video(video=display_char['file_id'], caption=text, parse_mode="HTML", reply_markup=reply_markup)
    elif file_type == 'document':
        await update.message.reply_document(document=display_char['file_id'], caption=text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.message.reply_photo(photo=display_char['file_id'], caption=text, parse_mode="HTML", reply_markup=reply_markup)

async def collection_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pagination and hmode clicks."""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    if data == "ignore" or data == "harem_page_ignore":
        await query.answer()
        return

    if data.startswith("hmode_"):
        mode = data.split("_")[1]
        
        if mode == "close":
            await query.message.delete()
            return
            
        await users_collection.update_one({"id": user_id}, {"$set": {"hmode": mode}}, upsert=True)
        await query.answer(f"Harem mode set to: {mode}")
        await query.edit_message_text(f"❄️ CHOOSE YOUR PREFFERED RARITY\n\n✅ Updated to: {mode}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ CLOSE", callback_data="hmode_close")]]))
        return

    if data.startswith("harem_page_"):
        parts = data.split("_")
        if len(parts) < 4:
            await query.answer("❌ Invalid callback data.", show_alert=True)
            return
            
        target_id = int(parts[2])
        page = int(parts[3])
        
        if user_id != target_id:
            await query.answer("❌ This is not your harem!", show_alert=True)
            return
            
            
        text, display_char, reply_markup = await get_harem_page(target_id, page, query.from_user.first_name)
        if text.startswith("❌"):
            await query.answer(text, show_alert=True)
            return

        file_type = display_char.get('file_type', 'photo') if display_char else 'photo'
        file_id = display_char.get('file_id') if display_char else None

        from telegram import InputMediaPhoto, InputMediaVideo, InputMediaDocument
        
        try:
            if file_id:
                if file_type == 'video':
                    media = InputMediaVideo(media=file_id, caption=text, parse_mode="HTML")
                elif file_type == 'document':
                    media = InputMediaDocument(media=file_id, caption=text, parse_mode="HTML")
                else:
                    media = InputMediaPhoto(media=file_id, caption=text, parse_mode="HTML")
                
                await query.edit_message_media(media=media, reply_markup=reply_markup)
            else:
                await query.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception as e:
            print(f"Error in harem callback: {e}")
            await query.answer("❌ Error updating harem page.", show_alert=True)
            pass

        await query.answer()

async def hmode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Interactive /hmode to change sorting/filtering."""
    keyboard = [
        [InlineKeyboardButton("🐉 Default", callback_data="hmode_Default"), InlineKeyboardButton("Detailed 🦖", callback_data="hmode_Detailed")],
        [InlineKeyboardButton("🦕 Reset Preference", callback_data="hmode_Default")],
        [InlineKeyboardButton("🤍 RARITY: Supreme", callback_data="hmode_Supreme")],
        [InlineKeyboardButton("✨ RARITY: Cataphract", callback_data="hmode_Cataphract")],
        [InlineKeyboardButton("⚡ RARITY: Crossverse", callback_data="hmode_Crossverse")],
        [InlineKeyboardButton("⚜️ RARITY: Divine", callback_data="hmode_Divine")],
        [InlineKeyboardButton("💮 RARITY: Mystical", callback_data="hmode_Mystical")],
        [InlineKeyboardButton("🟡 RARITY: Legendary", callback_data="hmode_Legendary")],
        [InlineKeyboardButton("🟠 RARITY: Rare", callback_data="hmode_Rare")],
        [InlineKeyboardButton("🟣 RARITY: Uncommon", callback_data="hmode_Uncommon")],
        [InlineKeyboardButton("🔵 RARITY: Common", callback_data="hmode_Common")],
        [InlineKeyboardButton("🗑️ CLOSE", callback_data="hmode_close")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("❄️ CHOOSE YOUR PREFFERED RARITY", reply_markup=reply_markup)

async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/profile - To view your harem profile"""
    user = update.effective_user
    user_data = await users_collection.find_one({"id": user.id})
    waifus = user_data.get("waifus", []) if user_data else []
        
    total_characters = len(waifus)
    total_distinct = len(set(waifus))
    max_characters = await characters_collection.count_documents({})
    if max_characters == 0: max_characters = 1
    
    rarities = {"Cataphract": 0, "Supreme": 0, "Crossverse": 0, "Divine": 0, "Mystical": 0, "Legendary": 0, "Rare": 0, "Uncommon": 0, "Common": 0}
    if waifus:
        # Normalize IDs for count
        norm_waifus = [str(int(wid)) if wid.isdigit() else wid for wid in waifus]
        cursor = characters_collection.find({"id": {"$in": norm_waifus}})
        async for c in cursor:
            r = c.get('rarity', 'Common')
            if r in rarities:
                # Count occurrences based on the user's waifus list
                cid = c['id']
                rarities[r] += norm_waifus.count(cid)
    
    # Local Rank (captures in this chat)
    from bot.database.mongo import captures_collection
    from bot.utils.spam import get_block_remaining
    chat_id = update.effective_chat.id
    
    # Block status
    remaining = await get_block_remaining(user.id)
    block_status = "🛡️ <b>Block Status:</b> Active"
    if remaining > 0:
        block_status = f"🛡️ <b>Block Status:</b> BLOCKED ({remaining // 60}m {remaining % 60}s)"

    # Global Rank (by total waifus)
    global_rank_pipeline = [
        {"$project": {"count": {"$size": {"$ifNull": ["$waifus", []]}}}},
        {"$sort": {"count": -1}}
    ]
    global_rank = 0
    g_idx = 1
    if user_data:
        async for u in users_collection.aggregate(global_rank_pipeline):
            if u["_id"] == user_data["_id"]:
                global_rank = g_idx
                break
            g_idx += 1
        
    # Local Rank (captures in this chat)
    local_rank_pipeline = [
        {"$match": {"chat_id": chat_id}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    local_rank = 0
    l_idx = 1
    async for entry in captures_collection.aggregate(local_rank_pipeline):
        if entry["_id"] == user.id:
            local_rank = l_idx
            break
        l_idx += 1
 
    h_percent = (float(total_distinct) / float(max_characters)) * 100.0 if max_characters > 0 else 0
    text = (
        "  ╭──「 🎗️ Cᴀᴛᴄʜᴇʀ Pʀᴏғɪʟᴇ 🎗 」\n"
        f"├─➩ 👤 ᴜsᴇʀ: <a href='tg://user?id={user.id}'>{escape_markdown(user.first_name)}</a>\n"
        f"├─➩ 🔩 ᴜsᴇʀ ɪᴅ: <code>{user.id}</code>\n"
        f"├─➩ ⚡ ᴛᴏᴛᴀʟ ᴄʜᴀʀᴀᴄᴛᴇʀ: {total_characters} ({total_distinct})\n"
        f"├─➩ 🫧 ʜᴀʀᴇᴍ: {total_distinct}/{max_characters} ({h_percent:.3f}%)\n"
        f"├─➩ {block_status}\n"
        "╭───────────────────\n"
        f"├─➩ 🔵 𝙍𝘼𝙍𝙄𝙏𝙔: Common: {rarities['Common']}\n"
        f"├─➩ 🟣 𝙍𝘼𝙍𝙄𝙏𝙔: Uncommon: {rarities['Uncommon']}\n"
        f"├─➩ 🟠 𝙍𝘼𝙍𝙄𝙏𝙔: Rare: {rarities['Rare']}\n"
        f"├─➩ 🟡 𝙍𝘼𝙍𝙄𝙏𝙔: Legendary: {rarities['Legendary']}\n"
        f"├─➩ 💮 𝙍𝘼𝙍𝙄𝙏𝙔: Mystical: {rarities['Mystical']}\n"
        f"├─➩ ⚜️ 𝙍𝘼𝙍𝙄ᴛʏ: Divine: {rarities['Divine']}\n"
        f"├─➩ 💮 𝙍𝘼𝙍𝙄𝙏𝙔: Crossverse: {rarities['Crossverse']}\n"
        f"├─➩ 💮 𝙍𝘼𝙍𝙄𝙏𝙔: Supreme: {rarities['Supreme']}\n"
        f"├─➩ 💮 𝙍𝘼𝙍𝙄𝙏ʏ: Cataphract: {rarities['Cataphract']}\n"
        "╭───────────────────\n"
        f"├─➩ 🏆 Gʟᴏʙᴀʟ Rᴀɴᴋ: {global_rank if global_rank > 0 else 'N/A'}\n"
        f"├─➩ 📍 Cʜᴀᴛ Rᴀɴᴋ: {local_rank if local_rank > 0 else 'N/A'}\n"
        "╰───────────────────"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global Leaderboard based on total waifus (as requested)."""
    user_pipeline = [
        {"$project": {
            "name": 1,
            "id": 1,
            "waifu_count": {"$size": {"$ifNull": ["$waifus", []]}}
        }},
        {"$sort": {"waifu_count": -1}},
        {"$limit": 10}
    ]
    user_cursor = users_collection.aggregate(user_pipeline)
    
    text = "🏆 <b>Global User Leaderboard</b> 🏆\n\n"
    idx = 1
    async for u in user_cursor:
        user_id = u.get('id', 'Unknown')
        user_name = escape_markdown(u.get('name', 'Unknown'))
        name_mention = f"<a href='tg://user?id={user_id}'>{user_name}</a>"
        count = u.get('waifu_count', 0)
        text += f"<b>{idx}.</b> {name_mention} (ID: <code>{user_id}</code>) — {count} waifus\n"
        idx += 1

    await update.message.reply_text(text, parse_mode="HTML")

async def gtop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global Character Leaderboard with Top Catcher (as requested)."""
    # 1. Get Top 10 Characters by capture count
    char_pipeline = [
        {"$group": {"_id": "$char_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    char_cursor = captures_collection.aggregate(char_pipeline)
    
    text = "🌟 <b>Top Captured Characters Globally</b> 🌟\n\n"
    c_idx = 1
    async for c in char_cursor:
        char_id = c["_id"]
        char_data = await characters_collection.find_one({"id": char_id})
        if not char_data:
            char_data = await characters_collection.find_one({"id": str(int(char_id)) if char_id.isdigit() else char_id})
            if not char_data: continue

        # 2. Find the Top Catcher for this character
        user_win_pipeline = [
            {"$match": {"char_id": char_id}},
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 1}
        ]
        user_win_cursor = captures_collection.aggregate(user_win_pipeline)
        top_user_text = "<i>N/A</i>"
        async for uw in user_win_cursor:
            u_id = uw["_id"]
            u_data = await users_collection.find_one({"id": u_id})
            u_name_val = u_data.get('name', 'Unknown') if u_data else "Unknown"
            u_mention = f"<a href='tg://user?id={u_id}'>{escape_markdown(u_name_val)}</a>"
            top_user_text = f"{u_mention} (ID: <code>{u_id}</code>) x{uw['count']}"
        
        text += f"<b>{c_idx}.</b> {escape_markdown(char_data['name'])} (ID: <code>{char_id}</code>) — {c['count']} grabs\n"
        text += f"   ﹂ 🏆 Top Catcher: {top_user_text}\n\n"
        c_idx += 1

    await update.message.reply_text(text, parse_mode="HTML")

async def fav_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/fav <ID> to set favorite waifu."""
    if not context.args:
        await update.message.reply_text("Usage: /fav <Character ID>")
        return

    # Normalize input ID
    input_id = context.args[0]
    norm_input = str(int(input_id)) if input_id.isdigit() else input_id
    
    user = update.effective_user
    user_data = await users_collection.find_one({"id": user.id})

    if not user_data or not user_data.get("waifus"):
        await update.message.reply_text("❌ You don't have any waifus!")
        return

    # Normalize all owned IDs for checking
    waifus_list = user_data["waifus"]
    normalized_owned = {str(int(wid)) if wid.isdigit() else wid for wid in waifus_list}
    
    if norm_input not in normalized_owned:
        await update.message.reply_text(f"❌ You don't own waifu ID {input_id}!")
        return
        
    # Robust search by ID (padded or not)
    if input_id.isdigit():
        norm_id = str(int(input_id))
        regex = re.compile(f"^0*{norm_id}$")
        char_data = await characters_collection.find_one({"id": regex})
    else:
        char_data = await characters_collection.find_one({"id": input_id})
        
    if not char_data:
        await update.message.reply_text(f"❌ Character ID {input_id} not found in database.")
        return
        
    actual_id = char_data['id']
    await users_collection.update_one({"id": user.id}, {"$set": {"favorite": actual_id}})
    await update.message.reply_text(f"💖 Successfully set <b>{escape_markdown(char_data['name'])}</b> as your favorite!", parse_mode="HTML")

async def check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/check <id or name> for detailed character stats and top owners."""
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
        await update.message.reply_text(f"❌ Character not found.")
        return
        
    char_id = char['id']
    rarity = char.get('rarity', 'Common')
    emoji_map = {
        "Common": "🔵", "Uncommon": "🟣", "Rare": "🟠", 
        "Legendary": "🟡", "Mystical": "💮", "Divine": "⚜️",
        "Crossverse": "💮", "Supreme": "💮", "Cataphract": "💮"
    }
    r_emoji = emoji_map.get(rarity, "💮")
    
    # Aggregate users who have this waifu to find top catchers and global count
    pipeline = [
        {"$match": {"waifus": char_id}},
        {"$project": {
            "name": 1,
            "id": 1,
            "count": {
                "$size": {
                    "$filter": {
                        "input": "$waifus",
                        "cond": {"$eq": ["$$this", char_id]}
                    }
                }
            }
        }},
        {"$facet": {
            "total": [{"$group": {"_id": None, "total": {"$sum": "$count"}}}],
            "top_10": [{"$sort": {"count": -1}}, {"$limit": 10}]
        }}
    ]
    
    results = await users_collection.aggregate(pipeline).to_list(length=1)
    
    global_total = 0
    top_catchers = []
    
    if results and len(results) > 0:
        facet_data = results[0]
        if facet_data.get("total") and len(facet_data["total"]) > 0:
            global_total = facet_data["total"][0]["total"]
            
        top_catchers = facet_data.get("top_10", [])
        
    text = (
        f"<b>Character Information</b>\n"
        f"Message: OwO! Check out this character!\n\n"
        f"<b>Series:</b> {escape_markdown(char['anime'])}\n\n"
        f"<b>ID & Name:</b> {char['id']}: {escape_markdown(char['name'])} [💠]\n\n"
        f"<b>Rarity:</b> ({r_emoji} <b>RARITY:</b> {rarity})\n\n"
        f"<b>Global Stats</b>\n"
        f"Caught Globally: {global_total} TIMES\n\n"
        f"<b>Top 10 Catchers</b>\n"
        f"🏅 <b>TOP 10 CATCHERS OF THIS CHARACTER!</b>\n\n"
    )
    
    if len(top_catchers) > 0:
        for u in top_catchers:
            uname = escape_markdown(u.get('name', 'Unknown'))
            uid = u.get('id', 'Unknown')
            ucount = u.get('count', 0)
            text += f"➥ <a href='tg://user?id={uid}'>{uname}</a> (<code>{uid}</code>) x{ucount}\n\n"
    else:
        text += "<i>Nobody has caught this character yet.</i>"
        
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
            text + "\n\n⚠️ <b>Media Error:</b> The file ID for this character is invalid for the current bot. Please re-upload this character.",
            parse_mode="HTML"
        )


async def hclaim_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/hclaim - Claim a random character from Common/Uncommon/Rare/Legendary."""
    import time
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Cooldown check (1 claim per 24 hours per user)
    user_data = await users_collection.find_one({"id": user.id})
    if user_data:
        last_claim = user_data.get("last_hclaim", 0)
        now = time.time()
        if now - last_claim < 86400:
            remaining = int(86400 - (now - last_claim))
            hours = remaining // 3600
            mins = (remaining % 3600) // 60
            await update.message.reply_text(f"⏳ You can claim again in {hours}h {mins}m.")
            return

    # Pick a random character from claimable rarities
    claimable_rarities = ["Common", "Uncommon", "Rare", "Legendary"]
    pipeline = [
        {"$match": {"rarity": {"$in": claimable_rarities}}},
        {"$sample": {"size": 1}}
    ]
    results = await characters_collection.aggregate(pipeline).to_list(length=1)

    if not results:
        await update.message.reply_text("❌ No claimable characters found in the database.")
        return

    char = results[0]
    char_id = char['id']
    normalized_id = str(int(char_id)) if char_id.isdigit() else char_id

    # Add to user's harem
    await users_collection.update_one(
        {"id": user.id},
        {
            "$set": {"name": user.first_name, "username": user.username, "last_hclaim": time.time()},
            "$push": {"waifus": normalized_id}
        },
        upsert=True
    )

    await captures_collection.insert_one({
        "user_id": user.id,
        "chat_id": chat_id,
        "char_id": normalized_id,
        "timestamp": update.message.date
    })

    emoji_map = {
        "Common": "🔵", "Uncommon": "🟣", "Rare": "🟠",
        "Legendary": "🟡", "Mystical": "💮", "Divine": "⚜️",
        "Crossverse": "⚡", "Supreme": "🤍", "Cataphract": "✨"
    }
    r_emoji = emoji_map.get(char.get('rarity', 'Common'), '💮')

    text = (
        f"🎁 <b>Harem Claim!</b>\n\n"
        f"<a href='tg://user?id={user.id}'>{escape_markdown(user.first_name)}</a> claimed:\n\n"
        f"🏷️ <b>{escape_markdown(char['name'])}</b>\n"
        f"🫧 Anime: {escape_markdown(char.get('anime', 'Unknown'))}\n"
        f"{r_emoji} Rarity: {char.get('rarity', 'Common')}\n"
        f"🆔 ID: {char_id}"
    )

    file_type = char.get('file_type', 'photo')
    try:
        if file_type == 'video':
            await update.message.reply_video(video=char['file_id'], caption=text, parse_mode="HTML")
        elif file_type == 'document':
            await update.message.reply_document(document=char['file_id'], caption=text, parse_mode="HTML")
        else:
            await update.message.reply_photo(photo=char['file_id'], caption=text, parse_mode="HTML")
    except Exception as e:
        print(f"HCLAIM MEDIA ERROR: {e}")
        await update.message.reply_text(text + f"\n\n⚠️ <i>Media failed to load (Possible invalid ID)</i>", parse_mode="HTML")
        # Log character issue
        from bot.modules.admin import send_log
        await send_log(context, f"⚠️ <b>Hclaim Media Error</b>\nChar: {char['name']} (ID: {char_id})\nError: <code>{e}</code>")
