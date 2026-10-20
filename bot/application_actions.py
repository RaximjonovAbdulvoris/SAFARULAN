"""Confirmed queue transitions for a single SAFAR application."""
import logging
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import ARCHIVE_GROUP, INCOMPLETE_GROUP, OTHER_PARK_GROUP

logger = logging.getLogger(__name__)
NOTICES = {
    "incomplete": (
        "Hujjatlaringizni ko‘rib chiqdik. Ayrim rasmlar to‘liq yoki aniq emas. "
        "Iltimos, arizani hujjatlarning tiniq va to‘liq rasmlari bilan qayta yuboring. "
        "Savollar uchun: @WBsafarTAXI"
    ),
    "otherpark": (
        "Arizangizni ko‘rib chiqdik. Ma’lumotlaringiz boshqa taksoparkda "
        "ro‘yxatda ko‘rinmoqda. O‘tish masalasini avval o‘sha park bilan "
        "hal qiling. Savollar uchun: @WBsafarTAXI"
    ),
}


def destination(action):
    return {"ready": ARCHIVE_GROUP, "incomplete": INCOMPLETE_GROUP,
            "otherpark": OTHER_PARK_GROUP}[action]


def controls(app_id, stage="main", progress=False):
    from bot.handlers.operator import build_operator_keyboard
    return build_operator_keyboard(app_id, in_progress=progress, stage=stage)


async def checkpoint(context):
    app = getattr(context, "application", None)
    if app is None or app.persistence is None:
        return True
    try:
        await app.update_persistence()
        await app.persistence.flush()
        return True
    except Exception:
        logger.error("Application state could not be saved; source cleanup blocked")
        return False


async def delete_messages(bot, record):
    chat = record["group_chat_id"]
    failed = []
    for mid in [*record.get("photo_msg_ids", []), *record.get("zip_msg_ids", []),
                record.get("kb_msg_id")]:
        if mid is None:
            continue
        try:
            await bot.delete_message(chat_id=chat, message_id=mid)
        except Exception:
            failed.append(mid)
    return failed


async def move(context, app_key, record, action):
    """Copy, persist destination, then clean source. Never delete an unconfirmed copy."""
    target = destination(action)
    if not target or not str(target).startswith("-"):
        return False, "Bu bo‘lim guruhi hali sozlanmagan. Ariza joyida qoldi."
    if str(target) == str(record["group_chat_id"]):
        return False, "Ariza o‘z guruhiga ko‘chirilmaydi."
    if record.get("transfer_key"):
        return False, "Ko‘chirish avval boshlangan. Guruhlarni tekshiring; takroriy nusxa yaratilmaydi."

    photo_ids = record.get("photo_msg_ids", [])
    copied = []
    try:
        for first in range(0, len(photo_ids), 10):
            chunk = photo_ids[first:first + 10]
            messages = await context.bot.copy_messages(
                chat_id=target, from_chat_id=record["group_chat_id"], message_ids=chunk)
            if len(messages) != len(chunk):
                raise RuntimeError("Telegram did not confirm the whole album")
            copied.extend(message.message_id for message in messages)
        text = record.get("display_text") or "📝 WB SAFAR TAXI · Ariza"
        if action != "ready":
            text += "\n\n📍 " + ("Chala rasm" if action == "incomplete" else "Boshqa park")
        reply_markup = controls(app_key, stage="review") if action != "ready" else None
        info = await context.bot.send_message(chat_id=target, text=text,
                                               parse_mode="HTML", reply_markup=reply_markup)
    except Exception as error:
        logger.warning("Application copy failed (%s)", type(error).__name__)
        return False, "Nusxalash tasdiqlanmadi. Asl ariza saqlandi; operator tekshirsin."

    if action != "ready":
        moved = dict(record, group_chat_id=int(target), photo_msg_ids=copied,
                     kb_msg_id=info.message_id, display_text=text,
                     queue_kind=action, zip_msg_ids=[], transfer_key=None)
        context.bot_data.setdefault("app_messages", {})[app_key] = moved
    else:
        record["transfer_key"] = f"archive:{info.message_id}"
    if not await checkpoint(context):
        if action != "ready":
            context.bot_data["app_messages"][app_key] = record
        else:
            record.pop("transfer_key", None)
        return False, "Yangi ariza yuborildi, lekin holat saqlanmadi. Asl ariza qoldi."

    failed = await delete_messages(context.bot, record)
    if failed:
        logger.warning("Application source cleanup incomplete: %d messages", len(failed))
    if action == "ready":
        context.bot_data.get("app_messages", {}).pop(app_key, None)
        context.bot_data.get("progress_state", {}).pop(app_key, None)
    elif action in NOTICES:
        try:
            await context.bot.send_message(chat_id=record["applicant_id"], text=NOTICES[action])
        except Exception:
            logger.warning("Applicant notice could not be delivered")
    await checkpoint(context)
    return True, "Ariza ko‘chirildi." if not failed else "Ariza ko‘chirildi; eski xabarlarni o‘chirish huquqini tekshiring."
