"""Operator-side callbacks: Tayyor / Izoh berish buttons under each application.

Two-way relay chat:
  Operator -> "Izoh berish" -> user receives comment + "💬 Javob yozish" button
  User presses button -> types reply -> forwarded back to operator group
  Operator can reply again via "Izoh berish" — cycle continues.
"""
import asyncio
import logging
from html import escape as h

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.config import ARCHIVE_GROUP

logger = logging.getLogger(__name__)

READY_TEXT = (
    "✅ Arizangiz ko‘rib chiqildi. WB SAFAR TAXI bilan ishlash bo‘yicha "
    "operatorimiz tez orada siz bilan bog‘lanadi.\n\n"
    "Savollar uchun: @WBsafarTAXI"
)


def build_operator_keyboard(applicant_user_id: int | str, in_progress: bool = False,
                            stage: str = "main") -> InlineKeyboardMarkup:
    progress_btn = InlineKeyboardButton(
        "Jarayonda🟡" if in_progress else "Jarayonda🔴",
        callback_data=f"op:progress:{applicant_user_id}",
    )
    rows = [[InlineKeyboardButton("✅ Tayyor", callback_data=f"op:ready:{applicant_user_id}"),
             progress_btn]]
    if stage == "main":
        rows.extend([
            [InlineKeyboardButton("💬 Izoh berish", callback_data=f"op:comment:{applicant_user_id}")],
            [InlineKeyboardButton("📷 Chala rasm", callback_data=f"op:incomplete:{applicant_user_id}"),
             InlineKeyboardButton("🚕 Boshqa park", callback_data=f"op:otherpark:{applicant_user_id}")],
        ])
    rows.extend([
        [InlineKeyboardButton("📦 Hujjatlarni ZIP yuklash", callback_data=f"op:download:{applicant_user_id}")],
        [InlineKeyboardButton("🗑 O‘chirish", callback_data=f"op:delete:{applicant_user_id}")],
    ])
    return InlineKeyboardMarkup(rows)


def _reply_keyboard(group_chat_id: int) -> InlineKeyboardMarkup:
    """Inline button shown to the user under the operator's comment."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("💬 Javob yozish", callback_data=f"user:reply:{group_chat_id}")]]
    )


# ------------------------------------------------------------------ #
#  OPERATOR SIDE                                                       #
# ------------------------------------------------------------------ #

async def on_operator_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    parts = query.data.split(":", 2)
    if len(parts) != 3 or parts[0] != "op":
        return
    action, raw_key = parts[1], parts[2]
    app_key = raw_key if raw_key.startswith("s") else int(raw_key) if raw_key.isdigit() else None
    if app_key is None:
        await query.answer("Ariza kodi noto‘g‘ri.", show_alert=True)
        return
    record = context.bot_data.get("app_messages", {}).get(app_key)
    if action in ("ready", "progress", "incomplete", "otherpark", "delete", "confirm", "download", "cancel", "comment"):
        if (not record or not update.effective_chat or not query.message or
                int(record.get("group_chat_id", 0)) != update.effective_chat.id or
                record.get("kb_msg_id") != query.message.message_id):
            await query.answer("Bu ariza tugmasi eskirgan. Yangi arizani oching.", show_alert=True)
            return
    if action == "cancel":
        await query.answer()
        if record and query.message.message_id == record.get("kb_msg_id"):
            await query.edit_message_reply_markup(reply_markup=build_operator_keyboard(
                app_key, context.bot_data.get("progress_state", {}).get(app_key, False),
                stage="review" if record.get("queue_kind") else "main"))
        return
    if action == "delete":
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🗑 Tasdiqlash", callback_data=f"op:confirm:{app_key}"),
            InlineKeyboardButton("Bekor qilish", callback_data=f"op:cancel:{app_key}"),
        ]]))
        return
    if action == "confirm":
        await query.answer()
        from bot.application_actions import delete_messages, checkpoint
        failed = await delete_messages(context.bot, record)
        if failed:
            await query.message.reply_text("Ba’zi xabarlarni o‘chirib bo‘lmadi. Botga o‘chirish huquqini bering.")
            return
        context.bot_data.get("app_messages", {}).pop(app_key, None)
        context.bot_data.get("progress_state", {}).pop(app_key, None)
        await checkpoint(context)
        return
    if action in ("ready", "incomplete", "otherpark"):
        await query.answer()
        from bot.application_actions import move
        if record.get("queue_kind") and action in ("incomplete", "otherpark"):
            await query.message.reply_text("Bu ariza allaqachon alohida navbatda.")
            return
        success, message = await move(context, app_key, record, action)
        if not success:
            await query.message.reply_text(message)
        elif action == "ready":
            try:
                await context.bot.send_message(chat_id=record["applicant_id"], text=READY_TEXT)
            except Exception:
                logger.warning("Applicant ready notice could not be delivered")
        return
    if action == "download":
        await query.answer("ZIP tayyorlanmoqda...")
        from bot.application_download import send_archive
        try:
            sent = await send_archive(context.bot, record, update.effective_chat.id,
                                      record["kb_msg_id"])
            record.setdefault("zip_msg_ids", []).append(sent.message_id)
        except Exception as error:
            logger.warning("ZIP could not be delivered (%s)", type(error).__name__)
            await query.message.reply_text("ZIPni tayyorlab bo‘lmadi. Hujjatlarni guruhdagi rasmlardan ko‘ring.")
        return
    if action == "progress":
        await query.answer()
        states = context.bot_data.setdefault("progress_state", {})
        states[app_key] = not states.get(app_key, False)
        await query.edit_message_reply_markup(reply_markup=build_operator_keyboard(
            app_key, states[app_key], stage="review" if record.get("queue_kind") else "main"))
        return
    if action == "comment":
        await query.answer()
        operator = update.effective_user
        chat_id = update.effective_chat.id if update.effective_chat else None
        if not operator or chat_id is None:
            return
        applicant_id = record.get("applicant_id") if record else app_key
        if not isinstance(applicant_id, int):
            await query.message.reply_text("Arizachining IDsi topilmadi.")
            return
        context.bot_data.setdefault("pending_comments", {})[(chat_id, operator.id)] = applicant_id
        info = context.bot_data.get("applicant_info", {}).get(applicant_id, {})
        name = h(info.get("name") or "Arizachi")
        link = f'<a href="tg://user?id={applicant_id}">{name}</a>'
        prompt = await context.bot.send_message(
            chat_id=chat_id,
            text=f"💬 <b>Izoh kiriting</b> → {link}\n👤 Operator: {h(operator.full_name)}\n\nBekor qilish uchun: /bekor",
            parse_mode="HTML", reply_to_message_id=query.message.message_id)
        context.bot_data.setdefault("pending_prompts", {})[(chat_id, operator.id)] = prompt.message_id


async def on_operator_text_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catch operator text in a group when a comment is pending."""
    msg = update.message
    if not msg or not msg.text:
        return
    chat = update.effective_chat
    operator = update.effective_user
    if not chat or not operator:
        return

    pending = context.bot_data.get("pending_comments", {})
    key = (chat.id, operator.id)
    applicant_id = pending.get(key)
    if applicant_id is None:
        return

    text = msg.text.strip()

    if text.lower() in ("/bekor", "bekor"):
        pending.pop(key, None)
        await msg.reply_text("❌ Izoh bekor qilindi.")
        return

    op_name = operator.full_name or "Operator"
    try:
        await context.bot.send_message(
            chat_id=applicant_id,
            text=f"💬 <b>WB SAFAR TAXI — Operator izohi:</b>\n\n{h(text)}",
            parse_mode="HTML",
            reply_markup=_reply_keyboard(chat.id),
        )
        await msg.reply_text(
            f"✅ Izoh arizachiga yuborildi.\n👤 Operator: {op_name}"
        )
    except Exception as e:
        logger.warning("Comment delivery failed (%s)", type(e).__name__)
        await msg.reply_text(
            "⚠️ Izoh yuborilmadi. Arizachi botni bloklagan bo‘lishi mumkin."
        )
    finally:
        pending.pop(key, None)


