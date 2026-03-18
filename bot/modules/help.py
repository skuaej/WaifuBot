from telegram import Update
from telegram.ext import ContextTypes
from bot.modules.admin import is_sudo

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detailed help command with categories."""
    user_id = update.effective_user.id
    is_admin = await is_sudo(user_id)
    
    text = (
        "📖 <b>Wᴀɪғᴜ Cᴀᴛᴄʜᴇʀ Hᴇʟᴘ</b>\n\n"
        "✨ <b>Uꜱᴇʀ Cᴏᴍᴍᴀɴᴅꜱ</b>\n"
        "• <code>/grab &lt;name&gt;</code> - Catch a spawned waifu\n"
        "• <code>/harem</code> - View your character collection\n"
        "• <code>/profile</code> - View your stats & ranking\n"
        "• <code>/search</code> - Search characters globally or in harems\n"
        "• <code>/smash</code> - Interactive smash game (5m cooldown)\n"
        "• <code>/cancel</code> - Cancel active smash proposal\n"
        "• <code>/hclaim</code> - Claim your daily free waifu\n"
        "• <code>/fav &lt;ID&gt;</code> - Set a favorite character\n"
        "• <code>/hmode</code> - Change your harem rarity filter\n"
        "• <code>/enable &lt;on/off&gt;</code> - Toggle games globally (Owner)\n"
        "• <code>/top</code>, <code>/gtop</code> - View leaderboards\n"
        "• <code>/balance</code>, <code>/bonus</code> - Economy commands\n"
        "• <code>/trade</code>, <code>/gift</code>, <code>/transfer</code> - Social commands\n\n"
    )
    
    if is_admin:
        text += (
            "🛠 <b>Aᴅᴍɪɴ Cᴏᴍᴍᴀɴᴅꜱ</b>\n"
            "• <code>/upload</code> - Add a new character (reply to media)\n"
            "• <code>/cgrant &lt;char_id&gt; [user_id]</code> - Give a character to a user\n"
            "• <code>/cgrant &lt;user_id&gt;</code> - View a user's grabbed list\n"
            "• <code>/delete &lt;IDs&gt;</code> - Remove characters from database\n"
            "• <code>/changetime &lt;seconds&gt;</code> - Set spawn rate\n"
            "• <code>/stats</code> - Bot statistics\n"
            "• <code>/broadcast</code> - Message all groups\n"
            "• <code>/addsudo</code>, <code>/resudo</code> - Manage sudo users\n"
            "• <code>/ping</code> - Check system status\n"
        )
        
    await update.message.reply_text(text, parse_mode="HTML")
