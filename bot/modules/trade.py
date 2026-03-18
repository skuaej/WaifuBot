from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.mongo import users_collection, characters_collection
from bot.utils.formatters import escape_markdown
import re

# Simple in-memory trade/gift requests: {target_user_id: {initiator_id, offer_char, request_char, type, char_data}}
active_deals = {} 

async def get_char_by_query(query: str):
    """Robust character lookup by Name or ID (all padding variants)."""
    q_stripped = query.strip()
    
    # 1. Try numeric/padded ID matches first
    if q_stripped.isdigit():
        norm_id = str(int(q_stripped))
        # Match "24", "024", "0024" etc using regex
        regex = re.compile(f"^0*{norm_id}$")
        char = await characters_collection.find_one({"id": regex})
        if char: return char
        
        # Try exact numeric match if stored as integer
        char = await characters_collection.find_one({"id": int(q_stripped)})
        if char: return char

    # 2. Try exact ID string (for non-numeric IDs)
    char = await characters_collection.find_one({"id": q_stripped})
    if char: return char
            
    # 3. Fallback to case-insensitive name search
    name_regex = re.compile(f"^{re.escape(q_stripped)}$", re.IGNORECASE)
    return await characters_collection.find_one({"name": name_regex})

async def gift_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/gift <Waifu Name or ID> (must reply to the target user)"""
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ You must reply to the user you want to gift to.")
        return
        
    if not context.args:
        await update.message.reply_text("Usage: /gift Character ID or Name")
        return

    target_user = update.message.reply_to_message.from_user
    if target_user.is_bot:
        await update.message.reply_text("❌ You cannot gift waifus to bots.")
        return

    sender = update.effective_user
    if sender.id == target_user.id:
        await update.message.reply_text("❌ You cannot gift yourself!")
        return

    query = " ".join(context.args)
    print(f"SYSTEM: User {sender.id} is searching for gift waifu: '{query}'")
    char_data = await get_char_by_query(query)

    if not char_data:
        print(f"SYSTEM: Character '{query}' not found in DB.")
        await update.message.reply_text(f"❌ Character '{query}' does not exist.")
        return
        
    char_id = char_data['id']
    print(f"SYSTEM: Found char: {char_data['name']} (ID: {char_id})")
    # Normalize ID for comparison: "0024" -> "24"
    norm_char_id = str(int(char_id)) if str(char_id).isdigit() else str(char_id)
    
    sender_data = await users_collection.find_one({"id": sender.id})
    if sender_data:
        # Normalize all owned IDs for set comparison
        owned_norm = {str(int(wid)) if str(wid).isdigit() else str(wid) for wid in sender_data.get("waifus", [])}
        if norm_char_id not in owned_norm:
            await update.message.reply_text(f"❌ You do not own {char_data['name']}.")
            return
    else:
        await update.message.reply_text("❌ You don't have any characters!")
        return

    # Store as a "gift" deal, indexed by target_user.id for convenience
    active_deals[target_user.id] = {
        "initiator_id": sender.id,
        "target_id": target_user.id,
        "char_data": char_data,
        "type": "gift"
    }

    keyboard = [
        [InlineKeyboardButton("🎁 CONFIRM GIFT", callback_data=f"gift_confirm_{target_user.id}")],
        [InlineKeyboardButton("❌ CANCEL", callback_data=f"gift_cancel_{target_user.id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sender_mention = f"<a href='tg://user?id={sender.id}'>{escape_markdown(sender.first_name)}</a>"
    target_mention = f"<a href='tg://user?id={target_user.id}'>{escape_markdown(target_user.first_name)}</a>"

    await update.message.reply_text(
        f"🎁 <b>Gɪғᴛ Pʀᴏᴘᴏsᴀʟ</b>\n\n"
        f"➥ <b>From:</b> {sender_mention} (ID: <code>{sender.id}</code>)\n"
        f"➥ <b>To:</b> {target_mention} (ID: <code>{target_user.id}</code>)\n"
        f"➥ <b>Character:</b> {escape_markdown(char_data['name'])} (ID: <code>{char_id}</code>)\n\n"
        f"👉 {sender_mention}, click <b>CONFIRM GIFT</b> below to send it!",
        parse_mode="HTML",
        reply_markup=reply_markup
    )

async def gift_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the 'Confirm Gift' inline button."""
    query = update.callback_query
    data = query.data
    user = query.from_user

    if not data.startswith("gift_"):
        return

    action = data.split("_")[1] # confirm or cancel
    target_id = int(data.split("_")[2])
    deal = active_deals.get(target_id)
    
    if action == "cancel":
        if not deal:
            await query.answer("❌ This gift deal has already expired.", show_alert=True)
            await query.message.delete()
            return
            
        if user.id != deal["initiator_id"] and user.id != deal["target_id"]:
            await query.answer("❌ You cannot cancel this gift!", show_alert=True)
            return
            
        active_deals.pop(target_id, None)
        await query.message.edit_text("❌ Gift proposal was cancelled.")
        await query.answer("Gift cancelled.")
        return

    if action != "confirm":
        return

    # ONLY the Gifter (initiator) should click "Confirm"
    if user.id != deal["initiator_id"]:
        await query.answer("❌ Only the sender can confirm this gift!", show_alert=True)
        return

    # Ensure we are working with a dict
    if not isinstance(deal, dict):
        return
        
    initiator_id = deal.get("initiator_id")
    receiver_id = deal.get("target_id")
    char_data = deal.get("char_data")
    
    if not char_data:
        return
        
    char_id = char_data.get('id')
    norm_char_id = str(int(char_id)) if str(char_id).isdigit() else str(char_id)

    # Final ownership check
    sender_data = await users_collection.find_one({"id": initiator_id})
    if not sender_data:
        await query.answer("❌ Error: Sender not found.", show_alert=True)
        return
        
    s_waifus = sender_data.get("waifus", [])
    # Find the actual ID in the list that matches (could be padded or not)
    match_id = next((wid for wid in s_waifus if (str(int(wid)) if wid.isdigit() else wid) == norm_char_id), None)

    if not match_id:
        await query.answer("❌ Gift failed: You no longer own the character.", show_alert=True)
        await query.message.delete()
        return

    # Transfer logic: pull EXACTLY ONE instance
    s_waifus.remove(match_id)
    await users_collection.update_one({"id": initiator_id}, {"$set": {"waifus": s_waifus}})
    
    # Check if empty favorite needs unsetting
    if sender_data.get("favorite") == match_id and match_id not in s_waifus:
        await users_collection.update_one({"id": initiator_id}, {"$unset": {"favorite": ""}})

    receiver_user = await context.bot.get_chat(receiver_id)
    await users_collection.update_one(
        {"id": receiver_id},
        {"$push": {"waifus": match_id}, "$set": {"name": receiver_user.first_name, "username": receiver_user.username}},
        upsert=True
    )

    sender_name = sender_data.get('name', 'Sender')
    sender_mention = f"<a href='tg://user?id={initiator_id}'>{escape_markdown(sender_name)}</a>"
    receiver_mention = f"<a href='tg://user?id={receiver_id}'>{escape_markdown(receiver_user.first_name)}</a>"

    await query.message.edit_text(
        f"✅ <b>Gɪғᴛ Cᴏɴғɪʀᴍᴇᴅ!</b>\n\n"
        f"<b>{sender_mention}</b> has gifted <b>{escape_markdown(char_data['name'])}</b> to <b>{receiver_mention}</b>!",
        parse_mode="HTML"
    )
    await query.answer("🎁 Gift sent!")

