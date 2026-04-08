import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from bot.database.mongo import groups_collection
from bot.utils.spawning import get_random_character
from bot.utils.formatters import generate_spawn_message, escape_markdown

# In-memory store for active spawns {chat_id: character_doc}
active_spawns = {}
# Dictionary to store despawn tasks: {chat_id: asyncio.Task}
despawn_tasks = {}

async def despawn_timer(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Wait for 5 minutes and remove the active character if not caught."""
    await asyncio.sleep(300) # 5 minutes
    
    if chat_id in active_spawns:
        character = active_spawns.pop(chat_id)
        # Delete original spawn message
        try:
            await context.bot.delete_message(chat_id, character['spawn_message_id'])
        except Exception:
            pass
            
        # Notify that character ran away
        text = f"The character <b>{character['name']}</b> of <b>{character['anime']}</b> has run away!"
        await context.bot.send_message(chat_id, text, parse_mode="HTML")
        
        # Clean up task
        if chat_id in despawn_tasks:
            del despawn_tasks[chat_id]


async def spawn_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Spawns a character in the group."""
    chat_id = update.effective_chat.id
    # Allow concurrent spawns if threshold is hit rapidly or changetime is 1

    character = await get_random_character()
    if not character:
        return # No characters in DB yet

    # Send spawn message
    text = generate_spawn_message(character['name'], character['rarity'])
    file_type = character.get('file_type', 'photo')
    if file_type == 'video':
        message = await context.bot.send_video(
            chat_id=chat_id,
            video=character['file_id'],
            caption=text,
            parse_mode="HTML"
        )
    elif file_type == 'document':
        message = await context.bot.send_document(
            chat_id=chat_id,
            document=character['file_id'],
            caption=text,
            parse_mode="HTML"
        )
    else:
        message = await context.bot.send_photo(
            chat_id=chat_id,
            photo=character['file_id'],
            caption=text,
            parse_mode="HTML"
        )

    # Register active spawn and start despawn timer
    character['spawn_message_id'] = message.message_id
    active_spawns[chat_id] = character
    
    # Cancel existing task if any
    if chat_id in despawn_tasks:
        despawn_tasks[chat_id].cancel()
        
    # Start new despawn task
    task = asyncio.create_task(despawn_timer(chat_id, context))
    despawn_tasks[chat_id] = task
    

async def group_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Listens to all group messages, increments counter, drops waifu when threshold hit."""
    if not update.effective_chat or update.effective_chat.type not in ['group', 'supergroup']:
        return
        
    if not update.message or update.message.text and update.message.text.startswith('/'):
        # Ignore commands for counting
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Global Spawn Check
    from bot.database.mongo import settings_collection
    global_settings = await settings_collection.find_one({"id": "global"})
    if global_settings and not global_settings.get("spawn_enabled", True):
        return
    
    # check block status & consecutive spamming
    from bot.utils.spam import get_block_remaining, check_and_warn_spam
    user_first_name = update.effective_user.first_name
    
    is_spamming = await check_and_warn_spam(chat_id, user_id, user_first_name, update.message)
    if is_spamming or await get_block_remaining(user_id) > 0:
        print(f"Ignored message from blocked/spamming user {user_id} for spawn count.")
        return

    # Upsert group stats manually to avoid unsupported return_document=True error
    await groups_collection.update_one(
        {"id": chat_id},
        {"$inc": {"message_count": 1}, "$setOnInsert": {"spawn_target": 70}},
        upsert=True
    )
    
    group = await groups_collection.find_one({"id": chat_id})
    if not group:
        print("Failed to find group in DB post-upsert")
        return

    count = group.get("message_count", 0)
    
    # Simple logic: Group Specific -> Default (75)
    target = group.get("spawn_target", 70)
    
    print(f"DEBUG [SPAWN]: Chat {chat_id} | Count: {count} | Target: {target}")

    if count >= target:
        print(f"Threshold reached in {chat_id}! Spawning character.")
        # Reset counter
        await groups_collection.update_one({"id": chat_id}, {"$set": {"message_count": 0}})
        # Spawn
        await spawn_character(update, context)
    else:
        print(f"Threshold not reached in {chat_id}: {count}/{target}")
