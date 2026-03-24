import time
from bot.database.mongo import blocks_collection

# Dictionary to track message counts: {user_id: [timestamps]}
user_activity = {}

# spam configuration
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
    
