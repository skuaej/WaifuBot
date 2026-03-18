import time
from telegram import Update
from telegram.ext import ContextTypes
from bot.database.mongo import users_collection
from bot.utils.formatters import escape_markdown

# 24 hours in seconds
DAILY_COOLDOWN = 24 * 60 * 60
DAILY_REWARD = 500

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/balance command to check coins."""
    user = update.effective_user
    user_data = await users_collection.find_one({"id": user.id})
    coins = user_data.get("coins", 0) if user_data else 0
    await update.message.reply_text(f"💰 You have <b>{coins}</b> coins.", parse_mode="HTML")

async def bonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/bonus for daily reward."""
    user = update.effective_user
    user_data = await users_collection.find_one({"id": user.id})

    current_time = time.time()
    last_bonus = user_data.get("last_bonus", 0) if user_data else 0

    if current_time - last_bonus < DAILY_COOLDOWN:
        remaining = int(DAILY_COOLDOWN - (current_time - last_bonus))
        hours, remainder = divmod(remaining, 3600)
        minutes, _ = divmod(remainder, 60)
        await update.message.reply_text(f"⏳ You have already claimed your bonus! Come back in {hours}h {minutes}m.")
        return

    await users_collection.update_one(
        {"id": user.id},
        {
            "$inc": {"coins": DAILY_REWARD},
            "$set": {
                "last_bonus": current_time,
                "name": user.first_name,
                "username": user.username
            }
        },
        upsert=True
    )

    await update.message.reply_text(f"🎉 You claimed your daily reward of <b>{DAILY_REWARD}</b> coins!", parse_mode="HTML")

async def transfer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/transfer <amount> to replied user."""
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to the user you want to transfer coins to.")
        return

    target_user = update.message.reply_to_message.from_user
    sender = update.effective_user

    if target_user.is_bot or sender.id == target_user.id:
        await update.message.reply_text("❌ Invalid target for transfer.")
        return

    try:
        amount = int(context.args[0])
        if amount <= 0:
            raise ValueError
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /transfer <amount>")
        return

    sender_data = await users_collection.find_one({"id": sender.id})
    sender_coins = sender_data.get("coins", 0) if sender_data else 0

    if sender_coins < amount:
        await update.message.reply_text(f"❌ You don't have enough coins! Balance: {sender_coins}")
        return

    # Deduct from sender
    await users_collection.update_one(
        {"id": sender.id},
        {"$inc": {"coins": -amount}}
    )

    # Add to target
    await users_collection.update_one(
        {"id": target_user.id},
        {
            "$inc": {"coins": amount},
            "$set": {"name": target_user.first_name, "username": target_user.username}
        },
        upsert=True
    )

    target_mention = f"<a href='tg://user?id={target_user.id}'>{escape_markdown(target_user.first_name)}</a>"
    await update.message.reply_text(
        f"💸 Successfully transferred <b>{amount}</b> coins to {target_mention}!",
        parse_mode="HTML"
    )
