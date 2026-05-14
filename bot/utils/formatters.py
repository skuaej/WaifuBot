def escape_markdown(text: str) -> str:
    """Helper function to escape HTML/Markdown characters if needed."""
    # We mainly use HTML parse mode, escaping <, >, &
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def generate_spawn_message(name: str, rarity: str) -> str:
    """Generate the user-requested spawn message with rarity-based icons."""
    rarity_emojis = {
        "Common": "\U0001f535",
        "Uncommon": "\U0001f7e3",
        "Rare": "\U0001f7e0",
        "Legendary": "\U0001f7e1",
        "Mystical": "\U0001f4ae",
        "Divine": "\u269c\ufe0f",
        "Crossverse": "\u26a1",
        "Supreme": "\U0001fa9e",
        "Cataphract": "\u2728"
    }
    emoji = rarity_emojis.get(rarity, "\U0001f7e1")
    
    return (
        f"{emoji} ᴀ ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀs sᴘᴀᴡɴᴇᴅ ɪɴ ᴛʜᴇ ᴄʜᴀᴛ!🧃\n\n"
        "ᴀᴅᴅ ᴛʜɪs ᴄʜᴀʀᴀᴄᴛᴇʀ ᴛᴏ ʏᴏᴜʀ ʜᴀʀᴇᴍ ᴜsɪɴɢ /catch or /hug [ɴᴀᴍᴇ]"
    )

def get_stylized_rarity(rarity: str) -> str:
    """Returns a stylized rarity string for themes."""
    rarity_emojis = {
        "Common": "\U0001f535", "Uncommon": "\U0001f7e3", "Rare": "\U0001f7e0", 
        "Legendary": "\U0001f7e1", "Mystical": "\U0001f4ae", "Divine": "\u269c\ufe0f",
        "Crossverse": "\u26a1", "Supreme": "\U0001fa9e", "Cataphract": "\u2728"
    }
    emoji = rarity_emojis.get(rarity, "\U0001f4ae")
    return f"({emoji} 𝙍𝘼𝙍𝙄𝙏𝙔: {rarity})"

def generate_success_message(user_id: int, user_name: str, char_name: str, anime: str, rarity: str, action: str) -> str:
    """Generate capture success message with restored premium fashion theme."""
    mention = f"<a href='tg://user?id={user_id}'>{escape_markdown(user_name)}</a>"
    
    rarity_emojis = {
        "Common": "\U0001f535", "Uncommon": "\U0001f7e3", "Rare": "\U0001f7e0", 
        "Legendary": "\U0001f7e1", "Mystical": "\U0001f4ae", "Divine": "\u269c\ufe0f",
        "Crossverse": "\u26a1", "Supreme": "\U0001fa9e", "Cataphract": "\u2728"
    }
    emoji = rarity_emojis.get(rarity, "\U0001f4ae")

    return (
        f"🪷 {mention}, ʏᴏᴜ {action.upper()} ᴀ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ!\n\n"
        f"\U0001fae7 Nᴀᴍᴇ: {escape_markdown(char_name)}\n"
        f"{emoji} 𝙍𝘼𝙍𝙄𝙏𝙔: {rarity}\n"
        f"🏖️ Aɴɪᴍᴇ: {escape_markdown(anime)}\n\n"
        f"❄️ ᴄʜᴇᴄᴋ ʏᴏᴜʀ /harem!"
    )
