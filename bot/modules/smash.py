from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import random
import time
from bot.database.mongo import users_collection, characters_collection, settings_collection
from bot.utils.formatters import escape_markdown

# Temporary storage for active proposals: {user_id: {"type": game_type, "time": timestamp, "char_data": data}}
active_games = {}

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, game_type: str = "smash"):
    """Generic handler for Smash game."""
    user = update.effective_user
    user_id = user.id
    now = time.time()
    
    # 0. Check global toggle
    settings = await settings_collection.find_one({"id": "global"})
    if settings and not settings.get("games_enabled", True):
        await update.message.reply_text("❌ The Smash game is currently disabled by the owner.")
        return

    # 1. Check for active proposal
    if user_id in active_games:
        entry = active_games[user_id]
        if now - entry["time"] < 900:
            await update.message.reply_text(
                f"<b>CANCEL! YOU HAVE ACTIVE SMASH PORPOSE AVAILABLE.</b>\n\n"
                "Use /cancel if you can't find the message.",
                parse_mode="HTML"
            )
            return
        else:
            del active_games[user_id]

    # 2. Check cooldown (5 minutes = 300 seconds)
    user_data = await users_collection.find_one({"id": user_id})
    cooldown_key = f"last_smash"
    last_run = user_data.get(cooldown_key, 0) if user_data else 0
    
    if now - last_run < 300:
        remaining = int(300 - (now - last_run))
        await update.message.reply_text(f"⏳ <b>Cooldown!</b> Please wait {remaining // 60}m {remaining % 60}s before another smash.", parse_mode="HTML")
        return

    # 3. Pull a random character of restricted rarity
    allowed_rarities = ["Common", "Uncommon", "Rare", "Legendary"]
    pipeline = [
        {"$match": {"rarity": {"$in": allowed_rarities}}},
        {"$sample": {"size": 1}}
    ]
    chars = await characters_collection.aggregate(pipeline).to_list(1)
    
    if not chars:
        await update.message.reply_text("❌ No eligible characters found in the database.")
        return
        
    char_data = chars[0]
    
    # Update cooldown immediately to prevent spam
    await users_collection.update_one(
        {"id": user_id},
        {"$set": {cooldown_key: now}},
        upsert=True
    )

    # 5. Build UI
    rarity = char_data.get('rarity', 'Common')
    emoji_map = {"Common": "🔵", "Uncommon": "🟣", "Rare": "🟠", "Legendary": "🟡"}
    r_emoji = emoji_map.get(rarity, "💮")
    
    title = "Sᴍᴀꜱʜ Pʀᴏᴘᴏꜱᴇ"
    
    text = (
        f"💥 <b>{title}!</b>\n\n"
        f"👤 <b>Player:</b> {escape_markdown(user.first_name)}\n"
        f"🌸 <b>Character:</b> {escape_markdown(char_data['name'])}\n"
        f"📺 <b>Anime:</b> {escape_markdown(char_data['anime'])}\n"
        f"✨ <b>Rarity:</b> ({r_emoji} {rarity})\n\n"
        f"<i>Will you smash or pass?</i>\n\n"
        f"➥ <i>Use /cancel to stop this proposal.</i>"
    )
    
    keyboard = [
        [
            InlineKeyboardButton(f"💥 SMASH", callback_data=f"smash_confirm_{user_id}"),
            InlineKeyboardButton("❌ CANCEL", callback_data=f"smash_cancel_{user_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    active_games[user_id] = {"type": "smash", "time": now, "char": char_data}
    
    try:
        if char_data.get('file_id'):
            file_type = char_data.get('file_type', 'photo')
            if file_type == 'video':
                await update.message.reply_video(video=char_data['file_id'], caption=text, reply_markup=reply_markup, parse_mode="HTML")
            elif file_type == 'document':
                 await update.message.reply_document(document=char_data['file_id'], caption=text, reply_markup=reply_markup, parse_mode="HTML")
            else:
                await update.message.reply_photo(photo=char_data['file_id'], caption=text, reply_markup=reply_markup, parse_mode="HTML")
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception as e:
        if user_id in active_games:
            del active_games[user_id]
        print(f"Error sending game media: {e}")
        await update.message.reply_text(f"❌ Error starting game: {e}")

async def smash_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await game_cmd(update, context, "smash")

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any active smash game."""
    user_id = update.effective_user.id
    if user_id in active_games:
        del active_games[user_id]
        await update.message.reply_text("✅ Your active smash proposal has been cancelled.")
    else:
        await update.message.reply_text("❌ You have no active proposals to cancel.")

async def _edit_game_msg(query, text):
    """Helper to edit either caption or text."""
    try:
        if query.message.caption:
            await query.edit_message_caption(caption=text, parse_mode="HTML")
        else:
            await query.edit_message_text(text=text, parse_mode="HTML")
    except Exception as e:
        print(f"Error editing game msg: {e}")

async def game_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle smash/cancel button clicks."""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    if not data.startswith("smash_"):
        return

    parts = data.split("_")
    action = parts[1]
    try:
        owner_id = int(parts[2])
    except (IndexError, ValueError):
        return

    if user_id != owner_id:
        await query.answer(f"❌ This is not your smash!", show_alert=True)
        return

    if action == "cancel":
        if owner_id in active_games:
            del active_games[owner_id]
        await _edit_game_msg(query, f"❌ <b>SMASH Proposal Cancelled.</b>")
        await query.answer("Cancelled.")
        return

    if action == "confirm":
        if owner_id not in active_games:
            await query.answer("❌ Proposal expired or already handled.", show_alert=True)
            return
            
        entry = active_games[owner_id]
        char_data = entry["char"]
        
        # 70% Win / 30% Loss logic
        win = random.random() < 0.70
        
        if win:
            await users_collection.update_one(
                {"id": owner_id},
                {"$push": {"waifus": char_data['id']}},
                upsert=True
            )
            text = f"🎯 <b>Sᴜᴄᴄᴇꜱꜱғᴜʟ SMASH!</b>\n\nYou have added <b>{escape_markdown(char_data['name'])}</b> to your harem! 🎉"
            await query.answer(f"Character added to harem!")
        else:
            text = f"💔 <b>SMASH Fᴀɪʟᴇᴅ!</b>\n\nOh no! <b>{escape_markdown(char_data['name'])}</b> slipped away..."
            await query.answer(f"Better luck next time!")

        del active_games[owner_id]
        await _edit_game_msg(query, text)