async def trade_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/trade <MyID> <TheirID> (must reply to them)"""
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "ℹ To start a trade, reply to the user you want to trade with using this format:\n\n"
            "/trade waifu_id_to_trade waifu_id_to_get",
            parse_mode="HTML"
        )
        return

    target_user = update.message.reply_to_message.from_user
    sender = update.effective_user

    if target_user.is_bot or sender.id == target_user.id:
        await update.message.reply_text("❌ Invalid trade target.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "ℹ To start a trade, reply to the user you want to trade with using this format:\n\n"
            "/trade waifu_id_to_trade waifu_id_to_get"
        )
        return

    offer_id = context.args[0]
    request_id = context.args[1]

    offer_char = await get_char_by_query(offer_id)
    request_char = await get_char_by_query(request_id)

    if not offer_char or not request_char:
        await update.message.reply_text("❌ One or both of the specified characters do not exist.")
        return

    sender_data = await users_collection.find_one({"id": sender.id})
    target_data = await users_collection.find_one({"id": target_user.id})
    
    # Normalize IDs for comparison
    norm_offer = str(int(offer_char['id'])) if str(offer_char['id']).isdigit() else str(offer_char['id'])
    norm_request = str(int(request_char['id'])) if str(request_char['id']).isdigit() else str(request_char['id'])

    if sender_data:
        sender_owned = {str(int(wid)) if str(wid).isdigit() else str(wid) for wid in sender_data.get("waifus", [])}
        if norm_offer not in sender_owned:
            await update.message.reply_text(f"❌ You do not own <b>{escape_markdown(offer_char['name'])}</b>.", parse_mode="HTML")
            return
    else:
        await update.message.reply_text("❌ You don't have any characters!")
        return

    if target_data:
        target_owned = {str(int(wid)) if str(wid).isdigit() else str(wid) for wid in target_data.get("waifus", [])}
        if norm_request not in target_owned:
            target_mention = f"<a href='tg://user?id={target_user.id}'>{escape_markdown(target_user.first_name)}</a>"
            await update.message.reply_text(f"❌ {target_mention} does not own <b>{escape_markdown(request_char['name'])}</b>.", parse_mode="HTML")
            return
    else:
        target_mention = f"<a href='tg://user?id={target_user.id}'>{escape_markdown(target_user.first_name)}</a>"
        await update.message.reply_text(f"❌ {target_mention} does not have any characters!", parse_mode="HTML")
        return

    # Store trade proposal
    active_deals[target_user.id] = {
        "initiator_id": sender.id,
        "offer_char": offer_char,
        "request_char": request_char,
        "type": "trade"
    }

    sender_mention = f"<a href='tg://user?id={sender.id}'>{escape_markdown(sender.first_name)}</a>"
    target_mention = f"<a href='tg://user?id={target_user.id}'>{escape_markdown(target_user.first_name)}</a>"

    await update.message.reply_text(
        f"🔄 <b>Tʀᴀᴅᴇ Pʀᴏᴘᴏsᴀʟ!</b>\n\n"
        f"<b>{sender_mention}</b> offers: <b>{escape_markdown(offer_char['name'])}</b>\n"
        f"For <b>{target_mention}</b>'s: <b>{escape_markdown(request_char['name'])}</b>\n\n"
        f"👉 {target_mention}, reply with `/accept` to confirm.",
        parse_mode="HTML"
    )

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/reset to cancel ongoing trade or gift deals."""
    user = update.effective_user
    found = False
    to_delete = []
    
    # Check dictionary items for user ID in initiator or target position
    for tid in list(active_deals.keys()):
        deal = active_deals[tid]
        if deal.get("initiator_id") == user.id or tid == user.id:
            to_delete.append(tid)
            found = True
    
    for tid in to_delete:
        active_deals.pop(tid, None)
        
    if found:
        await update.message.reply_text("✅ All your ongoing trade or gift deals have been cancelled.")
    else:
        await update.message.reply_text("⏹️ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ᴏɴɢᴏɪɴɢ ᴛʀᴀᴅᴇ ᴏʀ ɢɪғᴛ ᴅᴇᴀʟs.")

