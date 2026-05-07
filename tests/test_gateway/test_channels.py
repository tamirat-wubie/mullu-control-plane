"""Channel Adapter Tests.

Tests: WhatsApp, Telegram, Slack, Discord, and Web adapters — message parsing,
    webhook verification, send payloads.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.channels.whatsapp import WhatsAppAdapter  # noqa: E402
from gateway.channels.slack import SlackAdapter  # noqa: E402
from gateway.channels.discord import DiscordAdapter  # noqa: E402
from gateway.channels.telegram import TelegramAdapter  # noqa: E402
from gateway.channels.web import WebChatAdapter  # noqa: E402


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
        import hmac
        import hashlib
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


# ═══ Slack ═══


class TestSlackAdapter:
    def test_verify_request_valid(self):
        import hmac as _hmac
        import hashlib as _hash
        import time as _time
        secret = "test_signing_secret"
        adapter = SlackAdapter(bot_token="xoxb-123", signing_secret=secret)
        ts = str(int(_time.time()))
        body = '{"event": {}}'
        sig_base = f"v0:{ts}:{body}"
        sig = "v0=" + _hmac.new(secret.encode(), sig_base.encode(), _hash.sha256).hexdigest()
        assert adapter.verify_request(ts, body, sig) is True

    def test_verify_request_invalid(self):
        adapter = SlackAdapter(bot_token="xoxb-123", signing_secret="secret")
        assert adapter.verify_request(str(int(__import__("time").time())), "body", "v0=wrong") is False

    def test_verify_request_replay_rejected(self):
        adapter = SlackAdapter(bot_token="xoxb-123", signing_secret="secret")
        old_ts = str(int(__import__("time").time()) - 600)
        assert adapter.verify_request(old_ts, "body", "v0=anything") is False

    def test_url_verification(self):
        adapter = SlackAdapter(bot_token="xoxb-123", signing_secret="s")
        result = adapter.handle_url_verification({"type": "url_verification", "challenge": "abc123"})
        assert result == "abc123"

    def test_url_verification_non_challenge(self):
        adapter = SlackAdapter(bot_token="xoxb-123", signing_secret="s")
        assert adapter.handle_url_verification({"type": "event_callback"}) is None

    def test_parse_message(self):
        adapter = SlackAdapter(bot_token="xoxb-123", signing_secret="s")
        payload = {
            "team_id": "T123",
            "event": {
                "type": "message",
                "user": "U456",
                "text": "Hello from Slack",
                "channel": "C789",
                "ts": "1234567890.123456",
            }
        }
        msg = adapter.parse_message(payload)
        assert msg is not None
        assert msg.channel == "slack"
        assert msg.sender_id == "U456"
        assert msg.body == "Hello from Slack"
        assert "C789" in msg.conversation_id

    def test_parse_app_mention(self):
        adapter = SlackAdapter(bot_token="xoxb-123", signing_secret="s")
        payload = {
            "event": {
                "type": "app_mention",
                "user": "U456",
                "text": "@bot help me",
                "channel": "C789",
                "ts": "1234567890.000001",
            }
        }
        msg = adapter.parse_message(payload)
        assert msg is not None
        assert msg.body == "@bot help me"

    def test_ignore_bot_messages(self):
        adapter = SlackAdapter(bot_token="xoxb-123", signing_secret="s")
        payload = {
            "event": {
                "type": "message",
                "bot_id": "B123",
                "text": "bot reply",
                "channel": "C789",
                "ts": "123.456",
            }
        }
        assert adapter.parse_message(payload) is None

    def test_ignore_subtypes(self):
        adapter = SlackAdapter(bot_token="xoxb-123", signing_secret="s")
        payload = {
            "event": {
                "type": "message",
                "subtype": "message_changed",
                "user": "U456",
                "text": "edited",
                "channel": "C789",
                "ts": "123.456",
            }
        }
        assert adapter.parse_message(payload) is None

    def test_send_increments_count(self):
        adapter = SlackAdapter(bot_token="xoxb-123", signing_secret="s")
        adapter.send("C789", "Reply")
        assert adapter.sent_count == 1

    def test_build_send_payload_with_thread(self):
        adapter = SlackAdapter(bot_token="xoxb-123", signing_secret="s")
        payload = adapter.build_send_payload("C789", "In thread", thread_ts="123.456")
        assert payload["channel"] == "C789"
        assert payload["thread_ts"] == "123.456"


# ═══ Discord ═══


class TestDiscordAdapter:
    def test_verify_interaction_no_key(self):
        adapter = DiscordAdapter(bot_token="bot-123")
        assert adapter.verify_interaction("sig", "ts", "body") is True

    def test_parse_slash_command(self):
        adapter = DiscordAdapter(bot_token="bot-123")
        payload = {
            "type": 2,  # APPLICATION_COMMAND
            "id": "inter-123",
            "guild_id": "G456",
            "channel_id": "C789",
            "member": {"user": {"id": "U111"}},
            "data": {
                "name": "ask",
                "options": [{"name": "question", "value": "what is 2+2"}],
            },
        }
        msg = adapter.parse_interaction(payload)
        assert msg is not None
        assert msg.channel == "discord"
        assert msg.sender_id == "U111"
        assert "/ask" in msg.body
        assert "what is 2+2" in msg.body

    def test_parse_button_interaction(self):
        adapter = DiscordAdapter(bot_token="bot-123")
        payload = {
            "type": 3,  # MESSAGE_COMPONENT
            "id": "inter-456",
            "guild_id": "G456",
            "channel_id": "C789",
            "member": {"user": {"id": "U111"}},
            "data": {"custom_id": "approve:req-abc"},
        }
        msg = adapter.parse_interaction(payload)
        assert msg is not None
        assert msg.body == "approve:req-abc"

    def test_parse_ping_returns_none(self):
        adapter = DiscordAdapter(bot_token="bot-123")
        assert adapter.parse_interaction({"type": 1}) is None

    def test_parse_message_create(self):
        adapter = DiscordAdapter(bot_token="bot-123")
        event = {
            "id": "msg-789",
            "author": {"id": "U111", "bot": False},
            "content": "Hello from Discord",
            "channel_id": "C789",
            "guild_id": "G456",
        }
        msg = adapter.parse_message_create(event)
        assert msg is not None
        assert msg.body == "Hello from Discord"

    def test_ignore_bot_message_create(self):
        adapter = DiscordAdapter(bot_token="bot-123")
        event = {
            "id": "msg-789",
            "author": {"id": "B111", "bot": True},
            "content": "Bot reply",
            "channel_id": "C789",
        }
        assert adapter.parse_message_create(event) is None

    def test_send_increments_count(self):
        adapter = DiscordAdapter(bot_token="bot-123")
        adapter.send("C789", "Hello")
        assert adapter.sent_count == 1

    def test_build_approval_buttons(self):
        adapter = DiscordAdapter(bot_token="bot-123")
        buttons = adapter.build_approval_buttons("req-abc")
        assert len(buttons) == 1
        components = buttons[0]["components"]
        assert len(components) == 2
        assert components[0]["label"] == "Approve"
        assert components[1]["custom_id"] == "deny:req-abc"
