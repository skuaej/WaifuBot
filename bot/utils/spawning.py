import random
from bot.database.mongo import characters_collection

RARITY_WEIGHTS = {
    "Common": 40,
    "Uncommon": 25,
    "Rare": 15,
    "Legendary": 10,
    "Mystical": 5,
    "Divine": 3,
    "Crossverse": 1,
    "Supreme": 0.5,
    "Cataphract": 0.1
}

async def get_random_character():
    """Selects a random character based on weighted rarity adjusted to available pool."""
    available_rarities = await characters_collection.distinct("rarity")
    if not available_rarities:
        return None

    valid_rarities = {str(r): RARITY_WEIGHTS[str(r)] for r in available_rarities if str(r) in RARITY_WEIGHTS}
    
    if not valid_rarities:
        # Fallback to absolute random if the DB has weird unknown rarities
        fallback_pipeline = [{"$sample": {"size": 1}}]
        fallback_cursor = characters_collection.aggregate(fallback_pipeline)
        async for doc in fallback_cursor:
            return doc
        return None

    rarities = list(valid_rarities.keys())
    weights = list(valid_rarities.values())
    chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]

    # Fetch one character representing the correctly chosen weighted rarity
    pipeline = [
        {"$match": {"rarity": chosen_rarity}},
        {"$sample": {"size": 1}}
    ]
    
    cursor = characters_collection.aggregate(pipeline)
    async for doc in cursor:
        return doc
        
    # Final fallback: Pick ANY character if the chosen rarity has no characters (shouldn't happen with distinct() check but for safety)
    fallback_cursor = characters_collection.aggregate([{"$sample": {"size": 1}}])
    async for doc in fallback_cursor:
        return doc

    return None
