import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    InlineQueryHandler,
    CallbackQueryHandler,
    TypeHandler,
    filters,
    ContextTypes,
    ApplicationHandlerStop
)

from bot.modules.admin import (
    upload_cmd, delete_cmd, broadcast_cmd, changetime_cmd, 
    channel_post_handler, forward_save_handler, addsudo_cmd, 
    resudo_cmd, sudo_callback_handler, stats_cmd, send_log, 
    ping_cmd, enable_cmd, spwanglobal_cmd
)
from bot.utils.formatters import escape_markdown
from bot.config import BOT_TOKEN, LOG_CHAT_ID
from bot.database.mongo import init_db
from bot.modules.spawn import group_message_handler
from bot.modules.capture import capture_cmd
from bot.modules.collection import (
    harem_cmd, profile_cmd, top_cmd, gtop_cmd, fav_cmd, 
    check_cmd, hmode_cmd, collection_callback_handler, hclaim_cmd
)
from bot.modules.trade import trade_cmd, gift_cmd, accept_cmd, reset_cmd, gift_callback_handler
from bot.modules.economy import balance_cmd, bonus_cmd, transfer_cmd
from bot.modules.search import inline_query, search_cmd
from bot.modules.gift import cgrant_cmd
from bot.modules.help import help_cmd
from bot.modules.smash import smash_cmd, cancel_cmd, game_callback_handler
from bot.utils.spam import is_spammer
from bot.web import start_server

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def check_spam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """High priority handler to block spammers (Allows /profile ONLY)."""
    user = update.effective_user
    if not user:
        return
    user_id = user.id
    from bot.utils.spam import get_block_remaining, is_spammer
    
    # 1. Update activity window and check status
    spam_status = await is_spammer(user_id)
    
    if spam_status > 0:
        # User is blocked. Check if it's an allowed command.
        msg = update.effective_message
        text = ""
        if msg:
            text = (msg.text or msg.caption or "").strip()
            
        # 1. ALLOW /profile and /start (and their buttons)
        allowed_cmds = ("/profile", "/start")
        if text.startswith(allowed_cmds):
            return # Let them through
            
        # 2. Block and NOTIFY for other commands
        if text.startswith("/"):
            remaining = await get_block_remaining(user_id)
            if remaining > 0:
                logging.info(f"🚫 BLOCKED COMMAND (FEEDBACK): User {user_id} tried '{text[:20]}...'")
                try:
                    await update.message.reply_text(
                        f"🚫 <b>YOU ARE BLOCKED!</b> Get free in: {remaining // 60}m {remaining % 60}s\n"
                        f"Only /profile is available.",
                        parse_mode="HTML"
                    )
                except: pass
            raise ApplicationHandlerStop()
            
        # 3. Block buttons if they aren't profile-related
        if update.callback_query:
            query_data = update.callback_query.data
            allowed_prefixes = ("harem_", "stats_", "back_", "close_", "prof_")
            if not query_data.startswith(allowed_prefixes):
                logging.info(f"🚫 BLOCKED BUTTON: User {user_id} pressed '{query_data}'")
                remaining = await get_block_remaining(user_id)
                try:
                    await update.callback_query.answer(
                        f"🚫 BLOCKED! ({remaining // 60}m {remaining % 60}s remains)", 
                        show_alert=True
                    )
                except: pass
                raise ApplicationHandlerStop()
                
        # 4. SILENT for everything else (regular chat) - allow it to pass
        # This ensures chat still counts for spawn even if user is 'command-blocked'

