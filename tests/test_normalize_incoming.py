import os
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.utils.payload import (
    is_evolution_payload,
    is_group_message,
    normalize_incoming,
)


def _evo_direct(text="Oi, quero um bolo", from_me=False, push_name="Ana"):
    return {
        "event": "messages.upsert",
        "instance": "chokodelicia",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": from_me,
                "id": "3EB0ABC123",
            },
            "pushName": push_name,
            "messageTimestamp": 1745423700,
            "message": {"conversation": text},
        },
    }


def _evo_group():
    return {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "120363000000000000@g.us",
                "fromMe": False,
                "id": "GROUPID",
            },
            "pushName": "Grupo",
            "message": {"conversation": "msg em grupo"},
        },
    }


def _evo_extended():
    return {
        "data": {
            "key": {
                "remoteJid": "5511988887777@s.whatsapp.net",
                "fromMe": False,
                "id": "X1",
            },
            "pushName": "Bia",
            "message": {
                "extendedTextMessage": {"text": "olha este link", "previewType": "NONE"}
            },
        },
    }


def _zapi_legacy():
    return {
        "phone": "5511977776666",
        "fromMe": False,
        "chatName": "Carlos",
        "messageId": "ZAPI1",
        "text": {"message": "oi pela z-api"},
        "type": "text",
    }


class NormalizeIncomingTests(unittest.TestCase):
    def test_detects_evolution_payload(self):
        self.assertTrue(is_evolution_payload(_evo_direct()))
        self.assertFalse(is_evolution_payload(_zapi_legacy()))
        self.assertFalse(is_evolution_payload({}))

    def test_evolution_direct_message(self):
        norm = normalize_incoming(_evo_direct())
        self.assertEqual(norm["text"], "Oi, quero um bolo")
        self.assertEqual(norm["phone"], "5511999999999")
        self.assertEqual(norm["chat_name"], "Ana")
        self.assertEqual(norm["message_id"], "3EB0ABC123")
        self.assertEqual(norm["message_type"], "conversation")
        self.assertFalse(norm["from_me"])
        self.assertFalse(norm["is_group"])

    def test_evolution_from_me_true(self):
        norm = normalize_incoming(_evo_direct(from_me=True))
        self.assertTrue(norm["from_me"])

    def test_evolution_group_message_flagged(self):
        payload = _evo_group()
        self.assertTrue(is_group_message(payload))
        norm = normalize_incoming(payload)
        self.assertTrue(norm["is_group"])
        # phone local part preserved without @g.us suffix
        self.assertEqual(norm["phone"], "120363000000000000")

    def test_evolution_extended_text_message(self):
        norm = normalize_incoming(_evo_extended())
        self.assertEqual(norm["text"], "olha este link")
        self.assertEqual(norm["phone"], "5511988887777")
        self.assertEqual(norm["chat_name"], "Bia")
        self.assertEqual(norm["message_type"], "extendedTextMessage")

    def test_zapi_payload_still_works(self):
        norm = normalize_incoming(_zapi_legacy())
        self.assertEqual(norm["text"], "oi pela z-api")
        self.assertEqual(norm["phone"], "5511977776666")
        self.assertEqual(norm["chat_name"], "Carlos")
        self.assertEqual(norm["message_id"], "ZAPI1")
        self.assertFalse(norm["from_me"])
        self.assertFalse(norm["is_group"])

    def test_zapi_push_name_default_when_missing(self):
        norm = normalize_incoming({"phone": "5511900000000", "text": {"message": "x"}})
        self.assertEqual(norm["chat_name"], "Desconhecido")


if __name__ == "__main__":
    unittest.main()
