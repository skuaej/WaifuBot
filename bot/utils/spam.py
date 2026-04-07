import time

# --- SPAM CONFIGURATION ---
last_user = {}
warned_users = {}

async def get_block_remaining(user_id: int) -> int:
    """Return remaining block time in seconds, or 0 if not blocked."""
    if user_id in warned_users:
        remaining = 600 - (time.time() - warned_users[user_id])
        if remaining > 0:
            return int(remaining)
        else:
            del warned_users[user_id]
    return 0

async def is_spammer(user_id: int) -> int:
    """
    Check if a user is currently blocked.
    Returns: 0 if not blocked, 1 if already blocked.
    (Transient activity check is now moved to spawn message counter)
    """
    remaining = await get_block_remaining(user_id)
    if remaining > 0:
        return 1
    return 0

async def check_and_warn_spam(chat_id: int, user_id: int, user_first_name: str, message) -> bool:
    """
    Checks consecutive messages per chat. Mutates state. 
    Returns True if the message should be ignored for spawning.
    """
    chat_id_str = str(chat_id)
    now = time.time()
    
    if chat_id_str in last_user and last_user[chat_id_str]['user_id'] == user_id:
        last_user[chat_id_str]['count'] += 1
        if last_user[chat_id_str]['count'] >= 10:
            if user_id in warned_users and now - warned_users[user_id] < 600:
                return True
            else:
                try:
                    await message.reply_text(f"⚠️ Don't Spam {user_first_name}...\nYour Messages Will be ignored for 10 Minutes...")
                except Exception:
                    pass
                warned_users[user_id] = now
                return True
    else:
        last_user[chat_id_str] = {'user_id': user_id, 'count': 1}

    return False