async def accept_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/accept to confirm trade or receive gift."""
    user = update.effective_user
    if user.id not in active_deals:
        await update.message.reply_text("❌ You have no pending trades or gift deals to accept.")
        return

    deal = active_deals.pop(user.id)
    initiator_id = deal["initiator_id"]
    
    if deal.get("type") == "gift":
        await update.message.reply_text("❌ This gift must be confirmed by the sender using the button on the gift message.")
        active_deals[user.id] = deal
        return

    # Trade logic
    offer_char = deal["offer_char"]
    request_char = deal["request_char"]

    sender_data = await users_collection.find_one({"id": initiator_id})
    target_data = await users_collection.find_one({"id": user.id})

    if not sender_data or offer_char['id'] not in sender_data.get("waifus", []):
        await update.message.reply_text("❌ Trade failed: Initiator no longer owns the character.")
        return

    if not target_data or request_char['id'] not in target_data.get("waifus", []):
        await update.message.reply_text("❌ Trade failed: You no longer own the character.")
        return

    # Perform swap
    # Pull ONE instance each
    s_waifus = sender_data.get("waifus", [])
    if offer_char['id'] in s_waifus:
        s_waifus.remove(offer_char['id'])
        await users_collection.update_one({"id": initiator_id}, {"$set": {"waifus": s_waifus}})
        
    t_waifus = target_data.get("waifus", [])
    if request_char['id'] in t_waifus:
        t_waifus.remove(request_char['id'])
        await users_collection.update_one({"id": user.id}, {"$set": {"waifus": t_waifus}})
    
    await users_collection.update_one({"id": initiator_id}, {"$push": {"waifus": request_char['id']}})
    await users_collection.update_one({"id": user.id}, {"$push": {"waifus": offer_char['id']}})
    
    if sender_data.get("favorite") == offer_char['id']:
        await users_collection.update_one({"id": initiator_id}, {"$unset": {"favorite": ""}})
    if target_data.get("favorite") == request_char['id']:
        await users_collection.update_one({"id": user.id}, {"$unset": {"favorite": ""}})

    await update.message.reply_text("✅ Trade successful! Characters have been swapped.")
