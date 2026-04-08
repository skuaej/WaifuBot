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

def generate_success_message(user_id: int, user_name: str, char_name: str, anime: str, rarity: str, user_in_anime: int, total_in_anime: int) -> str:
    """Generate capture success message with new theme and anime stats."""
    mention = f"<a href='tg://user?id={user_id}'>{escape_markdown(user_name)}</a>"
    
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
        f"{mention} ʀᴇᴅɪʀᴇᴛ ᴛᴏ ᴘʀᴏꜰɪʟᴇ , ʏᴏᴜ ɢᴏᴛ ᴀ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ!\n\n"
        f"🫧 ɴᴀᴍᴇ: {escape_markdown(char_name)} [💠]\n"
        f"{emoji} 𝙍𝘼𝙍𝙄𝙏𝙔: {rarity}\n"
        f"🏖️ ᴀɴɪᴍᴇ: {escape_markdown(anime)} ({user_in_anime}/{total_in_anime})\n\n"
        f"❄️ ᴄʜᴇᴄᴋ ʏᴏᴜʀ /harem!"
    )
