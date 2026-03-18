from telegram import Update
from telegram.ext import ContextTypes
from bot.database.mongo import users_collection, characters_collection
from bot.modules.admin import check_admin
from bot.utils.formatters import escape_markdown
from bot.modules.trade import get_char_by_query

async def cgrant_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner/Sudo command to grant characters or view user collections."""
    if not await check_admin(update):
        return

    if not context.args:
        await update.message.reply_text(
            "<b>Usage:</b>\n"
            "• <code>/cgrant &lt;char_id&gt;</code> (replying to a user) - Give character\n"
            "• <code>/cgrant &lt;char_id&gt; &lt;user_id&gt;</code> - Give character\n"
            "• <code>/cgrant &lt;user_id&gt;</code> - View user's grabbed characters",
            parse_mode="HTML"
        )
        return

    # Parse arguments
    ids_to_grant = []
    target_user_id = None
    
    # Check if last argument is a user ID (numeric and not a range/single char id)
    # Actually, let's keep it simple: 
    # If replying: all args are character IDs
    # If not replying: last arg is user ID, rest are character IDs
    
    reply_target = update.message.reply_to_message.from_user if update.message.reply_to_message else None
    
    if reply_target:
        target_user_id = reply_target.id
        char_queries = context.args
    else:
        if len(context.args) < 1:
            return # Usage handled above
        
        # If there's only one arg and it's numeric, it might be a View request
        if len(context.args) == 1 and context.args[0].isdigit():
             try:
                target_id = int(context.args[0])
                # Check if it's a valid character ID first
                char_exists = await characters_collection.find_one({"id": str(target_id)})
                if not char_exists:
                    # Treat as View Collection request
                    user_data = await users_collection.find_one({"id": target_id})
                    if not user_data or not user_data.get("waifus"):
                        await update.message.reply_text(f"❌ User <code>{target_id}</code> has no characters.", parse_mode="HTML")
                        return
                    
                    waifus = user_data["waifus"]
                    char_cursor = characters_collection.find({"id": {"$in": waifus}})
                    char_names = []
                    async for c in char_cursor:
                        char_names.append(f"• {c['id']}: {c['name']}")
                    
                    if not char_names:
                        char_names = [f"• {wid}" for wid in waifus]

                    msg = f"👤 <b>Collection for {target_id}</b>:\n\n" + "\n".join(char_names[:50])
                    if len(char_names) > 50:
                        msg += f"\n\n<i>...and {len(char_names) - 50} more</i>"
                    
                    await update.message.reply_text(msg, parse_mode="HTML")
                    return
             except Exception: pass

        # Multi-arg grant: last one is User ID
        if len(context.args) >= 2:
            try:
                target_user_id = int(context.args[-1])
                char_queries = context.args[:-1]
            except ValueError:
                await update.message.reply_text("❌ Target User ID must be numeric.")
                return
        else:
            await update.message.reply_text("❌ Usage: <code>/cgrant &lt;IDs&gt; &lt;user_id&gt;</code>", parse_mode="HTML")
            return

    # Parse char_queries (can be "1,2,3" or "10-20" or "single_id")
    final_ids = []
    for query in char_queries:
        if "," in query:
            final_ids.extend([q.strip() for q in query.split(",") if q.strip()])
        elif "-" in query:
            try:
                start_s, end_s = query.split("-")
                start, end = int(start_s), int(end_s)
                final_ids.extend([str(i) for i in range(min(start, end), max(start, end) + 1)])
            except ValueError:
                final_ids.append(query)
        else:
            final_ids.append(query)

    # Resolve IDs to character objects
    granted_chars = []
    failed_queries = []
    
    for q in final_ids:
        char_data = await get_char_by_query(q)
        if char_data:
            granted_chars.append(char_data)
        else:
            failed_queries.append(q)

    if not granted_chars:
        await update.message.reply_text(f"❌ No characters found for queries: {', '.join(failed_queries[:10])}")
        return

    # Batch update
    char_ids_to_add = [c['id'] for c in granted_chars]
    await users_collection.update_one(
        {"id": target_user_id},
        {"$push": {"waifus": {"$each": char_ids_to_add}}},
        upsert=True
    )

    names_list = ", ".join([f"<b>{escape_markdown(c['name'])}</b>" for c in granted_chars[:10]])
    count = len(granted_chars)
    msg = f"✅ Granted {count} characters to " + (f"user <code>{target_user_id}</code>" if not reply_target else f"{escape_markdown(reply_target.first_name)}")
    msg += f"\n\nCharacters: {names_list}"
    if count > 10:
        msg += f"<i> and {count-10} others...</i>"
    
    if failed_queries:
        msg += f"\n\n⚠️ Failed to find: {', '.join(failed_queries[:5])}"

    await update.message.reply_text(msg, parse_mode="HTML")
