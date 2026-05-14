from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.mongo import users_collection, characters_collection, captures_collection
from bot.config import SUPPORT_CHAT_ID, SUPPORT_CHAT_LINK
from bot.utils.formatters import escape_markdown
import re
import random
import math
import html

async def get_harem_page(user_id: int, page: int, target_user_name: str) -> tuple:
    user_data = await users_collection.find_one({"id": user_id})
    if not user_data:
        # Try string ID as fallback
        user_data = await users_collection.find_one({"id": str(user_id)})
        
    if not user_data or not user_data.get("waifus"):
        return "\u274c You haven't caught any waifus yet!", None, None

    waifu_ids = user_data["waifus"]
    hmode = user_data.get("hmode", "Default")
    
    # Normalize all IDs for counting and display
    normalized_waifu_ids = [str(int(wid)) if wid.isdigit() else wid for wid in waifu_ids]
    
    from collections import Counter
    counts = Counter(normalized_waifu_ids)
    # Unique normalized IDs owned by the user
    normalized_owned_ids = list(counts.keys())
    
    # Fetch character data with projection
    projection = {"id": 1, "name": 1, "anime": 1, "rarity": 1, "file_id": 1, "file_type": 1}
    cursor = characters_collection.find({"id": {"$in": normalized_owned_ids}}, projection)
    char_map = {}
    async for char in cursor:
        char_map[char["id"]] = char
        
    # Ensure they exist in database
    normalized_owned_ids = [wid for wid in normalized_owned_ids if wid in char_map]
            
    emoji_map = {
        "Common": "\U0001f535", "Uncommon": "\U0001f7e3", "Rare": "\U0001f7e0", 
        "Legendary": "\U0001f7e1", "Mystical": "\U0001f4ae", "Divine": "\u269c\ufe0f",
        "Crossverse": "\u26a1", "Supreme": "\U0001fa9e", "Cataphract": "\u2728"
    }

    # Filter based on hmode if it's a specific rarity
    if hmode in emoji_map:
        normalized_owned_ids = [wid for wid in normalized_owned_ids if char_map[wid].get("rarity", "Common") == hmode]
    
    if not normalized_owned_ids:
        return f"\u274c You don't have any characters matching the selected rarity filter ({hmode}).", None, None

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
        r_emoji = emoji_map.get(char.get('rarity', 'Common'), '\U0001f4ae')
        char_count = counts.get(wid, 1)
        
        # Find total collected in this anime
        collected_in_anime = len([x for x in normalized_owned_ids if char_map[x]['anime'] == char['anime']])
        # Find total existing in this anime
        total_in_db = await characters_collection.count_documents({"anime": char['anime']})
        
        text += (
            f"\n\u2618\ufe0f <b>Name:</b> {escape_markdown(char['name'])} (x{char_count})\n"
            f"\U0001f194 <b>ID:</b> <code>{char['id']}</code>\n"
            f"{r_emoji} <b>Rarity:</b> {char.get('rarity', 'Common')}\n"
            f"\u269c\ufe0f <b>Anime:</b> {escape_markdown(char['anime'])} ({collected_in_anime}/{total_in_db})\n"
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
        nav_row.append(InlineKeyboardButton("\u2b05\ufe0f Back", callback_data=f"harem_page_{user_id}_{page-1}"))
    
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Next \u27a1\ufe0f", callback_data=f"harem_page_{user_id}_{page+1}"))
    
    if nav_row:
        keyboard.append(nav_row)
        
    keyboard.append([InlineKeyboardButton(f"\u26e9 CHARACTERS ({total_items})", switch_inline_query_current_chat=f"harem.{user_id} ")])
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
        await query.edit_message_text(f"❄️ CHOOSE YOUR PREFFERED RARITY\n\n\u2705 Updated to: {mode}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ CLOSE", callback_data="hmode_close")]]))
        return

    if data.startswith("harem_page_"):
        parts = data.split("_")
        if len(parts) < 4:
            await query.answer("\u274c Invalid callback data.", show_alert=True)
            return
            
        target_id = int(parts[2])
        page = int(parts[3])
        
        if user_id != target_id:
            await query.answer("\u274c This is not your harem!", show_alert=True)
            return
            
            
        text, display_char, reply_markup = await get_harem_page(target_id, page, query.from_user.first_name)
        if text.startswith("\u274c"):
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
            await query.answer("\u274c Error updating harem page.", show_alert=True)
            pass

        await query.answer()

