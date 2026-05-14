import logging, time
BOT_START_TIME = time.time()
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
    ApplicationHandlerStop,
    ChatMemberHandler
)

from bot.modules.admin import (
    upload_cmd, delete_cmd, broadcast_cmd, changetime_cmd, 
    channel_post_handler, forward_save_handler, addsudo_cmd, 
    resudo_cmd, sudo_callback_handler, stats_cmd, send_log, 
    ping_cmd, enable_cmd, spwanglobal_cmd, sudolist_cmd,
    transfer_cmd, transfercheck_cmd, bang_cmd, unbang_cmd, update_cmd,
    group_status_update_handler
)
from bot.utils.formatters import escape_markdown
from bot.config import BOT_TOKEN, LOG_CHAT_ID, PHOTO_URL, SUPPORT_CHAT_LINK
from bot.database.mongo import init_db
from bot.modules.spawn import group_message_handler
from bot.modules.capture import capture_cmd
from bot.modules.collection import (
    harem_cmd, profile_cmd, top_cmd, fav_cmd, 
    check_cmd, hmode_cmd, collection_callback_handler, hclaim_cmd, fav_callback_handler,
    topgroups_cmd, gtop_cmd, todaygtop_cmd, hdelete_cmd
)
from bot.modules.trade import trade_cmd, gift_cmd, accept_cmd, reset_cmd, gift_callback_handler, trade_callback_handler
from bot.modules.economy import balance_cmd, bonus_cmd, transfer_cmd
from bot.modules.search import inline_query, search_cmd
from bot.modules.gift import cgrant_cmd
from bot.modules.help import help_cmd, help_callback_handler
from bot.modules.smash import smash_cmd, cancel_cmd, game_callback_handler
from bot.web import start_server

