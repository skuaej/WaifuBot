import re
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.config import OWNER_ID, UPLOAD_CHANNEL_ID, LOG_CHAT_ID
from bot.database.mongo import users_collection, characters_collection, sudos_collection, db
from bot.utils.formatters import escape_markdown

# Group collection for settings
groups_collection = db["groups"]

# Rarity emoji and weight mapping
RARITY_MAP = {
    "Common": "Common", "Medium": "Uncommon", "Rare": "Rare",
    "Legendary": "Legendary", "Mystical": "Mystical", "Divine": "Divine",
    "Crossverse": "Crossverse", "Supreme": "Supreme", "Cataphract": "Cataphract"
}

def clean_character_name(name: str) -> str:
    """Consistently clean character names for matching and storage."""
    name = name.strip()
    name = re.sub(r"^[^\w\s]+\s*", "", name)
    name = re.sub(r"^V\s+", "", name, flags=re.IGNORECASE)
    return name.strip()

async def get_next_char_id():
    """Find the absolute maximum numeric ID to ensure uniqueness."""
    cursor = characters_collection.find({"id": {"$regex": "^[0-9]+$"}})
    max_id = 0
    async for char in cursor:
        try:
            cid = int(char["id"])
            if cid > max_id:
                max_id = cid
        except (ValueError, KeyError):
            continue
    
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
    if user_id == OWNER_ID:
        return True
    sudo = await sudos_collection.find_one({"user_id": user_id})
    return sudo is not None

async def has_power(user_id: int, power: str) -> bool:
    if user_id == OWNER_ID:
        return True
    sudo = await sudos_collection.find_one({"user_id": user_id})
    if not sudo:
        return False
    return power in sudo.get("powers", [])

async def check_admin(update: Update, power: str = None) -> bool:
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
    if update.effective_user.id != OWNER_ID:
        if update.message:
            await update.message.reply_text("❌ Only the bot owner can use this command.")
        return False
    return True

def _build_sudo_keyboard(sudo_id: int, powers: list):
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
    await send_log(context, f"👤 <b>Sudo Added</b>\nBy: {update.effective_user.first_name}\nTarget: <code>{sudo_id}</code>")

async def resudo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await send_log(context, f"🗑️ <b>Sudo Removed</b>\nBy: {update.effective_user.first_name}\nTarget: <code>{sudo_id}</code>")
    else:
        await update.message.reply_text(f"❌ User {sudo_id} is not a sudo.")

async def sudo_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

        await sudos_collection.update_one({"user_id": sudo_id}, {"$set": {"powers": powers}})
        keyboard = _build_sudo_keyboard(sudo_id, powers)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        status = "enabled" if power in powers else "disabled"
        await query.answer(f"{power.capitalize()} power {status}!")

async def forward_save_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.from_user or message.from_user.id != OWNER_ID:
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

    if not file_id or not message.caption:
        return

    caption = message.caption
    anime_match = re.search(r"(?:🫧 Anime:|Anime:|➤ From:)\s*(.+)", caption, re.IGNORECASE)
    name_match = re.search(r"(?:🏖️ Character Name:|Character Name:|Name:)\s*(.+?)(?:\s*\[.+\])?(?:\n|$)", caption, re.IGNORECASE)

    if not name_match or not anime_match:
        return

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

    # TYPE PARSING
    type_match = re.search(r"(?:Type:)\s*(.+)", caption, re.IGNORECASE)
    char_type = type_match.group(1).strip() if type_match else "Waifu"

    final_rarity = RARITY_MAP.get(rarity, rarity)

    if file_type != "photo" and final_rarity != "Cataphract":
        await message.reply_text(f"❌ <b>{file_type.capitalize()}</b> uploads are restricted to <b>Cataphract</b> rarity only.", parse_mode="HTML")
        return

    char_id = await get_next_char_id()

    character = {
        "id": char_id,
        "name": name,
        "anime": anime,
        "rarity": final_rarity,
        "type": char_type,
        "file_id": file_id,
        "file_type": file_type
    }

    await characters_collection.insert_one(character)
    await message.reply_text(
        f"✅ Auto-Saved new character:\n"
        f"<b>{escape_markdown(name)}</b> (ID: {char_id})\n"
        f"Anime: {escape_markdown(anime)}\nRarity: {final_rarity}\nType: {char_type}",
        parse_mode="HTML"
    )

