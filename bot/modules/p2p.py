"""
P2P Buy/Sell Card Market Module
Commands: /sell, /mysells
Callback: p2p_buy_<sale_id>
P2P Channel: -1003395328648
"""
import html
import uuid
import time
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from bot.database.mongo import (
    users_collection,
    characters_collection,
    p2p_sales_collection,
)
from bot.config import LOG_CHAT_ID


P2P_CHANNEL_ID = -1003395328648

RARITY_EMOJI = {
    "Common": "\U0001f535",
    "Uncommon": "\U0001f7e3",
    "Rare": "\U0001f7e0",
    "Legendary": "\U0001f7e1",
    "Mystical": "\U0001f4ae",
    "Divine": "\u269c\ufe0f",
    "Crossverse": "\u26a1",
    "Supreme": "\U0001fa9e",
    "Cataphract": "\u2728",
}

TYPE_DISPLAY = {
    "ee": "Event",
    "event": "Event",
    "normal": "Normal",
    "seasonal": "Seasonal",
}


def _type_label(raw: str) -> str:
    """Return a clean display label for a character type."""
    return TYPE_DISPLAY.get((raw or "normal").lower(), raw.capitalize())


def _build_listing_caption(char: dict, price: int, seller_name: str) -> str:
    """Build the styled P2P listing caption."""
    rarity = char.get("rarity", "Common")
    r_emoji = RARITY_EMOJI.get(rarity, "\U0001f4ae")
    ctype = _type_label(char.get("type", "normal"))
    type_header = "🌸 Event Character!" if ctype == "Event" else "✨ Character for Sale!"

    return (
        f"🛒 <b>{html.escape(type_header)}</b>\n\n"
        f"🆔 <b>ID:</b> <code>{html.escape(str(char['id']))}</code>\n"
        f"📛 <b>Name:</b> {html.escape(char.get('name', '?'))}\n"
        f"📺 <b>Series:</b> {html.escape(char.get('anime', '?'))}\n"
        f"{r_emoji} <b>Rarity:</b> {html.escape(rarity)}\n"
        f"🔖 <b>Type:</b> {html.escape(ctype)}\n\n"
        f"💰 <b>Price:</b> <b>{price}</b> coins\n"
        f"👤 <b>Seller:</b> {html.escape(seller_name)}"
    )