async def hmode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Interactive /hmode to change sorting/filtering."""
    keyboard = [
        [InlineKeyboardButton("🐉 Default", callback_data="hmode_Default"), InlineKeyboardButton("Detailed 🦖", callback_data="hmode_Detailed")],
        [InlineKeyboardButton("🦕 Reset Preference", callback_data="hmode_Default")],
        [InlineKeyboardButton("\u2728 RARITY: Cataphract", callback_data="hmode_Cataphract")],
        [InlineKeyboardButton("\U0001fa9e RARITY: Supreme", callback_data="hmode_Supreme")],
        [InlineKeyboardButton("\u26a1 RARITY: Crossverse", callback_data="hmode_Crossverse")],
        [InlineKeyboardButton("\u269c\ufe0f RARITY: Divine", callback_data="hmode_Divine")],
        [InlineKeyboardButton("\U0001f4ae RARITY: Mystical", callback_data="hmode_Mystical")],
        [InlineKeyboardButton("\U0001f7e1 RARITY: Legendary", callback_data="hmode_Legendary")],
        [InlineKeyboardButton("\U0001f7e0 RARITY: Rare", callback_data="hmode_Rare")],
        [InlineKeyboardButton("\U0001f7e3 RARITY: Uncommon", callback_data="hmode_Uncommon")],
        [InlineKeyboardButton("\U0001f535 RARITY: Common", callback_data="hmode_Common")],
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
                cid = str(c['id'])
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
            
    h_percent = (total_distinct / max_characters) * 100
    
    text = (
        "  ╭──「 🎗️ Cᴀᴛᴄʜᴇʀ Pʀᴏғɪʟᴇ 🎗 」\n"
        f"├─➩ \U0001f464 ᴜsᴇʀ: <a href='tg://user?id={user.id}'>{escape_markdown(user.first_name)}</a>\n"
        f"├─➩ 🔩 ᴜsᴇʀ ɪᴅ: <code>{user.id}</code>\n"
        f"├─➩ \u26a1 ᴛᴏᴛᴀʟ ᴄʜᴀʀᴀᴄᴛᴇʀ: {total_characters} ({total_distinct})\n"
        f"├─➩ \U0001fae7 ʜᴀʀᴇᴍ: {total_distinct}/{max_characters} ({h_percent:.3f}%)\n"
        f"├─➩ {block_status}\n"
        "╭───────────────────\n"
        f"├─➩ \U0001f535 𝙍𝘼𝙍𝙄𝙏𝙔: Common: {rarities['Common']}\n"
        f"├─➩ \U0001f7e3 𝙍𝘼𝙍𝙄𝙏𝙔: Uncommon: {rarities['Uncommon']}\n"
        f"├─➩ \U0001f7e0 𝙍𝘼𝙍𝙄𝙏𝙔: Rare: {rarities['Rare']}\n"
        f"├─➩ \U0001f7e1 𝙍𝘼𝙍𝙄𝙏𝙔: Legendary: {rarities['Legendary']}\n"
        f"├─➩ \U0001f4ae 𝙍𝘼𝙍𝙄𝙏𝙔: Mystical: {rarities['Mystical']}\n"
        f"├─➩ \u269c\ufe0f 𝙍𝘼𝙍𝙄ᴛʏ: Divine: {rarities['Divine']}\n"
        f"├─➩ \u26a1 𝙍𝘼𝙍𝙄𝙏𝙔: Crossverse: {rarities['Crossverse']}\n"
        f"├─➩ \U0001fa9e 𝙍𝘼𝙍𝙄𝙏𝙔: Supreme: {rarities['Supreme']}\n"
        f"├─➩ \u2728 𝙍𝘼𝙍𝙄ᴛʏ: Cataphract: {rarities['Cataphract']}\n"
        "╭───────────────────\n"
        f"├─➩ \U0001f3c6 Gʟᴏʙᴀʟ Rᴀɴᴋ: {global_rank if global_rank > 0 else 'N/A'}\n"
        f"├─➩ 📍 Cʜᴀᴛ Rᴀɴᴋ: {local_rank if local_rank > 0 else 'N/A'}\n"
        "╰───────────────────"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """TOP 10 USERS WITH MOST CHARACTERS GLOBALLY (Replaces /ctop /gtop)."""
    user_pipeline = [
        {"$project": {
            "name": 1,
            "first_name": 1,
            "id": 1,
            "waifu_count": {"$size": {"$ifNull": ["$waifus", []]}}
        }},
        {"$sort": {"waifu_count": -1}},
        {"$limit": 10}
    ]
    try:
        leaderboard_data = await users_collection.aggregate(user_pipeline).to_list(length=10)
    except Exception as e:
        print(f"TOP AGGREGATION ERROR: {e}")
        await update.message.reply_text("\u274c Error fetching the global leaderboard.")
        return
        
    if not leaderboard_data:
        await update.message.reply_text("\u274c No users found in the leaderboard.")
        return
        
    text = "<b>TOP 10 USERS WITH MOST CHARACTERS GLOBALLY</b>\n\n"
    idx = 1
    for u in leaderboard_data:
        user_id = u.get('id')
        name_val = u.get('name') or u.get('first_name') or 'Unknown'
        user_name = html.escape(str(name_val))
        if len(user_name) > 15:
            user_name = user_name[:15] + '...'
            
        count = u.get('waifu_count', 0)
        
        if user_id:
            text += f"{idx}. <a href='tg://user?id={user_id}'><b>{user_name}</b></a> (<code>{user_id}</code>) ➾ <b>{count}</b>\n"
        else:
            text += f"{idx}. <b>{user_name}</b> (<code>{u.get('_id')}</code>) ➾ <b>{count}</b>\n"
        idx += 1

    from bot.config import PHOTO_URL
    photo_url = random.choice(PHOTO_URL) if PHOTO_URL else "https://telegra.ph/file/b925c3985f0f325e62e17.jpg"
    await update.message.reply_photo(photo=photo_url, caption=text, parse_mode="HTML")

async def topgroups_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """TOP 10 GROUPS WHO GUESSED MOST CHARACTERS."""
    pipeline = [
        {"$group": {"_id": "$chat_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    cursor = captures_collection.aggregate(pipeline)
    leaderboard_data = await cursor.to_list(length=10)
    
    leaderboard_message = "<b>TOP 10 GROUPS WHO GUESSED MOST CHARACTERS</b>\n\n"
    i = 1
    for entry in leaderboard_data:
        chat_id = entry["_id"]
        count = entry["count"]
        try:
            chat = await context.bot.get_chat(chat_id)
            group_name = html.escape(chat.title or "Unknown")
        except:
            group_name = "Unknown Group"
            
        if len(group_name) > 10:
            group_name = group_name[:15] + '...'
            
        leaderboard_message += f'{i}. <b>{group_name}</b> ➾ <b>{count}</b>\n'
        i += 1
        
    from bot.config import PHOTO_URL
    photo_url = random.choice(PHOTO_URL) if PHOTO_URL else "https://telegra.ph/file/b925c3985f0f325e62e17.jpg"
    await update.message.reply_photo(photo=photo_url, caption=leaderboard_message, parse_mode='HTML')

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
        await update.message.reply_text("\u274c You don't have any waifus!")
        return

    # Normalize all owned IDs for checking
    waifus_list = user_data["waifus"]
    normalized_owned = {str(int(wid)) if str(wid).isdigit() else wid for wid in waifus_list}
    
    if norm_input not in normalized_owned:
        await update.message.reply_text(f"\u274c You don't own waifu ID {input_id}!")
        return
        
    # Robust search by ID (padded or not)
    if input_id.isdigit():
        norm_id = str(int(input_id))
        regex = re.compile(f"^0*{norm_id}$")
        char_data = await characters_collection.find_one({"id": regex})
    else:
        char_data = await characters_collection.find_one({"id": input_id})
        
    if not char_data:
        await update.message.reply_text(f"\u274c Character ID {input_id} not found in database.")
        return
        
    actual_id = char_data['id']
    
    keyboard = [
        [InlineKeyboardButton("\u2705 Yes", callback_data=f"fav_yes_{actual_id}"), InlineKeyboardButton("\u274c No", callback_data="fav_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"\U0001f496 Do you want to set <b>{escape_markdown(char_data['name'])}</b> as your favorite?"
    
    try:
        file_type = char_data.get('file_type', 'photo')
        if file_type == 'video':
            await update.message.reply_video(video=char_data['file_id'], caption=text, parse_mode="HTML", reply_markup=reply_markup)
        elif file_type == 'document':
            await update.message.reply_document(document=char_data['file_id'], caption=text, parse_mode="HTML", reply_markup=reply_markup)
        else:
            await update.message.reply_photo(photo=char_data['file_id'], caption=text, parse_mode="HTML", reply_markup=reply_markup)
    except Exception as e:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)

async def fav_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /fav inline buttons."""
    query = update.callback_query
    data = query.data
    user = query.from_user

    if not data.startswith("fav_"):
        return
        
    action = data.split("_")[1]
    
    if action == "no":
        await query.message.edit_reply_markup(reply_markup=None)
        await query.answer("Favorite change cancelled.")
        return
        
    if action == "yes":
        actual_id = data.split("_")[2]
        await users_collection.update_one({"id": user.id}, {"$set": {"favorite": actual_id}})
        
        char_data = await characters_collection.find_one({"id": actual_id})
        name = escape_markdown(char_data['name']) if char_data else "Unknown"
        
        await query.message.edit_caption(f"\U0001f496 Successfully set <b>{name}</b> as your favorite!", parse_mode="HTML", reply_markup=None)
        await query.answer("Favorite updated!")

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
        await update.message.reply_text(f"\u274c Character not found.")
        return
        
    char_id = char['id']
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
    local_results = await captures_collection.aggregate(local_pipeline).to_list(length=10)
    
    # Handle Type (optional)
    char_type = char.get('type')
    type_line = ""
    if char_type:
        match = re.search(r"\[(\W+)\]", char['name'])
        t_emoji = match.group(1) if match else "\U0001f4a0"
        type_line = f"\n{t_emoji}<b><i>{char_type}</i></b>{t_emoji}\n"

    # BUILD MESSAGE
    text = (
        f"OwO! Check out this character!\n\n"
        f"<b>{escape_markdown(char['anime'])}</b>\n"
        f"{char['id']}: {escape_markdown(char['name'])}\n"
        f"{stylized_rarity}\n"
        f"{type_line}\n"
    )

    # Global Top 10 Section
    if global_results:
        text += "\U0001f30e <b>ɢʟᴏʙᴀʟʟʏ ᴛᴏᴘ 10 ᴄᴀᴛᴄʜᴇʀs</b>\n"
        for entry in global_results:
            uid = entry["_id"]
            count = entry["count"]
            user_data = await users_collection.find_one({"id": uid})
            if not user_data:
                user_data = await users_collection.find_one({"id": str(uid)})
            
            uname = escape_markdown(user_data.get('name') or user_data.get('first_name') or 'Unknown')
            text += f"\u27a5 <a href='tg://user?id={uid}'>{uname}</a> (<code>{uid}</code>) x{count}\n"
        text += "\n"

    # Local Top 10 Section
    if local_results:
        text += f"\U0001f396\ufe0f ᴛᴏᴘ 10 ᴄᴀᴛᴄʜᴇʀs ᴏғ ᴛʜɪs ᴄʜᴀʀᴀᴄᴛᴇʀ ɪɴ ᴛʜɪs ᴄʜᴀᴛ\n"
        for entry in local_results:
            uid = entry["_id"]
            count = entry["count"]
            user_data = await users_collection.find_one({"id": uid})
            if not user_data:
                user_data = await users_collection.find_one({"id": str(uid)})
            
            uname = escape_markdown(user_data.get('name') or user_data.get('first_name') or 'Unknown')
            text += f"\u27a5 <a href='tg://user?id={uid}'>{uname}</a> (<code>{uid}</code>) x{count}\n"
        
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
            text + "\n\n\u26a0\ufe0f <b>Media Error:</b> The file ID for this character is invalid for the current bot. Please re-upload this character.",
            parse_mode="HTML"
        )


