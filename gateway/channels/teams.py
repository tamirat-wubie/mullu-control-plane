"""Microsoft Teams Channel Adapter.

Handles inbound Teams Bot Framework activity webhooks and outbound chat sends
via Microsoft Graph.

Requires: MICROSOFT_TEAMS_ACCESS_TOKEN, MICROSOFT_TEAMS_SHARED_SECRET (HMAC
verification fallback for installations without full JWT validation).
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from gateway.router import GatewayMessage


class TeamsAdapter:
    """Microsoft Teams adapter.

    Webhook receive: parses Bot Framework activity payload into GatewayMessage.
    Webhook verification: HMAC-SHA256 over the raw body using the shared secret
        carried in X-Mullu-Teams-Signature. Production deployments may instead
        bind a Bot Framework JWT validator; that path is layered on top of this
        adapter at the server boundary.
    Message send: Microsoft Graph chat.send is dispatched through the signed
        messaging worker; this adapter only counts inbound intentions.
    """

    channel_name = "teams"
    MAX_MESSAGE_SIZE = 8192

    def __init__(
        self,
        *,
        access_token: str,
        shared_secret: str = "",
    ) -> None:
        self._access_token = access_token
        self._shared_secret = shared_secret
        self._sent_count = 0

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook payload signature using shared secret."""
        if not self._shared_secret:
            return False
        expected = "sha256=" + hmac.new(
            self._shared_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_message(self, payload: dict[str, Any]) -> GatewayMessage | None:
        """Parse a Bot Framework activity into a GatewayMessage."""
        try:
            activity_type = str(payload.get("type", "")).strip()
            if activity_type and activity_type != "message":
                return None
            sender = str(payload.get("from", {}).get("id", "")).strip()
            sender_name = str(payload.get("from", {}).get("name", "")).strip()
            text = payload.get("text", "")
            activity_id = str(payload.get("id", "")).strip()
            conversation_id = str(payload.get("conversation", {}).get("id", "")).strip()
            if not sender or not text or not activity_id:
                return None
            if len(text) > self.MAX_MESSAGE_SIZE:
                text = text[: self.MAX_MESSAGE_SIZE]
            return GatewayMessage(
                message_id=f"teams-{activity_id}",
                channel="teams",
                sender_id=sender,
                body=text,
                conversation_id=conversation_id,
                metadata={
                    "from_name": sender_name,
                    "channel_data": payload.get("channelData", {}),
                    "activity_id": activity_id,
                },
            )
        except (KeyError, TypeError, ValueError):
            return None

    def send(self, recipient_id: str, body: str, **kwargs: Any) -> bool:
        """Record a Microsoft Graph send intention."""
        self._sent_count += 1
        return True

    def build_send_payload(self, recipient_id: str, body: str) -> dict[str, Any]:
        """Build the Graph chat.send body for a chat message."""
        return {
            "body": {
                "contentType": "text",
                "content": body,
            },
        }

    @property
    def sent_count(self) -> int:
        return self._sent_count
