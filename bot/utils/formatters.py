def escape_markdown(text: str) -> str:
    """Helper function to escape HTML/Markdown characters if needed."""
    # We mainly use HTML parse mode, escaping <, >, &
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def generate_spawn_message(name: str, rarity: str) -> str:
    """Generate the user-requested spawn message with rarity-based icons."""
    rarity_emojis = {
        "Common": "🔵",
        "Uncommon": "🟣",
        "Rare": "🟠",
        "Legendary": "🟡",
        "Mystical": "💮",
        "Divine": "⚜️",
        "Crossverse": "⚡",
        "Supreme": "🪞",
        "Cataphract": "✨"
    }
    emoji = rarity_emojis.get(rarity, "🟡")
    
    return (
        f"{emoji} ᴀ ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀs sᴘᴀᴡɴᴇᴅ ɪɴ ᴛʜᴇ ᴄʜᴀᴛ!🧃\n\n"
        "ᴀᴅᴅ ᴛʜɪs ᴄʜᴀʀᴀᴄᴛᴇʀ ᴛᴏ ʏᴏᴜʀ ʜᴀʀᴇᴍ ᴜsɪɴɢ /catch or /hug [ɴᴀᴍᴇ]"
    )

def get_stylized_rarity(rarity: str) -> str:
    """Returns a stylized rarity string for themes."""
    rarity_emojis = {
        "Common": "🔵", "Uncommon": "🟣", "Rare": "🟠", 
        "Legendary": "🟡", "Mystical": "💮", "Divine": "⚜️",
        "Crossverse": "⚡", "Supreme": "🪞", "Cataphract": "✨"
    }
    emoji = rarity_emojis.get(rarity, "💮")
    return f"({emoji} 𝙍𝘼𝙍𝙄𝙏𝙔: {rarity})"

def generate_success_message(user_id: int, user_name: str, char_name: str, anime: str, rarity: str, action: str) -> str:
    """Generate capture success message with new fashion theme."""
    mention = f"<a href='tg://user?id={user_id}'>{escape_markdown(user_name)}</a>"
    stylized_rarity = get_stylized_rarity(rarity)

    return (
        f"🪷 {mention}, ʏᴏᴜ {action.upper()} ᴀ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ!\n\n"
        f"<b>{escape_markdown(anime)}</b>\n"
        f"ɴᴇᴡ: {escape_markdown(char_name)}\n"
        f"{stylized_rarity}\n\n"
        f"❄️ ᴄʜᴇᴄᴋ ʏᴏᴜʀ /harem!"
    )
