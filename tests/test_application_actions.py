"""Queue moves must preserve the source until Telegram confirms the destination."""
import asyncio
import os
from types import SimpleNamespace
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

telegram = types.ModuleType("telegram")
telegram.InlineKeyboardButton = object
telegram.InlineKeyboardMarkup = object
sys.modules.setdefault("telegram", telegram)
for key in ("TELEGRAM_BOT_TOKEN", "DRIVER_GROUP_1", "DRIVER_GROUP_2",
            "DRIVER_GROUP_3", "DRIVER_GROUP_4", "BRAND_GROUP"):
    os.environ.setdefault(key, "test")

from bot import application_actions as actions


class QueueMoveTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.record = {
            "group_chat_id": -1001, "photo_msg_ids": [11, 12], "kb_msg_id": 13,
            "zip_msg_ids": [14], "display_text": "Ariza", "applicant_id": 99,
        }
        self.bot = SimpleNamespace(
            copy_messages=AsyncMock(return_value=[SimpleNamespace(message_id=21), SimpleNamespace(message_id=22)]),
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=23)),
            delete_message=AsyncMock(),
        )
        self.context = SimpleNamespace(bot=self.bot, bot_data={"app_messages": {"s1": self.record}},
                                       application=None)

    async def test_unconfigured_destination_preserves_source(self):
        with patch.object(actions, "INCOMPLETE_GROUP", ""):
            ok, _ = await actions.move(self.context, "s1", self.record, "incomplete")
        self.assertFalse(ok)
        self.bot.copy_messages.assert_not_awaited()
        self.bot.delete_message.assert_not_awaited()
        self.assertIs(self.context.bot_data["app_messages"]["s1"], self.record)

    async def test_copy_failure_preserves_source(self):
        self.bot.copy_messages.side_effect = RuntimeError("destination unavailable")
        with patch.object(actions, "INCOMPLETE_GROUP", "-2002"):
            ok, _ = await actions.move(self.context, "s1", self.record, "incomplete")
        self.assertFalse(ok)
        self.bot.delete_message.assert_not_awaited()

    async def test_successful_move_deletes_source_zip_and_updates_record(self):
        with patch.object(actions, "INCOMPLETE_GROUP", "-2002"), \
             patch.object(actions, "controls", return_value=None):
            ok, _ = await actions.move(self.context, "s1", self.record, "incomplete")
        self.assertTrue(ok)
        moved = self.context.bot_data["app_messages"]["s1"]
        self.assertEqual(moved["group_chat_id"], -2002)
        self.assertEqual(moved["photo_msg_ids"], [21, 22])
        self.assertEqual(self.bot.delete_message.await_count, 4)


if __name__ == "__main__":
    unittest.main()
