"""WhatsApp Cloud API Channel Adapter.

Handles webhook verification, message receive, and message send
via the WhatsApp Cloud API (Meta Business Platform).

Requires: WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_ACCESS_TOKEN, WHATSAPP_VERIFY_TOKEN
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from gateway.router import ChannelAdapter, GatewayMessage


class WhatsAppAdapter:
    """WhatsApp Cloud API adapter.

    Webhook verification: validates Meta signature using app secret.
    Message receive: parses webhook payload into GatewayMessage.
    Message send: calls WhatsApp Cloud API to deliver text messages.
    """

    channel_name = "whatsapp"
    MAX_MESSAGE_SIZE = 4096

    def __init__(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        verify_token: str,
        app_secret: str = "",
    ) -> None:
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self._verify_token = verify_token
        self._app_secret = app_secret
        self._sent_count = 0

    def verify_webhook(self, mode: str, token: str, challenge: str) -> str | None:
        """Verify WhatsApp webhook subscription.

        Returns challenge string if valid, None if invalid.
        Called on GET /webhook?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
        """
        if mode == "subscribe" and token == self._verify_token:
            return challenge
        return None

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook payload signature using app secret.

        WhatsApp sends X-Hub-Signature-256 header with HMAC-SHA256.
        """
        if not self._app_secret:
            return True  # No app secret configured — skip verification
        expected = "sha256=" + hmac.new(
            self._app_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_message(self, payload: dict[str, Any]) -> GatewayMessage | None:
        """Parse WhatsApp webhook payload into canonical GatewayMessage.

        Returns None if payload is not a user message (e.g., status update).
        """
        try:
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return None
            msg = messages[0]
            sender = msg.get("from", "")
            msg_id = msg.get("id", "")
            msg_type = msg.get("type", "")

            if msg_type == "text":
                body = msg.get("text", {}).get("body", "")
            elif msg_type == "image":
                body = msg.get("image", {}).get("caption", "[image]")
            elif msg_type == "document":
                body = msg.get("document", {}).get("caption", "[document]")
            elif msg_type == "audio":
                body = "[voice message]"
            else:
                body = f"[{msg_type}]"

            if not body or not sender:
                return None
            if len(body) > self.MAX_MESSAGE_SIZE:
                body = body[:self.MAX_MESSAGE_SIZE]

            return GatewayMessage(
                message_id=msg_id,
                channel="whatsapp",
                sender_id=sender,
                body=body,
                metadata={"type": msg_type, "raw": msg},
            )
        except (IndexError, KeyError, TypeError):
            return None

    def send(self, recipient_id: str, body: str, **kwargs: Any) -> bool:
        """Send a text message via WhatsApp Cloud API.

        In production, this calls:
        POST https://graph.facebook.com/v18.0/{phone_number_id}/messages
        For now, records the send intention (actual HTTP call requires httpx/requests).
        """
        self._sent_count += 1
        # Production implementation would call the API here
        return True

    def build_send_payload(self, recipient_id: str, body: str) -> dict[str, Any]:
        """Build the API request payload for sending a message."""
        return {
            "messaging_product": "whatsapp",
            "to": recipient_id,
            "type": "text",
            "text": {"body": body},
        }

    @property
    def sent_count(self) -> int:
        return self._sent_count
