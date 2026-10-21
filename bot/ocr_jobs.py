"""Read document images locally after an application reaches the operator."""
import asyncio
import logging

from bot.handlers.operator import build_operator_keyboard

logger = logging.getLogger(__name__)


async def inspect_application(context, app_key):
    record = context.bot_data.get("app_messages", {}).get(app_key)
    if not record:
        return
    data = dict(record.get("ocr_sources", {}), car_plate=record.get("car_plate"))
    try:
        from bot.document_ocr import extract_documents
        result = await asyncio.wait_for(extract_documents(context.bot, data), timeout=55)
    except Exception as error:
        logger.warning("SAFAR OCR failed: %s", type(error).__name__)
        result = {"status": "unavailable", "values": {}, "backend": "local"}
    record = context.bot_data.get("app_messages", {}).get(app_key)
    if not record:
        return
    record["ocr_result"] = result
    record.pop("ocr_sources", None)
    from bot.operator_card import render_card
    text = render_card(record.get('code', app_key),
                       record.get('applicant_link', 'Arizachi'),
                       record.get('entered_name', record.get('applicant_name')),
                       record.get('phone'), record.get('car_plate'), result)
    record["display_text"] = text
    try:
        await context.bot.edit_message_text(
            chat_id=record["group_chat_id"], message_id=record["kb_msg_id"],
            text=text, parse_mode="HTML",
            reply_markup=build_operator_keyboard(app_key,
                context.bot_data.get("progress_state", {}).get(app_key, False),
                "review" if record.get("queue_kind") else "main"),
        )
    except Exception as error:
        logger.warning("SAFAR OCR text update failed: %s", type(error).__name__)