async def sell_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /sell <character_id> <price>
    Lists a character for sale in the P2P channel.
    """
    seller = update.effective_user
    args = context.args or []

    if len(args) < 2:
        await update.message.reply_text(
            "📤 <b>Usage:</b> <code>/sell &lt;character_id&gt; &lt;price&gt;</code>\n"
            "Example: <code>/sell 33 500</code>",
            parse_mode="HTML",
        )
        return

    char_id = args[0].strip()
    try:
        price = int(args[1])
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Price must be a positive number.")
        return

    # Verify seller owns the character
    seller_data = await users_collection.find_one({"id": seller.id})
    if not seller_data or char_id not in (seller_data.get("waifus") or []):
        # Also try integer string normalization
        char_id_norm = str(int(char_id)) if char_id.isdigit() else char_id
        owned = [str(int(w)) if w.isdigit() else w for w in (seller_data.get("waifus") or [])]
        if char_id_norm not in owned:
            await update.message.reply_text(
                f"❌ You don't own character <code>{html.escape(char_id)}</code>.",
                parse_mode="HTML",
            )
            return
        char_id = char_id_norm  # use normalized form

    # Check it's not already listed
    existing = await p2p_sales_collection.find_one({
        "char_id": char_id,
        "seller_id": seller.id,
        "status": "active"
    })
    if existing:
        await update.message.reply_text(
            f"⚠️ Character <code>{html.escape(char_id)}</code> is already listed for sale.",
            parse_mode="HTML",
        )
        return

    # Fetch character details
    char = await characters_collection.find_one({"id": char_id})
    if not char:
        # Try without normalization
        char = await characters_collection.find_one({"id": args[0].strip()})
    if not char:
        await update.message.reply_text(
            f"❌ Character <code>{html.escape(char_id)}</code> not found in database.",
            parse_mode="HTML",
        )
        return

    # Build caption and keyboard
    sale_id = str(uuid.uuid4())[:12]
    caption = _build_listing_caption(char, price, seller.first_name)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 BUY", callback_data=f"p2p_buy_{sale_id}")]
    ])

    # Send to P2P channel
    file_id = char.get("file_id")
    file_type = char.get("file_type", "photo")
    try:
        if file_type == "video":
            channel_msg = await context.bot.send_video(
                chat_id=P2P_CHANNEL_ID,
                video=file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        elif file_type == "document":
            channel_msg = await context.bot.send_document(
                chat_id=P2P_CHANNEL_ID,
                document=file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        else:
            channel_msg = await context.bot.send_photo(
                chat_id=P2P_CHANNEL_ID,
                photo=file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to post to P2P channel: {e}")
        return

    # Save listing to database
    await p2p_sales_collection.insert_one({
        "sale_id": sale_id,
        "char_id": char_id,
        "char_name": char.get("name", "?"),
        "char_anime": char.get("anime", "?"),
        "char_rarity": char.get("rarity", "Common"),
        "char_type": char.get("type", "normal"),
        "seller_id": seller.id,
        "seller_name": seller.first_name,
        "price": price,
        "status": "active",
        "channel_msg_id": channel_msg.message_id,
        "created_at": time.time(),
    })

    # Remove character from seller's harem immediately (reserve it)
    await users_collection.update_one(
        {"id": seller.id},
        {"$pull": {"waifus": char_id}}
    )

    await update.message.reply_text(
        f"✅ <b>Listed for sale!</b>\n\n"
        f"📛 <b>{html.escape(char.get('name', '?'))}</b> — "
        f"<code>{html.escape(char_id)}</code>\n"
        f"💰 Price: <b>{price}</b> coins\n\n"
        f"🆔 Listing ID: <code>{sale_id}</code>\n"
        f"📢 Posted to the P2P market channel.",
        parse_mode="HTML",
    )


async def p2p_buy_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 🛒 BUY button press from the P2P channel."""
    query = update.callback_query
    buyer = query.from_user
    # NOTE: do NOT call query.answer() here early — we need show_alert for errors/success below.

    data = query.data  # "p2p_buy_<sale_id>"
    sale_id = data[len("p2p_buy_"):]

    # Fetch the listing
    listing = await p2p_sales_collection.find_one({"sale_id": sale_id})
    if not listing:
        await query.answer("❌ Listing not found.", show_alert=True)
        return

    if listing["status"] != "active":
        await query.answer("❌ This item has already been sold.", show_alert=True)
        return

    if listing["seller_id"] == buyer.id:
        await query.answer("❌ You cannot buy your own listing!", show_alert=True)
        return

    price = listing["price"]
    char_id = listing["char_id"]

    # Check buyer balance
    buyer_data = await users_collection.find_one({"id": buyer.id})
    buyer_coins = buyer_data.get("coins", 0) if buyer_data else 0
    if buyer_coins < price:
        await query.answer(
            f"❌ Not enough coins!\nYou have {buyer_coins}, need {price}.",
            show_alert=True
        )
        return

    # Deduct coins from buyer
    await users_collection.update_one({"id": buyer.id}, {"$inc": {"coins": -price}})

    # Add coins to seller
    await users_collection.update_one(
        {"id": listing["seller_id"]},
        {"$inc": {"coins": price}},
        upsert=True
    )

    # Add character to buyer's harem
    await users_collection.update_one(
        {"id": buyer.id},
        {
            "$push": {"waifus": char_id},
            "$set": {"name": buyer.first_name, "username": buyer.username}
        },
        upsert=True
    )

    # Mark listing as sold
    await p2p_sales_collection.update_one(
        {"sale_id": sale_id},
        {
            "$set": {
                "status": "sold",
                "buyer_id": buyer.id,
                "buyer_name": buyer.first_name,
                "sold_at": time.time(),
            }
        }
    )

    # Edit the channel message to show SOLD
    rarity = listing.get("char_rarity", "Common")
    r_emoji = RARITY_EMOJI.get(rarity, "\U0001f4ae")
    ctype = _type_label(listing.get("char_type", "normal"))
    sold_caption = (
        f"✅ <b>SOLD!</b>\n\n"
        f"📛 <b>Name:</b> {html.escape(listing.get('char_name', '?'))}\n"
        f"📺 <b>Series:</b> {html.escape(listing.get('char_anime', '?'))}\n"
        f"{r_emoji} <b>Rarity:</b> {html.escape(rarity)}\n"
        f"🔖 <b>Type:</b> {html.escape(ctype)}\n\n"
        f"💰 <b>Price:</b> <b>{price}</b> coins\n"
        f"👤 <b>Seller:</b> {html.escape(listing.get('seller_name', '?'))}\n"
        f"🛍️ <b>Buyer:</b> {html.escape(buyer.first_name)}"
    )
    try:
        await context.bot.edit_message_caption(
            chat_id=P2P_CHANNEL_ID,
            message_id=listing["channel_msg_id"],
            caption=sold_caption,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ SOLD", callback_data="p2p_sold_noop")]
            ])
        )
    except BadRequest:
        pass  # Message might have been deleted; proceed anyway

    # Send sold log to log channel
    try:
        await context.bot.send_message(
            chat_id=LOG_CHAT_ID,
            text=(
                f"🛒 <b>P2P Sale Completed</b>\n\n"
                f"📛 <b>Character:</b> {html.escape(listing.get('char_name', '?'))} "
                f"[<code>{html.escape(char_id)}</code>]\n"
                f"{r_emoji} <b>Rarity:</b> {html.escape(rarity)}\n"
                f"💰 <b>Price:</b> {price} coins\n"
                f"👤 <b>Seller:</b> {html.escape(listing.get('seller_name', '?'))} "
                f"[<code>{listing['seller_id']}</code>]\n"
                f"🛍️ <b>Buyer:</b> {html.escape(buyer.first_name)} "
                f"[<code>{buyer.id}</code>]"
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass  # Log failure should never block the transaction

    # Notify buyer with success alert
    await query.answer(
        f"✅ Purchase successful!\n{listing.get('char_name','?')} is now in your harem.",
        show_alert=True
    )


async def mysells_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /mysells - View your active listings and sold history.
    """
    user = update.effective_user

    active_cursor = p2p_sales_collection.find(
        {"seller_id": user.id, "status": "active"},
        sort=[("created_at", -1)]
    )
    sold_cursor = p2p_sales_collection.find(
        {"seller_id": user.id, "status": "sold"},
        sort=[("sold_at", -1)],
    )

    active_listings = await active_cursor.to_list(length=20)
    sold_listings = await sold_cursor.to_list(length=20)

    if not active_listings and not sold_listings:
        await update.message.reply_text(
            "📭 You have no sale listings yet.\n"
            "Use /sell &lt;character_id&gt; &lt;price&gt; to list a character!",
            parse_mode="HTML",
        )
        return

    lines = ["<b>🏪 My P2P Sales</b>\n"]

    if active_listings:
        lines.append("🔵 <b>Active Listings</b>")
        for s in active_listings:
            rarity = s.get("char_rarity", "Common")
            r_emoji = RARITY_EMOJI.get(rarity, "\U0001f4ae")
            ctype = _type_label(s.get("char_type", "normal"))
            lines.append(
                f"{r_emoji} <b>{html.escape(s.get('char_name','?'))}</b> "
                f"[<code>{html.escape(s['char_id'])}</code>]\n"
                f"   📺 {html.escape(s.get('char_anime','?'))} | 🔖 {html.escape(ctype)}\n"
                f"   💰 Price: <b>{s['price']}</b> coins\n"
                f"   🆔 <code>{s['sale_id']}</code>"
            )
        lines.append("")

    if sold_listings:
        lines.append("✅ <b>Sold</b>")
        for s in sold_listings:
            rarity = s.get("char_rarity", "Common")
            r_emoji = RARITY_EMOJI.get(rarity, "\U0001f4ae")
            ctype = _type_label(s.get("char_type", "normal"))
            sold_time = ""
            if s.get("sold_at"):
                dt = datetime.fromtimestamp(s["sold_at"], tz=timezone.utc)
                sold_time = f" on {dt.strftime('%b %d, %H:%M UTC')}"
            lines.append(
                f"{r_emoji} <b>{html.escape(s.get('char_name','?'))}</b> "
                f"[<code>{html.escape(s['char_id'])}</code>]\n"
                f"   📺 {html.escape(s.get('char_anime','?'))} | 🔖 {html.escape(ctype)}\n"
                f"   💰 Sold for: <b>{s['price']}</b> coins{sold_time}\n"
                f"   🛍️ Buyer: {html.escape(s.get('buyer_name','?'))}"
            )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