# ------------------------------------------------------------------ #
#  USER SIDE  (reply to operator comment)                              #
# ------------------------------------------------------------------ #

async def on_user_reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User pressed '💬 Javob yozish' under an operator comment."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    parts = query.data.split(":", 2)
    if len(parts) != 3 or parts[0] != "user" or parts[1] != "reply":
        return
    try:
        group_chat_id = int(parts[2])
    except ValueError:
        return

    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return

    context.bot_data.setdefault("pending_user_replies", {})[user_id] = group_chat_id

    await query.message.reply_text(
        "✏️ Javobingizni yozing:\n\nBekor qilish uchun: /bekor",
    )


async def on_user_reply_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forward the user's reply to the operator group."""
    msg = update.message
    if not msg:
        return
    user = update.effective_user
    if not user:
        return

    pending = context.bot_data.get("pending_user_replies", {})
    group_chat_id = pending.get(user.id)
    if group_chat_id is None:
        return

    text = (msg.text or "").strip()
    if not text:
        await msg.reply_text("❗ Iltimos, matn yozing.")
        return

    if text.lower() in ("/bekor", "bekor"):
        pending.pop(user.id, None)
        await msg.reply_text("❌ Javob bekor qilindi.")
        return

    user_link = (
        f'<a href="https://t.me/{user.username}">{h(user.full_name)}</a>'
        if user.username
        else f'<a href="tg://user?id={user.id}">{h(user.full_name or "Foydalanuvchi")}</a>'
    )

    context.bot_data.setdefault("applicant_info", {})[user.id] = {
        "name": user.full_name or "Arizachi",
        "username": user.username or "",
    }

    try:
        await context.bot.send_message(
            chat_id=group_chat_id,
            text=(
                f"📩 <b>Arizachi javobi:</b>\n"
                f"👤 {user_link}\n\n"
                f"{h(text)}"
            ),
            parse_mode="HTML",
            reply_markup=build_operator_keyboard(user.id),
        )
        await msg.reply_text("✅ Javobingiz operatorlarga yuborildi.")
    except Exception as e:
        logger.warning("Applicant reply failed (%s)", type(e).__name__)
        await msg.reply_text("⚠️ Javob yuborilmadi. Birozdan so‘ng qayta urinib ko‘ring.")
    finally:
        pending.pop(user.id, None)


# ------------------------------------------------------------------ #
#  REGISTRATION                                                        #
# ------------------------------------------------------------------ #

def register_operator_handlers(app):
    app.add_handler(CallbackQueryHandler(on_operator_button, pattern=r"^op:"))
    app.add_handler(CallbackQueryHandler(on_user_reply_button, pattern=r"^user:reply:"))
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
            on_operator_text_in_group,
        ),
        group=1,
    )
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            on_user_reply_message,
        ),
        group=2,
    )