async def hclaim_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/hclaim - Claim a random character from Common/Uncommon/Rare/Legendary."""
    import time
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Support Chat Join Check
    if SUPPORT_CHAT_ID:
        try:
            member = await context.bot.get_chat_member(SUPPORT_CHAT_ID, user.id)
            if member.status not in ["member", "administrator", "creator"]:
                raise Exception("Not a member")
        except Exception:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [[InlineKeyboardButton("\ud83d\ude80 JOIN SUPPORT CHAT", url=SUPPORT_CHAT_LINK)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"\u274c <b>You must join our Support Group to use this command!</b>\n\n"
                f"\ud83d\udc49 Click the button below to join, then try again.",
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            return

    user_data = await users_collection.find_one({"id": user.id})
    if user_data:
        last_claim = user_data.get("last_hclaim", 0)
        now = time.time()
        if now - last_claim < 86400:
            await update.message.reply_text("\u23f3 <b>You already claimed today!</b>\nCome back after next 24 hours.", parse_mode="HTML")
            return

    # Pick a random character from claimable rarities
    claimable_rarities = ["Common", "Uncommon", "Rare", "Legendary"]
    pipeline = [
        {"$match": {"rarity": {"$in": claimable_rarities}}},
        {"$sample": {"size": 1}}
    ]
    results = await characters_collection.aggregate(pipeline).to_list(length=1)

    if not results:
        await update.message.reply_text("\u274c No claimable characters found in the database.")
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
        "Common": "\U0001f535", "Uncommon": "\U0001f7e3", "Rare": "\U0001f7e0",
        "Legendary": "\U0001f7e1", "Mystical": "\U0001f4ae", "Divine": "\u269c\ufe0f",
        "Crossverse": "\u26a1", "Supreme": "\U0001fa9e", "Cataphract": "\u2728"
    }
    r_emoji = emoji_map.get(char.get('rarity', 'Common'), '\U0001f4ae')

    text = (
        f"\U0001f381 <b>Harem Claim!</b>\n\n"
        f"<a href='tg://user?id={user.id}'>{escape_markdown(user.first_name)}</a> claimed:\n\n"
        f"\U0001f3f7\ufe0f <b>{escape_markdown(char['name'])}</b>\n"
        f"\U0001fae7 Anime: {escape_markdown(char.get('anime', 'Unknown'))}\n"
        f"{r_emoji} Rarity: {char.get('rarity', 'Common')}\n"
        f"\U0001f194 ID: {char_id}"
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
        await update.message.reply_text(text + f"\n\n\u26a0\ufe0f <i>Media failed to load (Possible invalid ID)</i>", parse_mode="HTML")
        # Log character issue
        from bot.modules.admin import send_log
        await send_log(context, f"\u26a0\ufe0f <b>Hclaim Media Error</b>\nChar: {char['name']} (ID: {char_id})\nError: <code>{e}</code>")

async def todaygtop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GLOBAL TOP 10 USERS WITH MOST CHARACTERS CAUGHT TODAY."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    
    pipeline = [
        {"$match": {"timestamp": {"$gte": start_of_day}}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    
    leaderboard_data = await captures_collection.aggregate(pipeline).to_list(length=10)
    
    if not leaderboard_data:
        await update.message.reply_text("\u274c No characters caught globally today yet!")
        return
        
    text = "<b>GLOBAL TOP 10 CATCHERS (TODAY)</b>\n\n"
    idx = 1
    for entry in leaderboard_data:
        uid = entry["_id"]
        count = entry["count"]
        
        user_data = await users_collection.find_one({"id": uid})
        if not user_data:
             user_data = await users_collection.find_one({"id": str(uid)})
             
        name = "Unknown"
        if user_data:
            name = user_data.get("name") or user_data.get("first_name") or "Unknown"
        
        name = html.escape(name)
        if len(name) > 15:
            name = name[:15] + "..."
            
        text += f"{idx}. <a href='tg://user?id={uid}'><b>{name}</b></a> (<code>{uid}</code>) ➾ <b>{count}</b>\n"
        idx += 1
        
    from bot.config import PHOTO_URL
    import random
    photo_url = random.choice(PHOTO_URL) if PHOTO_URL else "https://telegra.ph/file/b925c3985f0f325e62e17.jpg"
    await update.message.reply_photo(photo=photo_url, caption=text, parse_mode="HTML")

async def gtop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """TOP 10 USERS WHO GUESSED MOST CHARACTERS IN THE CURRENT GROUP."""
    chat_id = update.effective_chat.id
    if update.effective_chat.type == "private":
        await update.message.reply_text("This command only works in groups.")
        return

    # Aggregation to find top users in this group
    pipeline = [
        {"$match": {"chat_id": chat_id}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    
    leaderboard_data = await captures_collection.aggregate(pipeline).to_list(length=10)
    
    if not leaderboard_data:
        await update.message.reply_text("\u274c No captures found in this group.")
        return
        
    text = f"<b>TOP 10 CATCHERS IN {html.escape(update.effective_chat.title)}</b>\n\n"
    idx = 1
    for entry in leaderboard_data:
        uid = entry["_id"]
        count = entry["count"]
        
        # Fetch name from users_collection
        user_data = await users_collection.find_one({"id": uid})
        if not user_data:
             user_data = await users_collection.find_one({"id": str(uid)})
             
        name = "Unknown"
        if user_data:
            name = user_data.get("name") or user_data.get("first_name") or "Unknown"
        
        name = html.escape(name)
        if len(name) > 15:
            name = name[:15] + "..."
            
        text += f"{idx}. <a href='tg://user?id={uid}'><b>{name}</b></a> (<code>{uid}</code>) ➾ <b>{count}</b>\n"
        idx += 1
        
    from bot.config import PHOTO_URL
    import random
    photo_url = random.choice(PHOTO_URL) if PHOTO_URL else "https://telegra.ph/file/b925c3985f0f325e62e17.jpg"
    await update.message.reply_photo(photo=photo_url, caption=text, parse_mode="HTML")


async def hdelete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/hdelete ID1, ID2, or range like 1-6 - Let users delete characters from their own harem."""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("Usage: /hdelete <Character IDs> (comma separated or range like 1-6)")
        return

    user_data = await users_collection.find_one({"id": user.id})
    if not user_data or not user_data.get("waifus"):
        await update.message.reply_text("\u274c You don't have any waifus to delete!")
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
                    await update.message.reply_text("\u274c Range too large. Max 5000 at a time.")
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
        await update.message.reply_text("\u274c You don't own any characters matching the provided IDs.")
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
            
    await update.message.reply_text(f"\u2705 Successfully deleted {len(set(actual_ids_to_delete))} unique character(s) from your harem.")
