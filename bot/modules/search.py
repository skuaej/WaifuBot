import re
import uuid
from telegram import Update, InlineQueryResultCachedPhoto, InlineQueryResultCachedVideo, InlineQueryResultCachedMpeg4Gif, InlineQueryResultCachedDocument, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import telegram.error
from bot.database.mongo import characters_collection
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
    from bot.database.mongo import users_collection
    from telegram import InlineQueryResultArticle, InputTextMessageContent
    import telegram.error

    query_text = update.inline_query.query.strip()
    user_id = update.inline_query.from_user.id
    
    if not query_text:
        return
    # Always fetch current user for global catch-tags
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
                # If target not found, fallback to self or empty results
                target_user_data = None 
        else:
            # harem. with nothing after it falls back to self
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

    # Filtration logic with robust ID padding handling
    search_filter = {}
    if query_text:
        regex = re.compile(re.escape(query_text), re.IGNORECASE)
        or_filters = [{"name": regex}, {"anime": regex}]
        
        # Smart ID lookup for digits: find "23" or "0023" etc.
        if query_text.isdigit():
            clean_id = str(int(query_text))
            or_filters.append({"id": re.compile(f"^0*{clean_id}$")})
        else:
            or_filters.append({"id": regex})
            
        search_filter["$or"] = or_filters
    elif not search_harem:
        # Default global search: Show some trending/random characters if query is empty
        # Instead of returning nothing, we give them a sample to look at
        search_filter = {"rarity": {"$in": ["Legendary", "Rare", "Mystical"]}}
    
    if search_harem:
        search_filter["id"] = {"$in": list(normalized_target_owned)}

    # Fetching
    limit_val = 50
    cursor = characters_collection.find(search_filter).limit(limit_val)
    
    if search_harem and not query_text:
        # Show 50 most recent captures in reverse order
        all_chars = await cursor.to_list(limit_val)
        char_dict = {c['id']: c for c in all_chars}
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

    if not characters and not search_harem:
        # Final emergency fallback to some random characters if query returned nothing
        characters = await characters_collection.find().limit(20).to_list(20)

    results = []
    seen = set()
    
    for char in characters:
        char_id = str(char.get('id', 'N/A'))
        name = char.get('name', 'Unknown')
        anime = char.get('anime', 'Unknown')
        norm_id = str(int(char_id)) if char_id.isdigit() else char_id
        
        if norm_id in seen: continue
        seen.add(norm_id)
        
        # Ownership status for the sender
        is_owned = norm_id in normalized_caller_owned
        ownership_tag = " [Caught ✅]" if is_owned else ""
        rarity = char.get('rarity', 'Common')
        
        emoji_map = {
            "Common": "🔵", "Uncommon": "🟣", "Rare": "🟠", 
            "Legendary": "🟡", "Mystical": "💮", "Divine": "⚜️",
            "Crossverse": "⚡", "Supreme": "🤍", "Cataphract": "✨"
        }
        r_emoji = emoji_map.get(rarity, "💮")
        
        caption = (
            f"OwO! Check out this character!{ownership_tag}\n\n"
            f"<b>{escape_markdown(anime)}</b>\n\n"
            f"{char_id}: <b>{escape_markdown(name)}</b>\n\n"
            f"<b>Rarity:</b> ({r_emoji} <b>RARITY:</b> {rarity})"
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

    # ALWAYS send an answer to prevent Spinner Hang
    cache_time = 300 if search_harem else 60
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
        # Universal article fallback: convert ALL results to articles
        total_fallback = []
        for char in characters[:50]:
            char_id = str(char.get('id', 'N/A'))
            name = char.get('name', 'Unknown')
            anime = char.get('anime', 'Unknown')
            rarity = char.get('rarity', 'Common')
            
            # Simple caption
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
