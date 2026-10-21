"""Operator controls for SAFAR applications."""
import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
)

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
            [InlineKeyboardButton("📷 Chala rasm", callback_data=f"op:incomplete:{applicant_user_id}"),
             InlineKeyboardButton("🚕 Boshqa park", callback_data=f"op:otherpark:{applicant_user_id}")],
        ])
    rows.extend([
        [InlineKeyboardButton("📦 Hujjatlarni ZIP yuklash", callback_data=f"op:download:{applicant_user_id}")],
        [InlineKeyboardButton("🗑 O‘chirish", callback_data=f"op:delete:{applicant_user_id}")],
    ])
    return InlineKeyboardMarkup(rows)


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
    if action == "comment":
        if (record and update.effective_chat and query.message and
                int(record.get("group_chat_id", 0)) == update.effective_chat.id and
                record.get("kb_msg_id") == query.message.message_id):
            try:
                await query.edit_message_reply_markup(reply_markup=build_operator_keyboard(
                    app_key, context.bot_data.get("progress_state", {}).get(app_key, False),
                    stage="review" if record.get("queue_kind") else "main"))
            except Exception as error:
                logger.warning("Old comment button could not be removed (%s)", type(error).__name__)
        await query.answer("Izoh funksiyasi olib tashlangan.", show_alert=True)
        return
    if action in ("ready", "progress", "incomplete", "otherpark", "delete", "confirm", "download", "cancel"):
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


async def on_old_user_reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answer buttons under comments sent before the feature was removed."""
    if update.callback_query:
        await update.callback_query.answer("Izoh funksiyasi olib tashlangan.", show_alert=True)


def register_operator_handlers(app):
    app.add_handler(CallbackQueryHandler(on_operator_button, pattern=r"^op:"))
    app.add_handler(CallbackQueryHandler(on_old_user_reply_button, pattern=r"^user:reply:"))