async def debug_all_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # print(f"DEBUG RAW UPDATE: {update.to_dict()}")
    pass

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Intro message with inline group join buttons."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    text = (
        "🌟 <b>Welcome to Waifu Catcher Bot!</b> 🌟\n\n"
        "I will spawn waifus in your group when people chat.\n"
        "Be the first to guess their name using /grab or /guess to catch them!\n\n"
        "📌 <b>Commands:</b>\n"
        "/hclaim - Claim a free random character daily\n"
        "/harem - View your collection\n"
        "/profile - View your stats\n\n"
        "Join our groups to start catching! 👇"
    )
    keyboard = [
        [InlineKeyboardButton("🚀 Join Support Chat", url="Https://t.me/+xIDVAEvE5m0yMTNl")],
        [InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{(await context.bot.get_me()).username}?startgroup=true")],
        [InlineKeyboardButton("🌸 Official Group", url="https://t.me/+" + "3868807342")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
    if update.effective_chat.type == "private":
        await send_log(context, f"👤 <b>User Started Bot</b>\nUser: {update.effective_user.first_name} (<code>{update.effective_user.id}</code>)")


def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN is missing!")
        return

    async def post_init(app):
        await init_db()
        try:
            await app.bot.send_message(chat_id=LOG_CHAT_ID, text="🚀 <b>Bot has started successfully!</b>", parse_mode="HTML")
        except Exception as e:
            print(f"FAILED TO SEND START LOG: {e}")

    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Track activity & Block (Group -1 runs first)
    # Global Handlers (processed first in group 0)
    application.add_handler(TypeHandler(Update, check_spam_handler))
    # application.add_handler(TypeHandler(Update, debug_all_updates)) # Disable debug for cleaner logs

    # Commands
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("enable", enable_cmd))
    
    # Capture System
    application.add_handler(CommandHandler(["grab", "guess", "catch", "hug"], capture_cmd))
    
    # Collection System
    application.add_handler(CommandHandler("harem", harem_cmd))
    application.add_handler(CommandHandler("profile", profile_cmd))
    application.add_handler(CommandHandler("top", top_cmd))
    application.add_handler(CommandHandler("gtop", gtop_cmd))
    application.add_handler(CommandHandler("fav", fav_cmd))
    application.add_handler(CommandHandler("hmode", hmode_cmd))
    application.add_handler(CommandHandler("check", check_cmd))
    application.add_handler(CallbackQueryHandler(gift_callback_handler, pattern="^gift_"))
    application.add_handler(CallbackQueryHandler(sudo_callback_handler, pattern="^sudo_"))
    application.add_handler(CallbackQueryHandler(game_callback_handler, pattern="^smash_"))
    application.add_handler(CallbackQueryHandler(collection_callback_handler))
    
    # Trade & Economy
    application.add_handler(CommandHandler("trade", trade_cmd))
    application.add_handler(CommandHandler("accept", accept_cmd))
    application.add_handler(CommandHandler("reset", reset_cmd))
    application.add_handler(CommandHandler("gift", gift_cmd))
    application.add_handler(CommandHandler("balance", balance_cmd))
    application.add_handler(CommandHandler("bonus", bonus_cmd))
    application.add_handler(CommandHandler("transfer", transfer_cmd))
    application.add_handler(CommandHandler("smash", smash_cmd))
    application.add_handler(CommandHandler("cancel", cancel_cmd))
    
    # Admin
    application.add_handler(CommandHandler("upload", upload_cmd))
    application.add_handler(CommandHandler("delete", delete_cmd))
    application.add_handler(CommandHandler("broadcast", broadcast_cmd))
    application.add_handler(CommandHandler("changetime", changetime_cmd))
    application.add_handler(CommandHandler("spwanglobal", spwanglobal_cmd))
    application.add_handler(CommandHandler("addsudo", addsudo_cmd))
    application.add_handler(CommandHandler("resudo", resudo_cmd))
    application.add_handler(CommandHandler(["stats", "total"], stats_cmd))
    application.add_handler(CommandHandler("ping", ping_cmd))
    application.add_handler(CommandHandler("cgrant", cgrant_cmd))
    
    # Harem Claim
    application.add_handler(CommandHandler("hclaim", hclaim_cmd))
    
    # Channel Post Handler for Auto-Uploads
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, channel_post_handler))
    
    # Auto-save forwarded images with captions
    application.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO | filters.Document.ALL) & filters.CAPTION,
        forward_save_handler
    ), group=1)
    
    # Group Message Handler for Spawning
    application.add_handler(MessageHandler(
        filters.ALL & (~filters.COMMAND),
        group_message_handler
    ))
    
    # Inline Query Handler
    application.add_handler(InlineQueryHandler(inline_query))
    
    # Standard Search Handler
    application.add_handler(CommandHandler("search", search_cmd))

    # Start health check server for Koyeb
    start_server()

    print("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
