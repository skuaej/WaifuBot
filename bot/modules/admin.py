Import re
from telegram import Update
from telegram.ext import ContextTypes
from bot.config import OWNER_ID, UPLOAD_CHANNEL_ID, LOG_CHAT_ID
from bot.database.mongo import users_collection, characters_collection, sudos_collection
from bot.utils.formatters import escape_markdown

# Rarity emoji and weight mapping
RARITY_MAP = {
    "Common": "Common", "Medium": "Uncommon", "Rare": "Rare",
    "Legendary": "Legendary", "Mystical": "Mystical", "Divine": "Divine",
    "Crossverse": "Crossverse", "Supreme": "Supreme", "Cataphract": "Cataphract"
}

def clean_character_name(name: str) -> str:
    """Consistently clean character names for matching and storage."""
    name = name.strip()
    # Remove decorative prefixes (symbols, "V ", etc.)
    name = re.sub(r"^[^\w\s]+\s*", "", name)
    name = re.sub(r"^V\s+", "", name, flags=re.IGNORECASE)
    return name.strip()

async def get_next_char_id():
    """Find the absolute maximum numeric ID to ensure uniqueness."""
    # Fetch characters with numeric IDs
    cursor = characters_collection.find({"id": {"$regex": "^[0-9]+$"}})
    max_id = 0
    async for char in cursor:
        try:
            cid = int(char["id"])
            if cid > max_id:
                max_id = cid
        except (ValueError, KeyError):
            continue
    
    # Also check total count as a safety measure
    count = await characters_collection.count_documents({})
    max_id = max(max_id, count)
    
    return str(max_id + 1)