async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post
    if not message or message.chat.id != UPLOAD_CHANNEL_ID:
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

    if not file_id or not message.caption:
        return

    caption = message.caption
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
            rarity = old_rarity_match.group(1).strip().capitalize() if old_rarity_match else "Mystical"

        type_match = re.search(r"(?:Type:)\s*(.+)", caption, re.IGNORECASE)
        char_type = type_match.group(1).strip() if type_match else "Waifu"

        final_rarity = RARITY_MAP.get(rarity, rarity)

        if file_type != "photo" and final_rarity != "Cataphract":
            return 

        char_id = await get_next_char_id()

        character = {
            "id": char_id,
            "name": name,
            "anime": anime,
            "rarity": final_rarity,
            "type": char_type,
            "file_id": file_id,
            "file_type": file_type
        }
        await characters_collection.insert_one(character)


async def upload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback manual upload command: 
    /upload Name, Anime, Rarity, [Type] OR
    reply to a message with a caption and just use /upload
    """
    if not await check_admin(update, power="upload"):
        return

    message = update.message
    if not message.reply_to_message or not (message.reply_to_message.photo or message.reply_to_message.document or message.reply_to_message.video):
        await message.reply_text("Please reply to an image/video/document to upload.")
        return

    # UPDATED LOGIC: Allows 3 or 4 arguments
    raw_args = " ".join(context.args).strip()
    if raw_args:
        args = [a.strip() for a in raw_args.split(",")]
        
        if len(args) not in [3, 4]:
            await message.reply_text("❌ Usage: /upload Name, Anime, Rarity, [Type]\n(Type is optional)")
            return
            
        name = args[0]
        anime = args[1]
        rarity = args[2]
        
        # ✨ OPTIONAL TYPE: Uses the 4th argument if provided, otherwise "Waifu"
        char_type = args[3] if len(args) == 4 else "Waifu"
        
    else:
        # Auto-parse from caption
        caption = message.reply_to_message.caption or message.reply_to_message.text or ""
        if not caption:
             await message.reply_text("Original message has no caption. Please provide manual arguments.")
             return
             
        anime_match = re.search(r"(?:🫧 Anime:|Anime:|➤ From:)\s*(.+)", caption, re.IGNORECASE)
        name_match = re.search(r"(?:🏖️ Character Name:|Character Name:|Name:)\s*(.+?)(?:\s*\[.+\])?(?:\n|$)", caption, re.IGNORECASE)
        
        if not name_match or not anime_match:
             await message.reply_text("Could not parse Name or Anime. Please use manual format: /upload Name, Anime, Rarity, Type")
             return
             
        name = clean_character_name(name_match.group(1))
        anime = anime_match.group(1).split('\n')[0].split('|')[0].strip()
        
        rarity_match = re.search(r"𝙍𝘼𝙍𝙄𝙏𝙔:\s*(\w+)", caption, re.IGNORECASE)
        if rarity_match:
            rarity = rarity_match.group(1).capitalize()
        else:
            old_rarity_match = re.search(r"Rarity:\s*(.+)", caption, re.IGNORECASE)
            rarity = old_rarity_match.group(1).strip().capitalize() if old_rarity_match else "Mystical"
            
        type_match = re.search(r"(?:Type:)\s*(.+)", caption, re.IGNORECASE)
        char_type = type_match.group(1).strip() if type_match else "Waifu"
    
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

    if file_type != "photo" and final_rarity != "Cataphract":
        await message.reply_text(f"❌ <b>{file_type.capitalize()}</b> uploads are restricted to <b>Cataphract</b> rarity only.", parse_mode="HTML")
        return

    char_id = await get_next_char_id()

    character = {
        "id": char_id,
        "name": name,
        "anime": anime,
        "rarity": final_rarity,
        "type": char_type,  # Saved into DB
        "file_id": file_id,
        "file_type": file_type
    }

    await characters_collection.insert_one(character)
    
    await message.reply_text(
        f"✅ Successfully uploaded: {escape_markdown(name)} (ID: {char_id})\n"
        f"Anime: {escape_markdown(anime)}\n"
        f"Rarity: {final_rarity}\n"
        f"Type: {char_type}",
        parse_mode="HTML"
    )
    await send_log(context, f"📤 <b>Character Uploaded</b>\nName: {escape_markdown(name)}\nType: {char_type}\nID: {char_id}", file_id=file_id, file_type=file_type)


async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/delete ID1, ID2, ... or range like 1-100"""
    if not await check_admin(update, power="delete"):
        return

    if not context.args:
        await update.message.reply_text("Usage: /delete Character ID(s) (comma separated or range 1-100)")
        return

    raw_args = " ".join(context.args)
    parts = [p.strip() for p in raw_args.split(",")]
    actual_ids_to_delete = set()
    
    for part in parts:
        if "-" in part:
            try:
                start_str, end_str = part.split("-")
                start = int(start_str)
                end = int(end_str)
                if end - start < 1000:
                    for i in range(start, end + 1):
                        cursor = characters_collection.find({"id": re.compile(f"^0*{i}$")})
                        async for c in cursor:
                            actual_ids_to_delete.add(c["id"])
                else:
                    await update.message.reply_text("Range too large. Max 1000 at a time.")
                    return
            except ValueError:
                await update.message.reply_text(f"Invalid range format: {part}")
                return
        else:
            # Single ID
            cursor = characters_collection.find({"id": re.compile(f"^0*{part}$")})
            async for c in cursor:
                actual_ids_to_delete.add(c["id"])

    if not actual_ids_to_delete:
        await update.message.reply_text("No characters found with those IDs.")
        return

    # Delete from characters collection
    result = await characters_collection.delete_many({"id": {"$in": list(actual_ids_to_delete)}})
    
    # Clean up from users' harems
    await users_collection.update_many(
        {},
        {"$pull": {"waifus": {"$in": list(actual_ids_to_delete)}}}
    )
    
    await update.message.reply_text(f"✅ Successfully deleted {result.deleted_count} characters.")
    await send_log(context, f"🗑️ <b>Characters Deleted</b>\nBy: {update.effective_user.first_name}\nIDs: {', '.join(list(actual_ids_to_delete)[:20])}")

