"""Channel Adapter Tests.

Tests: WhatsApp, Telegram, and Web adapters — message parsing,
    webhook verification, send payloads.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest
from gateway.channels.whatsapp import WhatsAppAdapter
from gateway.channels.telegram import TelegramAdapter
from gateway.channels.web import WebChatAdapter


# ═══ WhatsApp ═══


class TestWhatsAppAdapter:
    def test_verify_webhook_valid(self):
        adapter = WhatsAppAdapter(
            phone_number_id="123", access_token="tok",
            verify_token="my_verify", app_secret="secret",
        )
        result = adapter.verify_webhook("subscribe", "my_verify", "challenge_123")
        assert result == "challenge_123"

    def test_verify_webhook_invalid(self):
        adapter = WhatsAppAdapter(
            phone_number_id="123", access_token="tok",
            verify_token="my_verify",
        )
        assert adapter.verify_webhook("subscribe", "wrong_token", "challenge") is None

    def test_verify_signature(self):
        adapter = WhatsAppAdapter(
            phone_number_id="123", access_token="tok",
            verify_token="v", app_secret="secret",
        )
        import hmac, hashlib
        payload = b'{"test": "data"}'
        sig = "sha256=" + hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
        assert adapter.verify_signature(payload, sig) is True

    def test_verify_signature_no_secret(self):
        adapter = WhatsAppAdapter(
            phone_number_id="123", access_token="tok", verify_token="v",
        )
        assert adapter.verify_signature(b"anything", "anything") is True

    def test_parse_text_message(self):
        adapter = WhatsAppAdapter(
            phone_number_id="123", access_token="tok", verify_token="v",
        )
        payload = {
            "entry": [{"changes": [{"value": {
                "messages": [{
                    "from": "+1234567890",
                    "id": "wamid.abc123",
                    "type": "text",
                    "text": {"body": "Hello agent"},
                }]
            }}]}]
        }
        msg = adapter.parse_message(payload)
        assert msg is not None
        assert msg.channel == "whatsapp"
        assert msg.sender_id == "+1234567890"
        assert msg.body == "Hello agent"
        assert msg.message_id == "wamid.abc123"

    def test_parse_image_message(self):
        adapter = WhatsAppAdapter(
            phone_number_id="123", access_token="tok", verify_token="v",
        )
        payload = {
            "entry": [{"changes": [{"value": {
                "messages": [{
                    "from": "+1234567890",
                    "id": "wamid.img1",
                    "type": "image",
                    "image": {"caption": "Check this out"},
                }]
            }}]}]
        }
        msg = adapter.parse_message(payload)
        assert msg is not None
        assert msg.body == "Check this out"

    def test_parse_empty_payload(self):
        adapter = WhatsAppAdapter(
            phone_number_id="123", access_token="tok", verify_token="v",
        )
        assert adapter.parse_message({}) is None
        assert adapter.parse_message({"entry": []}) is None

    def test_send_increments_count(self):
        adapter = WhatsAppAdapter(
            phone_number_id="123", access_token="tok", verify_token="v",
        )
        assert adapter.sent_count == 0
        adapter.send("+1234567890", "Hello")
        assert adapter.sent_count == 1

    def test_build_send_payload(self):
        adapter = WhatsAppAdapter(
            phone_number_id="123", access_token="tok", verify_token="v",
        )
        payload = adapter.build_send_payload("+1234567890", "Hi there")
        assert payload["messaging_product"] == "whatsapp"
        assert payload["to"] == "+1234567890"
        assert payload["text"]["body"] == "Hi there"


# ═══ Telegram ═══


class TestTelegramAdapter:
    def test_verify_webhook(self):
        adapter = TelegramAdapter(bot_token="123:ABC")
        assert adapter.verify_webhook("my_secret", "my_secret") is True
        assert adapter.verify_webhook("my_secret", "wrong") is False

    def test_parse_text_message(self):
        adapter = TelegramAdapter(bot_token="123:ABC")
        update = {
            "update_id": 123456,
            "message": {
                "message_id": 42,
                "from": {"id": 98765},
                "chat": {"id": 98765},
                "text": "Hello from Telegram",
            }
        }
        msg = adapter.parse_message(update)
        assert msg is not None
        assert msg.channel == "telegram"
        assert msg.sender_id == "98765"
        assert msg.body == "Hello from Telegram"
        assert msg.conversation_id == "98765"

    def test_parse_callback_query(self):
        adapter = TelegramAdapter(bot_token="123:ABC")
        update = {
            "callback_query": {
                "id": "cb123",
                "from": {"id": 98765},
                "message": {"chat": {"id": 98765}},
                "data": "approve:req-abc",
            }
        }
        msg = adapter.parse_message(update)
        assert msg is not None
        assert msg.body == "approve:req-abc"

    def test_parse_empty_update(self):
        adapter = TelegramAdapter(bot_token="123:ABC")
        assert adapter.parse_message({}) is None

    def test_send_increments_count(self):
        adapter = TelegramAdapter(bot_token="123:ABC")
        adapter.send("98765", "Reply")
        assert adapter.sent_count == 1

    def test_build_approval_keyboard(self):
        adapter = TelegramAdapter(bot_token="123:ABC")
        kb = adapter.build_approval_keyboard("req-abc")
        assert "inline_keyboard" in kb
        buttons = kb["inline_keyboard"][0]
        assert len(buttons) == 2
        assert buttons[0]["text"] == "Approve"
        assert buttons[1]["callback_data"] == "deny:req-abc"


# ═══ Web Chat ═══


class TestWebChatAdapter:
    def test_parse_message(self):
        adapter = WebChatAdapter()
        msg = adapter.parse_message(
            {"body": "Hello from web", "user_id": "web-user-1"},
            session_token="sess123",
        )
        assert msg is not None
        assert msg.channel == "web"
        assert msg.sender_id == "web-user-1"
        assert msg.body == "Hello from web"

    def test_parse_empty_message(self):
        adapter = WebChatAdapter()
        assert adapter.parse_message({}) is None

    def test_parse_uses_session_token_as_fallback(self):
        adapter = WebChatAdapter()
        msg = adapter.parse_message({"body": "hi"}, session_token="sess-xyz")
        assert msg.sender_id == "sess-xyz"

    def test_send_increments_count(self):
        adapter = WebChatAdapter()
        adapter.send("user1", "Response")
        assert adapter.sent_count == 1

    def test_connection_management(self):
        adapter = WebChatAdapter()
        assert adapter.active_connections == 0
        adapter.register_connection("sess1", "ws_obj")
        assert adapter.active_connections == 1
        adapter.remove_connection("sess1")
        assert adapter.active_connections == 0
