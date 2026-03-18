import time
from bot.database.mongo import blocks_collection

# Dictionary to track message counts: {user_id: [timestamps]}
user_activity = {}

# spam configuration
MSG_LIMIT = 5  # messages
TIME_WINDOW = 10  # seconds
BLOCK_DURATION = 1800  # 30 minutes (1800s)

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

async def is_spammer(user_id: int) -> bool:
    """Check if a user is currently blocked or should be blocked."""
    now = time.time()
    
    # 1. Check if user is currently blocked
    remaining = await get_block_remaining(user_id)
    if remaining > 0:
        return True
    
    # 2. Check transient activity for new spam
    if user_id not in user_activity:
        user_activity[user_id] = []
    
    # Cleanup old timestamps
    user_activity[user_id] = [t for t in user_activity[user_id] if now - t < TIME_WINDOW]
    
    # Add now
    user_activity[user_id].append(now)
    
    # Check limit
    if len(user_activity[user_id]) > MSG_LIMIT:
        # Block them
        until = now + BLOCK_DURATION
        await blocks_collection.update_one(
            {"id": user_id},
            {"$set": {"until": until}},
            upsert=True
        )
        return True
        
    return False