async def send_log(context: ContextTypes.DEFAULT_TYPE, text: str, file_id: str = None, file_type: str = "photo"):
    """Send a log message (with optional media) to the log chat."""
    if not LOG_CHAT_ID:
        return
    try:
        if file_id:
            if file_type == "video":
                await context.bot.send_video(chat_id=LOG_CHAT_ID, video=file_id, caption=text, parse_mode="HTML")
            elif file_type == "document":
                await context.bot.send_document(chat_id=LOG_CHAT_ID, document=file_id, caption=text, parse_mode="HTML")
            else:
                await context.bot.send_photo(chat_id=LOG_CHAT_ID, photo=file_id, caption=text, parse_mode="HTML")
        else:
            await context.bot.send_message(chat_id=LOG_CHAT_ID, text=text, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending log: {e}")

async def is_sudo(user_id: int) -> bool:
    """Check if a user is a sudo user or the owner."""
    if user_id == OWNER_ID:
        return True
    sudo = await sudos_collection.find_one({"user_id": user_id})
    return sudo is not None

async def has_power(user_id: int, power: str) -> bool:
    """Check if a user has a specific power."""
    if user_id == OWNER_ID:
        return True
    sudo = await sudos_collection.find_one({"user_id": user_id})
    if not sudo:
        return False
    return power in sudo.get("powers", [])

async def check_admin(update: Update, power: str = None) -> bool:
    """Check if the user is the owner or a sudo with the required power."""
    user_id = update.effective_user.id
    if user_id == OWNER_ID:
        return True
    if power:
        if await has_power(user_id, power):
            return True
    elif await is_sudo(user_id):
        return True
    if update.message:
        await update.message.reply_text("❌ You don't have permission to use this command.")
    return False

async def check_owner(update: Update) -> bool:
    """Check if the user is the owner only (not sudo)."""
    if update.effective_user.id != OWNER_ID:
        if update.message:
            await update.message.reply_text("❌ Only the bot owner can use this command.")
        return False
    return True

def _build_sudo_keyboard(sudo_id: int, powers: list):
    """Build inline keyboard for managing sudo powers."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    upload_status = "✅" if "upload" in powers else "❌"
    delete_status = "✅" if "delete" in powers else "❌"
    keyboard = [
        [InlineKeyboardButton(f"{upload_status} Upload Power", callback_data=f"sudo_toggle_{sudo_id}_upload")],
        [InlineKeyboardButton(f"{delete_status} Delete Power", callback_data=f"sudo_toggle_{sudo_id}_delete")],
        [InlineKeyboardButton("🗑️ Remove Sudo", callback_data=f"sudo_remove_{sudo_id}")],
        [InlineKeyboardButton("✅ Done", callback_data="sudo_done")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def addsudo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/addsudo <telegram_id> - Add a sudo user with powers (owner only)."""
    if not await check_owner(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /addsudo <telegram_id>")
        return

    try:
        sudo_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid Telegram user ID.")
        return

    existing = await sudos_collection.find_one({"user_id": sudo_id})
    if existing:
        powers = existing.get("powers", [])
        keyboard = _build_sudo_keyboard(sudo_id, powers)
        await update.message.reply_text(
            f"⚙️ Manage powers for sudo <code>{sudo_id}</code>:",
            parse_mode="HTML", reply_markup=keyboard
        )
        return

    await sudos_collection.insert_one({"user_id": sudo_id, "powers": ["upload", "delete"]})
    keyboard = _build_sudo_keyboard(sudo_id, ["upload", "delete"])
    await update.message.reply_text(
        f"✅ User <code>{sudo_id}</code> added as sudo.\n⚙️ Manage powers:",
        parse_mode="HTML", reply_markup=keyboard
    )
    await send_log(context, f"👤 <b>Sudo Added</b>\nBy: {update.effective_user.first_name} (<code>{update.effective_user.id}</code>)\nTarget: <code>{sudo_id}</code>")

async def resudo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/resudo <telegram_id> - Remove a sudo user (owner only)."""
    if not await check_owner(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /resudo <telegram_id>")
        return

    try:
        sudo_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid Telegram user ID.")
        return

    result = await sudos_collection.delete_one({"user_id": sudo_id})
    if result.deleted_count > 0:
        await update.message.reply_text(f"✅ User <code>{sudo_id}</code> has been removed from sudo.", parse_mode="HTML")
        await send_log(context, f"🗑️ <b>Sudo Removed</b>\nBy: {update.effective_user.first_name} (<code>{update.effective_user.id}</code>)\nTarget: <code>{sudo_id}</code>")
    else:
        await update.message.reply_text(f"❌ User {sudo_id} is not a sudo.")

async def sudo_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button clicks for sudo power management."""
    query = update.callback_query
    user_id = query.from_user.id

    if user_id != OWNER_ID:
        await query.answer("❌ Only the owner can manage sudos.", show_alert=True)
        return

    data = query.data

    if data == "sudo_done":
        await query.edit_message_text("✅ Sudo management complete.")
        await query.answer()
        return

    if data.startswith("sudo_remove_"):
        sudo_id = int(data.split("_")[2])
        await sudos_collection.delete_one({"user_id": sudo_id})
        await query.edit_message_text(f"🗑️ User <code>{sudo_id}</code> removed from sudo.", parse_mode="HTML")
        await query.answer("Removed!")
        return

    if data.startswith("sudo_toggle_"):
        parts = data.split("_")
        sudo_id = int(parts[2])
        power = parts[3]

        sudo = await sudos_collection.find_one({"user_id": sudo_id})
        if not sudo:
            await query.answer("❌ User is no longer a sudo.", show_alert=True)
            return

        powers = sudo.get("powers", [])
        if power in powers:
            powers.remove(power)
        else:
            powers.append(power)

        await sudos_collection.update_one(
            {"user_id": sudo_id},
            {"$set": {"powers": powers}}
        )

        keyboard = _build_sudo_keyboard(sudo_id, powers)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        status = "enabled" if power in powers else "disabled"
        await query.answer(f"{power.capitalize()} power {status}!")
        await send_log(context, f"⚙️ <b>Sudo Power Toggle</b>\nSudo: <code>{sudo_id}</code>\nPower: {power.capitalize()} is now {status.upper()}")

async def forward_save_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Auto-saves characters when the owner sends/forwards an image with caption.
    Works in private chat, groups, and channels.
    """
    message = update.message
    if not message:
        return

    print(f"[AUTO-SAVE] Triggered! Chat: {message.chat.type} | From: {message.from_user.id if message.from_user else 'None'} | Has photo: {bool(message.photo)} | Has caption: {bool(message.caption)}")

    # Only work for the owner
    if not message.from_user or message.from_user.id != OWNER_ID:
        print(f"[AUTO-SAVE] Skipped - not owner")
        return

    # Must have media
    file_type = "photo"
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"

    if not file_id:
        print(f"[AUTO-SAVE] Skipped - no media")
        return

    # Must have a caption
    caption = message.caption
    if not caption:
        print(f"[AUTO-SAVE] Skipped - no caption")
        return

    print(f"[AUTO-SAVE] Caption: {caption[:80]}...")

    # Parse caption
    anime_match = re.search(r"(?:🫧 Anime:|Anime:|➤ From:)\s*(.+)", caption, re.IGNORECASE)
    name_match = re.search(r"(?:🏖️ Character Name:|Character Name:|Name:)\s*(.+?)(?:\s*\[.+\])?(?:\n|$)", caption, re.IGNORECASE)

    if not name_match or not anime_match:
        print(f"[AUTO-SAVE] Skipped - caption parsing failed. Name: {bool(name_match)}, Anime: {bool(anime_match)}")
        return  # Silently skip if caption doesn't match character format

    name = name_match.group(1).strip()
    anime = anime_match.group(1).split('\n')[0].split('|')[0].strip()

    rarity_match = re.search(r"𝙍𝘼𝙍𝙄𝙏𝙔:\s*(\w+)", caption, re.IGNORECASE)
    if rarity_match:
        rarity = rarity_match.group(1).capitalize()
    else:
        old_rarity_match = re.search(r"Rarity:\s*(.+)", caption, re.IGNORECASE)
        if old_rarity_match:
            rarity = old_rarity_match.group(1).strip().capitalize()
        else:
            rarity = "Mystical"

    final_rarity = RARITY_MAP.get(rarity, rarity)

    # RESTRICTION: Only Cataphract can have video/document
    if file_type != "photo" and final_rarity != "Cataphract":
        print(f"[AUTO-SAVE] Rejected - {file_type} is for Cataphract only.")
        await message.reply_text(f"❌ <b>{file_type.capitalize()}</b> uploads are restricted to <b>Cataphract</b> rarity only.", parse_mode="HTML")
        return

    # Generate next ID
    char_id = await get_next_char_id()

    # Always insert duplicates with new ID as requested
    print(f"DEBUG: Adding character {name} with new ID {char_id}")

    character = {
        "id": char_id,
        "name": name,
        "anime": anime,
        "rarity": final_rarity,
        "file_id": file_id,
        "file_type": file_type
    }

    await characters_collection.insert_one(character)
    await message.reply_text(
        f"✅ Auto-Saved new character:\n"
        f"<b>{escape_markdown(name)}</b> (ID: {char_id})\n"
        f"Anime: {escape_markdown(anime)}\nRarity: {final_rarity}",
        parse_mode="HTML"
    )
    await send_log(context, f"🆕 <b>Auto-Saved Character</b>\nName: {escape_markdown(name)}\nArtist/Anime: {escape_markdown(anime)}\nRarity: {final_rarity}\nID: {char_id}\nTarget: Owner (Auto-Save)", file_id=file_id, file_type=file_type)

async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Auto uploads waifus from a specific channel.
    """
    message = update.channel_post
    print(f"DEBUG: Received channel post in {message.chat.id if message else 'None'}")
    
    if not message or message.chat.id != UPLOAD_CHANNEL_ID:
        print(f"DEBUG: Message skipped. Target: {UPLOAD_CHANNEL_ID}")
        return

    file_type = "photo"
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"

    if not file_id:
        print("DEBUG: No media found in message.")
        return

    caption = message.caption
    print(f"DEBUG: Caption received: {repr(caption)}")

    if not caption:
        return

    # Parse caption
    anime_match = re.search(r"(?:🫧 Anime:|Anime:|➤ From:)\s*(.+)", caption, re.IGNORECASE)
    name_match = re.search(r"(?:🏖️ Character Name:|Character Name:|Name:)\s*(.+?)(?:\s*\[.+\])?(?:\n|$)", caption, re.IGNORECASE)
    
    if name_match and anime_match:
        name = clean_character_name(name_match.group(1))
        anime = anime_match.group(1).split('\n')[0].split('|')[0].strip()
        
        rarity_match = re.search(r"𝙍𝘼𝙍𝙄𝙏𝙔:\s*(\w+)", caption, re.IGNORECASE)
        if rarity_match:
            rarity = rarity_match.group(1).capitalize()
        else:
            old_rarity_match = re.search(r"Rarity:\s*(.+)", caption, re.IGNORECASE)
            if old_rarity_match:
                rarity = old_rarity_match.group(1).strip().capitalize()
            else:
                rarity = "Mystical"

        final_rarity = RARITY_MAP.get(rarity, rarity)

        # RESTRICTION: Only Cataphract can have video/document
        if file_type != "photo" and final_rarity != "Cataphract":
            print(f"DEBUG: Rejected channel post media {file_type} for rarity {final_rarity}")
            return # Silently skip channel posts that don't match rules

        char_id = await get_next_char_id()

        character = {
            "id": char_id,
            "name": name,
            "anime": anime,
            "rarity": final_rarity,
            "file_id": file_id,
            "file_type": file_type
        }

        await characters_collection.insert_one(character)
        await send_log(
            context, 
            f"🆕 <b>Auto-Saved Character</b>\nName: {escape_markdown(name)}\nArtist/Anime: {escape_markdown(anime)}\nRarity: {final_rarity}\nID: {char_id} (from Channel)",
            file_id=file_id,
            file_type=file_type
        )
    else:
        # Optional: log parsing failure
        pass

async def upload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback manual upload command: 
    /upload name, anime, rarity OR
    reply to a message with a caption and just use /upload
    """
    if not await check_admin(update, power="upload"):
        return

    message = update.message
    if not message.reply_to_message or not (message.reply_to_message.photo or message.reply_to_message.document or message.reply_to_message.video):
        await message.reply_text("Please reply to an image/video/document to upload.")
        return

    # Check for manual arguments
    raw_args = " ".join(context.args).strip()
    if raw_args:
        args = raw_args.split(",")
        if len(args) != 3:
            await message.reply_text("Manual Usage: /upload Name, Anime, Rarity\nOr reply to a channel post with a caption with just /upload")
            return
        name, anime, rarity = [a.strip() for a in args]
    else:
        # Auto-parse from caption
        caption = message.reply_to_message.caption or message.reply_to_message.text or ""
        if not caption:
             await message.reply_text("Original message has no caption. Please provide manual arguments.")
             return
             
        anime_match = re.search(r"(?:🫧 Anime:|Anime:|➤ From:)\s*(.+)", caption, re.IGNORECASE)
        name_match = re.search(r"(?:🏖️ Character Name:|Character Name:|Name:)\s*(.+?)(?:\s*\[.+\])?(?:\n|$)", caption, re.IGNORECASE)
        
        if not name_match or not anime_match:
             await message.reply_text("Could not parse Name or Anime from the caption. Please use the manual format: /upload Name, Anime, Rarity")
             return
             
        name = clean_character_name(name_match.group(1))
        anime = anime_match.group(1).split('\n')[0].split('|')[0].strip()
        
        rarity_match = re.search(r"𝙍𝘼𝙍𝙄𝙏𝙔:\s*(\w+)", caption, re.IGNORECASE)
        if rarity_match:
            rarity = rarity_match.group(1).capitalize()
        else:
            # Fallback to old format or Mystical
            old_rarity_match = re.search(r"Rarity:\s*(.+)", caption, re.IGNORECASE)
            if old_rarity_match:
                rarity = old_rarity_match.group(1).strip().capitalize()
            else:
                rarity = "Mystical"
    
    file_type = "photo"
    if message.reply_to_message.photo:
        file_id = message.reply_to_message.photo[-1].file_id
    elif message.reply_to_message.video:
        file_id = message.reply_to_message.video.file_id
        file_type = "video"
    elif message.reply_to_message.document:
        file_id = message.reply_to_message.document.file_id
        file_type = "document"

    final_rarity = RARITY_MAP.get(rarity, rarity.capitalize())

    # RESTRICTION: Only Cataphract can have video/document
    if file_type != "photo" and final_rarity != "Cataphract":
        await message.reply_text(f"❌ <b>{file_type.capitalize()}</b> uploads are restricted to <b>Cataphract</b> rarity only.", parse_mode="HTML")
        return

    char_id = await get_next_char_id()

    character = {
        "id": char_id,
        "name": name,
        "anime": anime,
        "rarity": final_rarity,
        "file_id": file_id,
        "file_type": file_type
    }

    await characters_collection.insert_one(character)
    await message.reply_text(f"✅ Successfully uploaded: {escape_markdown(name)} (ID: {char_id})\nAnime: {escape_markdown(anime)}\nRarity: {final_rarity}", parse_mode="HTML")
    await send_log(
        context, 
        f"📤 <b>Character Uploaded</b>\nBy: {update.effective_user.first_name} (<code>{update.effective_user.id}</code>)\nName: {escape_markdown(name)}\nAnime: {escape_markdown(anime)}\nRarity: {final_rarity}\nID: {char_id}",
        file_id=file_id,
        file_type=file_type
    )

async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/delete ID1, ID2, ... or range like 1-100"""
    if not await check_admin(update, power="delete"):
        return

    if not context.args:
        await update.message.reply_text("Usage: /delete Character ID(s) (comma separated or range 1-100)")
        return

    raw_args = " ".join(context.args)
    parts = [p.strip() for p in raw_args.split(",")]
    
    # We'll first find the actual ID strings in the DB to ensure robust deletion
    actual_ids_to_delete = set()
    
    for part in parts:
        if "-" in part:
            try:
                start_str, end_str = part.split("-")
                start = int(start_str)
                end = int(end_str)
                # For ranges, we look for anything that matches ^0*N$ for N in [start, end]
                # To be efficient for large ranges, we'll search by regex on the ID field
                # If the range is small, we can generate all regexes. For large ranges,
                # we might just fetch all characters and filter in Python or use a clever regex.
                if end - start < 1000:
                    for i in range(start, end + 1):
                        cursor = characte 

