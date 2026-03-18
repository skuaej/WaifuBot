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
        "ᴀᴅᴅ ᴛʜɪs ᴄʜᴀʀᴀᴄᴛᴇʀ ᴛᴏ ʏᴏᴜʀ ʜᴀʀᴇᴍ ᴜsɪɴɢ /catch [ɴᴀᴍᴇ]"
    )

def generate_success_message(user_id: int, user_name: str, char_name: str, anime: str, rarity: str) -> str:
    """Generate capture success message."""
    mention = f"<a href='tg://user?id={user_id}'>{escape_markdown(user_name)}</a>"
    return (
        f"💖 <b>Congratulations {mention}!</b>\n\n"
        f"You successfully captured: <b>{escape_markdown(char_name)}</b>\n"
        f"<b>Anime:</b> {escape_markdown(anime)}\n"
        f"<b>Rarity:</b> {rarity} 💠\n\n"
        f"<i>View your newly caught character using /harem!</i>"
    )
