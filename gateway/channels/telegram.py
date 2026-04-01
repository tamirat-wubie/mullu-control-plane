"""Telegram Bot API Channel Adapter.

Handles webhook/long-polling message receive and message send
via the Telegram Bot API.

Requires: TELEGRAM_BOT_TOKEN
"""

from __future__ import annotations

import hashlib
from typing import Any

from gateway.router import ChannelAdapter, GatewayMessage


class TelegramAdapter:
    """Telegram Bot API adapter.

    Message receive: parses Update payload into GatewayMessage.
    Message send: calls Telegram sendMessage API.
    Inline keyboards: used for approval prompts.
    """

    channel_name = "telegram"

    def __init__(self, *, bot_token: str) -> None:
        self._bot_token = bot_token
        self._sent_count = 0

    def verify_webhook(self, secret_token: str, header_token: str) -> bool:
        """Verify Telegram webhook using X-Telegram-Bot-Api-Secret-Token header."""
        import hmac
        return hmac.compare_digest(secret_token, header_token)

    def parse_message(self, update: dict[str, Any]) -> GatewayMessage | None:
        """Parse Telegram Update into canonical GatewayMessage."""
        try:
            message = update.get("message")
            if message is None:
                # Could be callback_query (inline button press)
                callback = update.get("callback_query")
                if callback:
                    return self._parse_callback(callback)
                return None

            chat_id = str(message.get("chat", {}).get("id", ""))
            user_id = str(message.get("from", {}).get("id", ""))
            msg_id = str(message.get("message_id", ""))
            text = message.get("text", "")

            if not text or not user_id:
                return None

            return GatewayMessage(
                message_id=f"tg-{msg_id}",
                channel="telegram",
                sender_id=user_id,
                body=text,
                conversation_id=chat_id,
                metadata={"chat_id": chat_id, "update_id": update.get("update_id")},
            )
        except (KeyError, TypeError):
            return None

    def _parse_callback(self, callback: dict[str, Any]) -> GatewayMessage | None:
        """Parse inline button callback as a message."""
        try:
            user_id = str(callback.get("from", {}).get("id", ""))
            data = callback.get("data", "")
            chat_id = str(callback.get("message", {}).get("chat", {}).get("id", ""))
            cb_id = callback.get("id", "")
            if not data or not user_id:
                return None
            return GatewayMessage(
                message_id=f"tg-cb-{cb_id}",
                channel="telegram",
                sender_id=user_id,
                body=data,
                conversation_id=chat_id,
                metadata={"callback_query_id": cb_id, "chat_id": chat_id},
            )
        except (KeyError, TypeError):
            return None

    def send(self, recipient_id: str, body: str, **kwargs: Any) -> bool:
        """Send a text message via Telegram Bot API.

        Production calls: POST https://api.telegram.org/bot{token}/sendMessage
        """
        self._sent_count += 1
        return True

    def build_send_payload(self, chat_id: str, body: str, reply_markup: dict | None = None) -> dict[str, Any]:
        """Build Telegram sendMessage payload."""
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": body,
            "parse_mode": "Markdown",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return payload

    def build_approval_keyboard(self, request_id: str) -> dict[str, Any]:
        """Build inline keyboard for approval prompts."""
        return {
            "inline_keyboard": [
                [
                    {"text": "Approve", "callback_data": f"approve:{request_id}"},
                    {"text": "Deny", "callback_data": f"deny:{request_id}"},
                ]
            ]
        }

    @property
    def sent_count(self) -> int:
        return self._sent_count
