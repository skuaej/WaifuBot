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
    
    # ALWAYS fetch current user for global catch-tags
    caller_data = await users_collection.find_one({"id": user_id})
    if not caller_data:
        caller_data = await users_collection.find_one({"id": str(user_id)})
    
    caller_owned = set(caller_data.get("waifus", [])) if caller_data else set()
    normalized_caller_owned = {str(int(wid)) if str(wid).isdigit() else str(wid) for wid in caller_owned}

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
        regex = re.compile(re.escape(query_text), re.IGNORECASE)
        or_filters = [{"name": regex}, {"anime": regex}]
        
        # Smart ID lookup
        if query_text.isdigit():
            clean_id = int(query_text)
            or_filters.append({"id": clean_id})
            or_filters.append({"id": str(clean_id)})
        else:
            or_filters.append({"id": regex})
            
        search_filter["$or"] = or_filters

    if search_harem:
        search_filter["id"] = {"$in": list(normalized_target_owned)}

    # Fetching
    limit_val = 50
    cursor = characters_collection.find(search_filter).sort("_id", -1).limit(limit_val)
    
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

    # Fallback if NOTHING is found - show recent characters
    if not characters and not search_harem:
        characters = await characters_collection.find().sort("_id", -1).limit(25).to_list(25)

    # BATCH STATS FETCHING (Crucial for performance)
    results = []
    if characters:
        all_res_ids = []
        for c in characters:
            cid = str(c.get('id'))
            all_res_ids.append(cid)
            if cid.isdigit():
                all_res_ids.append(int(cid))
        
        # Single aggregation to get counts for all characters in results
        stats_pipeline = [
            {"$match": {"waifus": {"$in": all_res_ids}}},
            {"$unwind": "$waifus"},
            {"$match": {"waifus": {"$in": all_res_ids}}},
            {"$group": {"_id": "$waifus", "total": {"$sum": 1}}}
        ]
        
        # Create a mapping of ID -> Total Count
        id_stats = {}
        async for stat in users_collection.aggregate(stats_pipeline):
            sid = str(stat["_id"])
            id_stats[sid] = id_stats.get(sid, 0) + stat["total"]

        seen = set()
        for char in characters:
            char_id = str(char.get('id', 'N/A'))
            name = char.get('name', 'Unknown')
            anime = char.get('anime', 'Unknown')
            norm_id = str(int(char_id)) if char_id.isdigit() else char_id
            
            if norm_id in seen: continue
            seen.add(norm_id)
            
            is_owned = norm_id in normalized_caller_owned
            ownership_tag = " [Caught ✅]" if is_owned else ""
            rarity = str(char.get('rarity', 'Common'))
            
            emoji_map = {
                "1": "🤍", "Common": "🔵", "Uncommon": "🟣", "Rare": "🟠", 
                "Legendary": "🟡", "Mystical": "💮", "Divine": "⚜️",
                "Crossverse": "⚡", "Supreme": "🤍", "Cataphract": "✨"
            }
            r_emoji = emoji_map.get(rarity, "💮")
            
            # Use batch stats
            global_total = id_stats.get(norm_id, 0)
            
            caption = (
                f"OwO! Check out this character!{ownership_tag}\n\n"
                f"<b>{escape_markdown(anime)}</b>\n\n"
                f"{char_id}: <b>{escape_markdown(name)}</b>\n\n"
                f"<b>Rarity:</b> ({r_emoji} <b>RARITY:</b> {rarity})\n"
                f"<b>Globally Caught:</b> {global_total} times"
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

    cache_time = 300 if search_harem else 1  
    
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

