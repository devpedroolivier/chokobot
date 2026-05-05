"""Regressão: dedupe de reply duplicada (#9).

Antes da correção, ~3% dos inbounds geravam 2 AiReplyGeneratedEvents idênticos
em <3s. A guarda dedupa por hash do reply em janela de 10s.
"""
import asyncio
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.estados import (
    get_recent_bot_reply,
    set_recent_bot_reply,
)


class ReplyDedupeStoreTests(unittest.TestCase):
    def test_set_and_get(self):
        phone = "5599998888777"
        ts = datetime.now(ZoneInfo("UTC"))
        set_recent_bot_reply(phone, "abc123", ts)
        out = get_recent_bot_reply(phone)
        self.assertIsNotNone(out)
        self.assertEqual(out["hash"], "abc123")

    def test_overwrite(self):
        phone = "5599998888776"
        t1 = datetime.now(ZoneInfo("UTC"))
        set_recent_bot_reply(phone, "h1", t1)
        t2 = t1 + timedelta(seconds=15)
        set_recent_bot_reply(phone, "h2", t2)
        self.assertEqual(get_recent_bot_reply(phone)["hash"], "h2")


if __name__ == "__main__":
    unittest.main()