# List of all commands handled by this bot (lower case)
BOT_COMMANDS = {
    "start", "help", "enable", "grab", "guess", "catch", "hug",
    "harem", "profile", "top", "gtop", "todaygtop", "topgroups", "fav", "hmode", "check",
    "trade", "accept", "reset", "gift", "balance", "bonus", "transfer", "smash", "cancel",
    "upload", "delete", "broadcast", "changetime", "timepower", "spwanglobal", "addsudo", "sudo", "resudo",
    "stats", "total", "ping", "pin", "pinf", "cgrant", "sudolist", "transfercheck", "bang", "unbang", "update",
    "hclaim", "claim", "search", "hdelete"
}

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
    
    # 0. Global Ban Check (Persistent)
    from bot.database.mongo import db
    bans_col = db['bans']
    if await bans_col.find_one({"user_id": user_id}):
        # Notify once if it's a message
        if update.message:
            try:
                await update.effective_chat.send_message("\u274c You are globally banned from using this bot.")
            except: pass
        raise ApplicationHandlerStop()

    from bot.utils.spam import get_block_remaining, is_spammer
    
    # 1. Update activity window and check status
    spam_status = await is_spammer(user_id)
    
    if spam_status > 0:
        # User is blocked. Check if it's an allowed command.
        msg = update.effective_message
        if msg:
            text = (msg.text or msg.caption or "").strip()
            
            if text.startswith("/"):
                # Extract command name: /grab@botname -> grab
                command_part = text.split()[0].split('@')[0][1:].lower()

                # 1. ALLOW /profile and /start (and their variants)
                if command_part in ("profile", "start"):
                    return # Let them through
                
                # 2. Block and NOTIFY ONLY if it's one of OUR commands
                if command_part in BOT_COMMANDS:
                    remaining = await get_block_remaining(user_id)
                    if remaining > 0:
                        logging.info(f"\U0001f6ab BLOCKED COMMAND (FEEDBACK): User {user_id} tried '{text[:20]}...'")
                        try:
                            await update.effective_chat.send_message(
                                f"\U0001f6ab <b>YOU ARE BLOCKED!</b> (Time: {remaining // 60}m {remaining % 60}s)\n"
                                f"Use /profile to check your status.",
                                parse_mode="HTML"
                            )
                        except: pass
                    raise ApplicationHandlerStop()
                
                # 3. If it's another command (not ours), let it pass silently
                return
            
        # 3. Block buttons if they aren't profile-related
        if update.callback_query:
            query_data = update.callback_query.data
            allowed_prefixes = ("harem_", "stats_", "back_", "close_", "prof_")
            if not query_data.startswith(allowed_prefixes):
                logging.info(f"\U0001f6ab BLOCKED BUTTON: User {user_id} pressed '{query_data}'")
                remaining = await get_block_remaining(user_id)
                try:
                    await update.callback_query.answer(
                        f"\U0001f6ab BLOCKED! ({remaining // 60}m {remaining % 60}s remains)", 
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
    import random
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    photo_url = random.choice(PHOTO_URL)
    me = await context.bot.get_me()
    
    keyboard = [
        [InlineKeyboardButton("ADD ME", url=f"http://t.me/{me.username}?startgroup=new")],
        [
            InlineKeyboardButton("SUPPORT", url=SUPPORT_CHAT_LINK or "https://t.me/"),
            InlineKeyboardButton("UPDATES", url="https://t.me/")
        ],
        [InlineKeyboardButton("HELP", callback_data="start_help")],
        [InlineKeyboardButton("SOURCE", url="https://github.com/MyNameIsShekhar/WAIFU-HUSBANDO-CATCHER")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.effective_chat.type == "private":
        if context.args:
            arg = context.args[0]
            if arg.startswith("upd_"):
                char_id = arg.split("_")[1]
                await update.message.reply_text(
                    f"\U0001f4dd <b>Update Character {char_id}</b>\n\n"
                    f"To update this character, use:\n"
                    f"<code>/update {char_id} [name] [series] [rarity] [type]</code>\n\n"
                    f"Or reply to a new image/video with <code>/update {char_id}</code>.",
                    parse_mode="HTML"
                )
                return

        caption = (
            "***Heyyyy...***\n\n"
            "***I am An Open Source Character Catcher Bot...​Add Me in Your group.. And I will send Random Characters After.. every 70 messages in Group... Use /guess to.. Collect that Characters in Your Collection.. and see Collection by using /Harem... So add in Your groups and Collect Your harem***"
        )
        await update.message.reply_photo(photo=photo_url, caption=caption, reply_markup=reply_markup, parse_mode="markdown")
        await send_log(context, f"\U0001f464 <b>User Started Bot</b>\nUser: {update.effective_user.first_name} (<code>{update.effective_user.id}</code>)")
    else:
        await update.message.reply_photo(
            photo=photo_url, 
            caption="\U0001f3b4Alive!?... \n connect to me in PM For more information ",
            reply_markup=reply_markup
        )

def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN is missing!")
        return

    async def post_init(app):
        await init_db()
        try:
            await app.bot.send_message(chat_id=LOG_CHAT_ID, text="\ud83d\ude80 <b>Bot has started successfully!</b>", parse_mode="HTML")
        except Exception as e:
            print(f"FAILED TO SEND START LOG: {e}")

    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Track activity & Block (Group -1 runs first)
    # Global Handlers (processed first in group -1)
    application.add_handler(TypeHandler(Update, check_spam_handler), group=-1)
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
    application.add_handler(CommandHandler("todaygtop", todaygtop_cmd))
    application.add_handler(CommandHandler("TopGroups", topgroups_cmd))
    application.add_handler(CommandHandler("fav", fav_cmd))
    application.add_handler(CommandHandler("hmode", hmode_cmd))
    application.add_handler(CommandHandler("check", check_cmd))
    application.add_handler(CommandHandler("hdelete", hdelete_cmd))
    application.add_handler(CallbackQueryHandler(gift_callback_handler, pattern="^gift_"))
    application.add_handler(CallbackQueryHandler(sudo_callback_handler, pattern="^sudo_"))
    application.add_handler(CallbackQueryHandler(game_callback_handler, pattern="^smash_"))
    application.add_handler(CallbackQueryHandler(help_callback_handler, pattern="^(start_|help_)"))
    application.add_handler(CallbackQueryHandler(trade_callback_handler, pattern="^trade_"))
    application.add_handler(CallbackQueryHandler(fav_callback_handler, pattern="^fav_"))
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
    application.add_handler(CommandHandler(["changetime", "timepower"], changetime_cmd))
    application.add_handler(CommandHandler("spwanglobal", spwanglobal_cmd))
    application.add_handler(CommandHandler(["addsudo", "sudo"], addsudo_cmd))
    application.add_handler(CommandHandler("resudo", resudo_cmd))
    application.add_handler(CommandHandler(["stats", "total"], stats_cmd))
    application.add_handler(CommandHandler(["ping", "pin", "pinf"], ping_cmd))
    application.add_handler(CommandHandler("cgrant", cgrant_cmd))
    application.add_handler(CommandHandler("sudolist", sudolist_cmd))
    application.add_handler(CommandHandler("transfer", transfer_cmd))
    application.add_handler(CommandHandler("transfercheck", transfercheck_cmd))
    application.add_handler(CommandHandler("bang", bang_cmd))
    application.add_handler(CommandHandler("unbang", unbang_cmd))
    application.add_handler(CommandHandler("update", update_cmd))
    
    # Harem Claim
    application.add_handler(CommandHandler(["hclaim", "claim"], hclaim_cmd))
    
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
    
    # Group Status Update Handler (Join/Leave Notices)
    application.add_handler(ChatMemberHandler(group_status_update_handler, ChatMemberHandler.MY_CHAT_MEMBER))

    # Start health check server for Koyeb
    start_server()

    print("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