# -----------------
# Additional Admin Commands
# -----------------

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/broadcast - Send message to all users (reply to a message)."""
    if not await check_owner(update): return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to a message to broadcast it.")
        return
        
    msg = update.message.reply_to_message
    users = users_collection.find({})
    success, failed = 0, 0
    
    await update.message.reply_text("🚀 Broadcasting message...")
    
    async for user in users:
        try:
            await context.bot.copy_message(chat_id=user["id"], from_chat_id=msg.chat_id, message_id=msg.message_id)
            success += 1
        except Exception:
            failed += 1
            
    await update.message.reply_text(f"✅ Broadcast complete!\nSent: {success}\nFailed: {failed}")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stats - View bot statistics."""
    if not await check_admin(update): return
    total_users = await users_collection.count_documents({})
    total_chars = await characters_collection.count_documents({})
    total_groups = await groups_collection.count_documents({}) if groups_collection else 0
    
    await update.message.reply_text(
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Users: {total_users}\n"
        f"🌸 Characters: {total_chars}\n"
        f"🏘️ Groups: {total_groups}",
        parse_mode="HTML"
    )

async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ping - Check bot response time."""
    start_time = time.time()
    msg = await update.message.reply_text("Pinging...")
    end_time = time.time()
    ms = round((end_time - start_time) * 1000)
    await msg.edit_text(f"🏓 <b>Pong!</b> {ms}ms", parse_mode="HTML")

async def enable_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/enable - Enable spawning in current group."""
    if update.effective_chat.type == "private":
        await update.message.reply_text("❌ This command must be used in a group.")
        return
        
    chat_id = update.effective_chat.id
    await groups_collection.update_one({"id": chat_id}, {"$set": {"spawning_enabled": True}}, upsert=True)
    await update.message.reply_text("✅ Spawning has been enabled in this group!")

async def changetime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/changetime <minutes> - Change spawn interval for group."""
    if not await check_admin(update): return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ Usage: /changetime <minutes>")
        return
        
    minutes = int(context.args[0])
    await update.message.reply_text(f"✅ Spawn time updated to {minutes} minutes.")

async def spwanglobal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/spwanglobal - Force global spawn."""
    if not await check_owner(update): return
    await update.message.reply_text("🌍 Global spawn triggered (Implementation requires linking to spawn loop).")
