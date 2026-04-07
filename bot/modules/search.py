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
    
    if query_text.lower().startswith("harem."):
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
            
    elif query_text.lower().startswith("my "):
        search_harem = True
        query_text = query_text[3:].strip()
        target_user_data = caller_data

    # Selection of characters to show
    target_owned = list(target_user_data.get("waifus", [])) if target_user_data else []
    normalized_target_owned = {str(int(wid)) if str(wid).isdigit() else str(wid) for wid in target_owned}

    # Filtration logic with robust ID handling
    search_filter = {}
    if query_text:
        regex = re.compile(re.escape(query_text), re.IGNORECASE)
        or_filters = [{"name": regex}, {"anime": regex}]
        
        # Smart ID lookup: Check both String and Integer versions of the ID
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
    
    # Sort by _id -1 (descending) to show newly uploaded characters first!
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
            if len(unique_ordered) >= 50: break
        characters = unique_ordered
    else:
        characters = await cursor.to_list(limit_val)

    # Fallback if NOTHING is found
    if not characters and not search_harem:
        characters = await characters_collection.find().sort("_id", -1).limit(20).to_list(20)

    results = []
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
        
        # Fetch global catch stats for this one character
        search_ids = [char_id]
        if char_id.isdigit():
            search_ids.append(int(char_id))
            
        stats_pipeline = [
            {"$match": {"waifus": {"$in": search_ids}}},
            {"$project": {
                "name": 1, "first_name": 1, "id": 1,
                "count": {
                    "$size": {
                        "$filter": {
                            "input": "$waifus",
                            "cond": {"$in": ["$$this", search_ids]}
                        }
                    }
                }
            }},
            {"$facet": {
                "total": [{"$group": {"_id": None, "total": {"$sum": "$count"}}}],
                "top": [{"$sort": {"count": -1}}, {"$limit": 3}]
            }}
        ]
        
        stats_results = await users_collection.aggregate(stats_pipeline).to_list(length=1)
        global_total = 0
        top_text = ""
        
        if stats_results:
            facet = stats_results[0]
            if facet.get("total"):
                global_total = facet["total"][0]["total"]
            
            tops = facet.get("top", [])
            if tops:
                top_text = "\n🏅 <b>Top Catchers:</b>\n"
                for u in tops:
                    t_name = escape_markdown(u.get('name') or u.get('first_name') or 'Unknown')
                    t_id = u.get('id') or u.get('_id', 'Unknown')
                    t_count = u.get('count', 0)
                    top_text += f"➥ <a href='tg://user?id={t_id}'>{t_name}</a> (<code>{t_id}</code>) x{t_count}\n"
        
        caption = (
            f"OwO! Check out this character!{ownership_tag}\n\n"
            f"<b>{escape_markdown(anime)}</b>\n\n"
            f"{char_id}: <b>{escape_markdown(name)}</b>\n\n"
            f"<b>Rarity:</b> ({r_emoji} <b>RARITY:</b> {rarity})\n"
            f"<b>Globally Caught:</b> {global_total} times"
            f"{top_text}"
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

    cache_time = 300 if search_harem else 1  # Set to 1 for global search so newly added characters appear fast
    
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
        total_fallback = []
        for char in characters[:50]:
            char_id = str(char.get('id', 'N/A'))
            name = char.get('name', 'Unknown')
            anime = char.get('anime', 'Unknown')
            rarity = str(char.get('rarity', 'Common'))
            
            cap = (
                f"OwO! Search Result!\n\n"
                f"<b>{escape_markdown(anime)}</b>\n\n"
                f"{char_id}: <b>{escape_markdown(name)}</b>\n\n"
                f"<b>Rarity:</b> {rarity}"
            )
            
            total_fallback.append(InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=f"{name} [Text Fallback]",
                description=f"ID: {char_id} • {anime}",
                input_message_content=InputTextMessageContent(cap, parse_mode="HTML")
            ))
            
        try:
            await update.inline_query.answer(total_fallback, cache_time=1)
        except Exception as last_resort:
            print(f"🚨 [INLINE LAST RESORT ERROR] {last_resort}")
    except Exception as e:
        print(f"🚨 [INLINE FATAL] {e}")
