import re
import uuid
import telegram.error
from telegram import (
    Update, 
    InlineQueryResultCachedPhoto, 
    InlineQueryResultCachedVideo, 
    InlineQueryResultCachedMpeg4Gif, 
    InlineQueryResultCachedDocument, 
    InlineQueryResultArticle, 
    InputTextMessageContent, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from telegram.ext import ContextTypes
from bot.database.mongo import characters_collection, users_collection
from bot.utils.formatters import escape_markdown

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command to prompt user to use inline search."""
    keyboard = [
        [InlineKeyboardButton("🔦 SEARCH CHARACTERS", switch_inline_query_current_chat="")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚪ TO SEARCH CHARACTER CLICK ON BUTTON BELOW", 
        reply_markup=reply_markup
    )

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline queries to search for characters, with resilient fallbacks."""
    query_text = update.inline_query.query.strip()
    user_id = update.inline_query.from_user.id
    
    # Check if user exists in cache/memory if possible, otherwise DB
    caller_data = await users_collection.find_one({"id": user_id})
    if not caller_data:
        caller_data = await users_collection.find_one({"id": str(user_id)})
    
    caller_owned = set(caller_data.get("waifus", [])) if caller_data else set()
    normalized_caller_owned = {str(wid) for wid in caller_owned}

    # Harem search logic
    target_user_data = None
    search_harem = False
    
    # Check for specific search modes
    mode_query = query_text.lower()
    
    if mode_query.startswith("harem."):
        search_harem = True
        match = re.search(r"harem\.(\S+)\s*(.*)", query_text, re.IGNORECASE)
        if match:
            target_query = match.group(1).strip()
            query_text = match.group(2).strip()
            
            if target_query.isdigit():
                tid = int(target_query)
                target_user_data = await users_collection.find_one({"id": tid})
                if not target_user_data:
                    target_user_data = await users_collection.find_one({"id": str(tid)})
            else:
                target_username = target_query.replace("@", "")
                target_user_data = await users_collection.find_one({"username": re.compile(f"^{re.escape(target_username)}$", re.IGNORECASE)})
            
            if not target_user_data:
                target_user_data = None 
        else:
            search_harem = True
            query_text = query_text[6:].strip()
            target_user_data = caller_data
            
    elif mode_query.startswith("my "):
        search_harem = True
        query_text = query_text[3:].strip()
        target_user_data = caller_data

    elif mode_query.startswith("image "):
        # Just search as normal, but keep 'image ' out of query
        query_text = query_text[6:].strip()

    # Selection of characters to show
    target_owned = list(target_user_data.get("waifus", [])) if target_user_data else []
    normalized_target_owned = {str(int(wid)) if str(wid).isdigit() else str(wid) for wid in target_owned}

    # Filtration logic with robust ID handling
    search_filter = {}
    if query_text:
        # Use a more efficient regex prefix search if possible, but keep partial match for now
        # escape_markdown is not needed for regex, but re.escape is.
        regex = re.compile(re.escape(query_text), re.IGNORECASE)
        or_filters = [
            {"name": regex}, 
            {"anime": regex}
        ]
        
        # Smart ID lookup
        if query_text.isdigit():
            clean_id = str(int(query_text)) # Normalize 001 -> 1
            or_filters.append({"id": clean_id})
            or_filters.append({"id": int(clean_id)})
        
        search_filter["$or"] = or_filters

    if search_harem:
        search_filter["id"] = {"$in": list(normalized_target_owned)}

    # Fetching with projection to save memory (RAM)
    limit_val = 50
    projection = {"id": 1, "name": 1, "anime": 1, "rarity": 1, "file_id": 1, "file_type": 1, "type": 1, "caught_count": 1}
    cursor = characters_collection.find(search_filter, projection).sort("_id", -1).limit(limit_val)
    
    char_dict = {} # Initialize for later use
    counts = {}    # Initialize for later use
    if search_harem and target_user_data:
        from collections import Counter
        counts = Counter(normalized_target_owned)
    
    if search_harem and not query_text:
        all_chars = await cursor.to_list(limit_val)
        char_dict = {str(c['id']): c for c in all_chars}
        unique_ordered = []
        seen_ids = set()
        for wid in reversed(target_owned):
            norm_wid = str(int(wid)) if str(wid).isdigit() else str(wid)
            if norm_wid in char_dict and norm_wid not in seen_ids:
                unique_ordered.append(char_dict[norm_wid])
                seen_ids.add(norm_wid)
            if len(unique_ordered) >= limit_val: break
        characters = unique_ordered
    else:
        characters = await cursor.to_list(limit_val)
        if search_harem:
            char_dict = {str(c['id']): c for c in characters}

    # Fallback if NOTHING is found - show recent characters
    if not characters and not search_harem:
        characters = await characters_collection.find().sort("_id", -1).limit(25).to_list(25)

    # BATCH STATS FETCHING (Crucial for performance)
    results = []
    if characters:
        seen = set()
        for char in characters:
            char_id = str(char.get('id', 'N/A'))
            name = char.get('name', 'Unknown')
            anime = char.get('anime', 'Unknown')
            norm_id = str(int(char_id)) if char_id.isdigit() else char_id
            
            if norm_id in seen: continue
            seen.add(norm_id)
            
            is_owned = norm_id in normalized_caller_owned
            ownership_tag = " [Caught \u2705]" if is_owned else ""
            rarity = str(char.get('rarity', 'Common'))
            
            emoji_map = {
                "1": "🤍", "Common": "\U0001f535", "Uncommon": "\U0001f7e3", "Rare": "\U0001f7e0", 
                "Legendary": "\U0001f7e1", "Mystical": "\U0001f4ae", "Divine": "\u269c\ufe0f",
                "Crossverse": "\u26a1", "Supreme": "🤍", "Cataphract": "\u2728"
            }
            r_emoji = emoji_map.get(rarity, "\U0001f4ae")
            
            # Use stored caught_count for speed
            global_total = char.get('caught_count', 0)
            char_type = char.get('type')
            
            from bot.utils.formatters import get_stylized_rarity
            stylized_rarity = get_stylized_rarity(rarity)

            if search_harem and target_user_data:
                # Special Harem Theme
                target_name = target_user_data.get('name') or target_user_data.get('first_name') or 'Unknown'
                char_count = counts.get(norm_id, 1)
                
                # Fetch anime progress for harem view
                anime_total = await characters_collection.count_documents({"anime": anime})
                anime_collected = await characters_collection.count_documents({"id": {"$in": list(normalized_target_owned)}, "anime": anime})
                
                caption = (
                    f"\u26e9 <b>{escape_markdown(target_name)}'s harem</b>\n\n"
                    f"\u2618\ufe0f Name: {escape_markdown(name)} (x{char_count})\n"
                    f"{r_emoji} Rarity: {rarity}\n"
                    f"\u269c\ufe0f Anime: {escape_markdown(anime)} ({anime_collected}/{anime_total})\n\n"
                    f"\U0001f194: {char_id} - Needed for trading/gifting"
                )
            else:
                # General Fashion Theme
                type_line = ""
                is_event = False
                if char_type:
                    if char_type.lower() in ["ee", "event"]:
                        char_type = "event"
                        is_event = True
                    match = re.search(r"\[(\W+)\]", name)
                    t_emoji = match.group(1) if match else "\U0001f4a0"
                    if is_event:
                        type_line = f"\n<b><i>{char_type}</i></b>{t_emoji}\n"
                    else:
                        type_line = f"\n{t_emoji}<b><i>{char_type}</i></b>{t_emoji}\n"

                header = f"OwO! Check out this event character!{ownership_tag}" if is_event else f"OwO! Check out this character!{ownership_tag}"
                caption = (
                    f"{header}\n\n"
                    f"<b>{escape_markdown(anime)}</b>\n"
                    f"{char_id}: <b>{escape_markdown(name)}</b>\n"
                    f"{stylized_rarity}\n"
                    f"{type_line}\n"
                    f"\U0001f30e ᴄᴀᴜɢʜᴛ ɢʟᴏʙᴀʟʟʏ: {global_total} ᴛɪᴍᴇs"
                )
            
            file_id = char.get('file_id')
            file_type = char.get('file_type', 'photo')
            res_id = str(uuid.uuid4())
            
            title_text = f"[{r_emoji}] {name}{ownership_tag}"
            desc_text = f"ID: {char_id} • {anime} • {rarity}"

            if file_id:
                try:
                    if file_type == 'photo':
                        results.append(InlineQueryResultCachedPhoto(
                            id=res_id, photo_file_id=file_id, 
                            title=title_text, description=desc_text,
                            caption=caption, parse_mode="HTML"
                        ))
                    elif file_type == 'video':
                        results.append(InlineQueryResultCachedVideo(
                            id=res_id, video_file_id=file_id, 
                            title=title_text, description=desc_text,
                            caption=caption, parse_mode="HTML"
                        ))
                    elif file_type == 'animation':
                        results.append(InlineQueryResultCachedMpeg4Gif(
                            id=res_id, mpeg4_file_id=file_id, 
                            title=title_text, description=desc_text,
                            caption=caption, parse_mode="HTML"
                        ))
                    elif file_type == 'document':
                        results.append(InlineQueryResultCachedDocument(
                            id=res_id, document_file_id=file_id, 
                            title=title_text, description=desc_text,
                            caption=caption, parse_mode="HTML"
                        ))
                    continue
                except Exception as e:
                    print(f"Error adding media for {name}: {e}")

            # Final Text Fallback
            results.append(InlineQueryResultArticle(
                id=res_id, title=f"{title_text} [TEXT]",
                description=desc_text,
                input_message_content=InputTextMessageContent(caption, parse_mode="HTML")
            ))

    cache_time = 300 if search_harem else 10 # Increased from 1s to 10s to reduce Koyeb load
    
    if not results:
        results.append(InlineQueryResultArticle(
            id=str(uuid.uuid4()), title="No characters found",
            input_message_content=InputTextMessageContent("Try searching for something else! OwO")
        ))
        cache_time = 1

    try:
        await update.inline_query.answer(results, cache_time=cache_time, is_personal=True)
    except telegram.error.BadRequest as e:
        print(f"🚨 [INLINE ERROR] {e} | Query: {query_text}")
    except Exception as e:
        print(f"🚨 [INLINE FATAL] {e}")

