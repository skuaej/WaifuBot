import time
import html
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
    await update.message.reply_text(f"\U0001f4b0 You have <b>{coins}</b> coins.", parse_mode="HTML")


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
        await update.message.reply_text(f"\u23f3 You have already claimed your bonus! Come back in {hours}h {minutes}m.")
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


async def _resolve_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Resolve the target user from the command arguments.
    Supports:
      - Replying to a message (no args needed)
      - /pay @username <amount>
      - /pay <user_id> <amount>
      - /pay <mention entity> <amount>
    Returns (target_user_dict, amount) or (None, None) on failure.
    The target_user_dict has keys: id, name, username
    """
    msg = update.message
    args = context.args or []

    # ── 1. Reply-based: /pay <amount> while replying ──────────────────────────
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if len(args) < 1:
            await msg.reply_text("Usage when replying: <b>/pay &lt;amount&gt;</b>", parse_mode="HTML")
            return None, None
        try:
            amount = int(args[0])
            if amount <= 0:
                raise ValueError
        except ValueError:
            await msg.reply_text("❌ Amount must be a positive number.")
            return None, None

        tu = msg.reply_to_message.from_user
        return {"id": tu.id, "name": tu.first_name, "username": tu.username}, amount

    # ── 2. Mention entity in the message ─────────────────────────────────────
    if msg.entities:
        for ent in msg.entities:
            if ent.type in ("text_mention",):
                # text_mention has a user object directly
                if len(args) < 1:
                    await msg.reply_text("Usage: <b>/pay @mention &lt;amount&gt;</b>", parse_mode="HTML")
                    return None, None
                try:
                    amount = int(args[-1])
                    if amount <= 0:
                        raise ValueError
                except ValueError:
                    await msg.reply_text("❌ Amount must be a positive number.")
                    return None, None
                tu = ent.user
                return {"id": tu.id, "name": tu.first_name, "username": tu.username}, amount

    # ── 3. Argument-based: /pay @username <amount> or /pay <id> <amount> ─────
    if len(args) < 2:
        await msg.reply_text(
            "📤 <b>Usage:</b>\n"
            "• Reply to a user: <code>/pay &lt;amount&gt;</code>\n"
            "• By username: <code>/pay @username &lt;amount&gt;</code>\n"
            "• By User ID: <code>/pay &lt;user_id&gt; &lt;amount&gt;</code>\n"
            "• Tag/mention: mention the user then <code>/pay &lt;amount&gt;</code>",
            parse_mode="HTML"
        )
        return None, None

    target_arg = args[0]
    try:
        amount = int(args[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await msg.reply_text("❌ Amount must be a positive number.")
        return None, None

    # Try numeric ID
    if target_arg.lstrip("-").isdigit():
        uid = int(target_arg)
        user_data = await users_collection.find_one({"id": uid})
        if not user_data:
            await msg.reply_text(f"❌ No user found with ID <code>{uid}</code>.", parse_mode="HTML")
            return None, None
        return {"id": user_data["id"], "name": user_data.get("name", str(uid)), "username": user_data.get("username")}, amount

    # Try username (strip leading @)
    uname = target_arg.lstrip("@")
    user_data = await users_collection.find_one({"username": {"$regex": f"^{uname}$", "$options": "i"}})
    if not user_data:
        await msg.reply_text(f"❌ No user found with username <code>@{html.escape(uname)}</code>.", parse_mode="HTML")
        return None, None
    return {"id": user_data["id"], "name": user_data.get("name", uname), "username": user_data.get("username")}, amount


async def pay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /pay - Transfer coins to another user.
    Supports: reply, @username, user_id, or text mention.
    """
    sender = update.effective_user
    target, amount = await _resolve_target_user(update, context)
    if target is None:
        return

    if target["id"] == sender.id:
        await update.message.reply_text("❌ You cannot pay yourself!")
        return

    sender_data = await users_collection.find_one({"id": sender.id})
    sender_coins = sender_data.get("coins", 0) if sender_data else 0

    if sender_coins < amount:
        await update.message.reply_text(
            f"❌ Insufficient coins!\n💰 Your balance: <b>{sender_coins}</b> coins",
            parse_mode="HTML"
        )
        return

    # Deduct from sender
    await users_collection.update_one({"id": sender.id}, {"$inc": {"coins": -amount}})

    # Add to target (upsert so even inactive users can receive)
    await users_collection.update_one(
        {"id": target["id"]},
        {
            "$inc": {"coins": amount},
            "$set": {
                "name": target["name"],
                **({"username": target["username"]} if target.get("username") else {})
            }
        },
        upsert=True
    )

    target_mention = f"<a href='tg://user?id={target['id']}'>{html.escape(target['name'])}</a>"
    await update.message.reply_text(
        f"💸 Successfully sent <b>{amount}</b> coins to {target_mention}!\n"
        f"💰 Your remaining balance: <b>{sender_coins - amount}</b> coins",
        parse_mode="HTML"
    )
