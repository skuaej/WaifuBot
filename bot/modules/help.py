import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.config import BOT_TOKEN, SUPPORT_CHAT_LINK

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detailed help command overlay."""
    help_text = (
        "***Help Section:***\n\n"
        "***/guess: To Guess character (only works in group)***\n"
        "***/fav: Add Your fav***\n"
        "***/trade : To trade Characters***\n"
        "***/gift: Give any Character from Your Collection to another user.. (only works in groups)***\n"
        "***/daily: Claim daily character card***\n"
        "***/hclaim: Claim daily character card***\n"
        "***/collection: To see Your Collection***\n"
        "***/topgroups : See Top Groups.. Ppl Guesses Most in that Groups***\n"
        "***/top: Too See Top Users***\n"
        "***/ctop : Your ChatTop***\n"
        "***/changetime: Change Character appear time (only works in Groups)***\n"
    )
    help_keyboard = [[InlineKeyboardButton("⤾ Bᴀᴄᴋ", callback_data="start_back")]]
    reply_markup = InlineKeyboardMarkup(help_keyboard)
    await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode="markdown")

async def help_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    me = await context.bot.get_me()
    
    if query.data == "start_help":
        help_text = (
            "***Help Section:***\n\n"
            "***/guess: To Guess character (only works in group)***\n"
            "***/fav: Add Your fav***\n"
            "***/trade : To trade Characters***\n"
            "***/gift: Give any Character from Your Collection to another user.. (only works in groups)***\n"
            "***/daily: Claim daily character card***\n"
            "***/hclaim: Claim daily character card***\n"
            "***/collection: To see Your Collection***\n"
            "***/topgroups : See Top Groups.. Ppl Guesses Most in that Groups***\n"
            "***/top: Too See Top Users***\n"
            "***/ctop : Your ChatTop***\n"
            "***/changetime: Change Character appear time (only works in Groups)***\n"
        )
        help_keyboard = [[InlineKeyboardButton("⤾ Bᴀᴄᴋ", callback_data="start_back")]]
        reply_markup = InlineKeyboardMarkup(help_keyboard)
        await context.bot.edit_message_caption(
            chat_id=update.effective_chat.id, 
            message_id=query.message.message_id, 
            caption=help_text, 
            reply_markup=reply_markup, 
            parse_mode="markdown"
        )
        return

    if query.data == "start_back":
        caption = (
            "***Heyyyy...***\n\n"
            "***I am An Open Source Character Catcher Bot...​Add Me in Your group.. And I will send Random Characters After.. every 100 messages in Group... Use /guess to.. Collect that Characters in Your Collection.. and see Collection by using /Harem... So add in Your groups and Collect Your harem***"
        )
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
        await context.bot.edit_message_caption(
            chat_id=update.effective_chat.id, 
            message_id=query.message.message_id, 
            caption=caption, 
            reply_markup=reply_markup, 
            parse_mode="markdown"
        )

