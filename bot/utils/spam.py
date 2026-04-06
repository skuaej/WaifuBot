from telegram import Update
from itertools import groupby
import math
from html import escape 
import random
import time

from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from shivu import collection, user_collection, application
# Make sure this import matches exactly where your blocks_collection is initialized
from bot.database.mongo import blocks_collection 

# --- SPAM CONFIGURATION ---
user_activity = {}
MSG_LIMIT = 5      # 6th message triggers the block
TIME_WINDOW = 1    # within 1 second
BLOCK_DURATION = 60 # Block for 60 seconds (1 minute)

async def get_block_remaining(user_id: int) -> int:
    """Return remaining block time in seconds, or 0 if not blocked."""
    block_data = await blocks_collection.find_one({"id": user_id})
    if not block_data:
        return 0
    
    remaining = int(block_data['until'] - time.time())
    if remaining <= 0:
        await blocks_collection.delete_one({"id": user_id})
        return 0
    return remaining

async def is_spammer(user_id: int) -> int:
    """
    Returns: 0 if clear, 1 if already blocked, 2 if just triggered block.
    """
    now = time.time()
    
    # 1. Check if user is currently blocked in DB
    remaining = await get_block_remaining(user_id)
    if remaining > 0:
        return 1
    
    # 2. Track transient activity
    if user_id not in user_activity:
        user_activity[user_id] = []
    
    # Cleanup timestamps older than the window
    user_activity[user_id] = [t for t in user_activity[user_id] if now - t < TIME_WINDOW]
    user_activity[user_id].append(now)
    
    # 3. Check if they just hit the limit
    if len(user_activity[user_id]) > MSG_LIMIT:
        until = now + BLOCK_DURATION
        await blocks_collection.update_one(
            {"id": user_id},
            {"$set": {"until": until}},
            upsert=True
        )
        return 2 # This indicates the EXACT moment they are blocked
        
    return 0

# --- MAIN COMMAND LOGIC ---

async def harem(update: Update, context: CallbackContext, page=0) -> None:
    user_id = update.effective_user.id

    # --- SPAM BLOCKER LOGIC ---
    spam_status = await is_spammer(user_id)
    
    if spam_status == 1:
        # User is already blocked. Ignore silently so bot doesn't get rate-limited.
        # But answer callbacks so the button loading animation stops.
        if update.callback_query:
            await update.callback_query.answer("You are currently blocked for spam.", show_alert=False)
        return
        
    elif spam_status == 2:
        # User JUST triggered the block right now. Send them the warning.
        if update.message:
            await update.message.reply_text(f"🚨 You are clicking too fast! You have been temporarily blocked for {BLOCK_DURATION} seconds.")
        elif update.callback_query:
            await update.callback_query.answer(f"🚨 Blocked for {BLOCK_DURATION}s due to spam!", show_alert=True)
        return
    # --- END SPAM BLOCKER LOGIC ---

    user = await user_collection.find_one({'id': user_id})
    if not user:
        if update.message:
            await update.message.reply_text('You Have Not Guessed any Characters Yet..')
        else:
            await update.callback_query.edit_message_text('You Have Not Guessed any Characters Yet..')
        return

    characters = sorted(user['characters'], key=lambda x: (x['anime'], x['id']))

    character_counts = {k: len(list(v)) for k, v in groupby(characters, key=lambda x: x['id'])}

    unique_characters = list({character['id']: character for character in characters}.values())

    total_pages = math.ceil(len(unique_characters) / 15)  

    if page < 0 or page >= total_pages:
        page = 0  

    harem_message = f"<b>{escape(update.effective_user.first_name)}'s Harem - Page {page+1}/{total_pages}</b>\n"

    current_characters = unique_characters[page*15:(page+1)*15]

    current_grouped_characters = {k: list(v) for k, v in groupby(current_characters, key=lambda x: x['anime'])}

    for anime, characters in current_grouped_characters.items():
        harem_message += f'\n<b>{anime} {len(characters)}/{await collection.count_documents({"anime": anime})}</b>\n'

        for character in characters:
            count = character_counts[character['id']]  
            harem_message += f'{character["id"]} {character["name"]} ×{count}\n'

    total_count = len(user['characters'])
    
    keyboard = [[InlineKeyboardButton(f"See Collection ({total_count})", switch_inline_query_current_chat=f"collection.{user_id}")]]

    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"harem:{page-1}:{user_id}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"harem:{page+1}:{user_id}"))
        keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if 'favorites' in user and user['favorites']:
        fav_character_id = user['favorites'][0]
        fav_character = next((c for c in user['characters'] if c['id'] == fav_character_id), None)

        if fav_character and 'img_url' in fav_character:
            if update.message:
                await update.message.reply_photo(photo=fav_character['img_url'], parse_mode='HTML', caption=harem_message, reply_markup=reply_markup)
            else:
                if update.callback_query.message.caption != harem_message:
                    await update.callback_query.edit_message_caption(caption=harem_message, reply_markup=reply_markup, parse_mode='HTML')
        else:
            if update.message:
                await update.message.reply_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
            else:
                if update.callback_query.message.text != harem_message:
                    await update.callback_query.edit_message_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
    else:
        if user['characters']:
            random_character = random.choice(user['characters'])

            if 'img_url' in random_character:
                if update.message:
                    await update.message.reply_photo(photo=random_character['img_url'], parse_mode='HTML', caption=harem_message, reply_markup=reply_markup)
                else:
                    if update.callback_query.message.caption != harem_message:
                        await update.callback_query.edit_message_caption(caption=harem_message, reply_markup=reply_markup, parse_mode='HTML')
            else:
                if update.message:
                    await update.message.reply_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
                else:
                    if update.callback_query.message.text != harem_message:
                        await update.callback_query.edit_message_text(harem_message, parse_mode='HTML', reply_markup=reply_markup)
        else:
            if update.message:
                await update.message.reply_text("Your List is Empty :)")

async def harem_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data

    _, page, user_id = data.split(':')

    page = int(page)
    user_id = int(user_id)

    if query.from_user.id != user_id:
        await query.answer("It's Not Your Harem", show_alert=True)
        return

    await harem(update, context, page)


application.add_handler(CommandHandler(["harem", "collection"], harem, block=False))
harem_handler = CallbackQueryHandler(harem_callback, pattern='^harem', block=False)
application.add_handler(harem_handler)
    
