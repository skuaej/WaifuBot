import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from bot.database.mongo import users_collection, characters_collection, captures_collection
from bot.modules.spawn import active_spawns
from bot.utils.spam import is_spammer
from bot.utils.formatters import generate_success_message

async def capture_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /grab and /guess."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    if not context.args:
        await update.message.reply_text("usage by hug grab catch command")
        return

    # Daily Catch Limit (40 per day)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    
    daily_count = await captures_collection.count_documents({
        "user_id": user.id,
        "timestamp": {"$gte": start_of_day}
    })
    
    if daily_count >= 40:
        await update.message.reply_text("❌ <b>You have reached your daily catch limit (40/day)!</b>\nCome back tomorrow! OwO", parse_mode="HTML")
        return

    # Anti-spam
    from bot.utils.spam import get_block_remaining
    remaining = await get_block_remaining(user.id)
    if remaining > 0:
        await update.message.reply_text(
            f"🚫 <b>YOU ARE BLOCKED FROM CATCHING!</b>\n"
            f"<b>Reason:</b> Spamming\n"
            f"<b>Remaining:</b> {remaining // 60}m {remaining % 60}s",
            parse_mode="HTML"
        )
        return

    # Check if a spawn is active in this group
    if chat_id not in active_spawns:
        await update.message.reply_text("not charter here spawn  in this chat")
        return

    guess_name = " ".join(context.args).strip()
    active_char = active_spawns[chat_id]

    # Normalize ID to prevent mismatch (e.g., "0024" vs "24")
    raw_id = active_char['id']
    normalized_id = str(int(raw_id)) if raw_id.isdigit() else raw_id

    # Case-insensitive match with extra stripping and punctuation removal
    def normalize_name(n):
        import string
        n = n.strip().lower()
        # Remove common punctuation
        for char in string.punctuation:
            n = n.replace(char, '')
        return " ".join(n.split()) # Normalize whitespace

    actual_name = normalize_name(active_char['name'])
    user_guess = normalize_name(guess_name)

    # Enhanced Matching Logic:
    # 1. Exact match (normalized)
    # 2. Partial match (user guess is part of the actual name)
    # 3. Handle cases where multiple characters might match by prioritizing the current spawn
    
    is_correct = False
    if user_guess == actual_name:
        is_correct = True
    elif len(user_guess) >= 3 and user_guess in actual_name:
        # Allow partial match if guess is at least 3 chars
        is_correct = True
    
    if is_correct:
        # Correct guess! Prevent multiple winners by popping immediately.
        char_data = active_spawns.pop(chat_id)
        

        # Update user in DB
        # We store normalized character ID in their waifus list.
        # User wants to be able to catch the same character multiple times (unlimited grabs).
        from bot.database.mongo import captures_collection
        
        await asyncio.gather(
            users_collection.update_one(
                {"id": user.id},
                {
                    "$set": {"name": user.first_name, "username": user.username},
                    "$push": {"waifus": normalized_id},
                    "$inc": {"coins": 100} # Award 100 coins for catching
                },
                upsert=True
            ),
            characters_collection.update_one(
                {"id": normalized_id},
                {"$inc": {"caught_count": 1}}
            ),
            captures_collection.insert_one({
                "user_id": user.id,
                "chat_id": chat_id,
                "char_id": normalized_id,
                "timestamp": update.message.date
            })
        )

        # Detect Command for Success Message (grab -> grabbed, hug -> hugged, etc.)
        raw_command = update.message.text.split()[0][1:].lower().split('@')[0]
        action_map = {
            "grab": "ɢʀᴀʙʙᴇᴅ",
            "hug": "ʜᴜɢɢᴇᴅ",
            "catch": "ᴄᴀᴜɢʜᴛ",
            "guess": "ɢᴜᴇssᴇᴅ"
        }
        action = action_map.get(raw_command, "ɢᴏᴛ")

        success_msg = generate_success_message(
            user.id,
            user.first_name, 
            char_data['name'], 
            char_data['anime'], 
            char_data['rarity'],
            action
        )
        await update.message.reply_text(success_msg, parse_mode="HTML")
    else:
        # Incorrect guess
        await update.message.reply_text("incorrect name try again ..")
