"""Twilio SMS Channel Adapter.

Handles inbound SMS webhooks (form-encoded) and outbound SMS sends via the
Twilio Programmable Messaging API.

Requires: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_SMS_SENDER, TWILIO_WEBHOOK_URL.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import urllib.parse
from typing import Any

from gateway.router import GatewayMessage


class SmsAdapter:
    """Twilio Programmable Messaging adapter.

    Webhook receive: parses application/x-www-form-urlencoded payload into a
    GatewayMessage.
    Webhook verification: validates X-Twilio-Signature using auth token.
    Message send: build_send_payload returns the form body for the Messages.json
    REST API. Production HTTP is performed by the messaging worker; this
    adapter only counts intentions on the inbound path.
    """

    channel_name = "sms"
    MAX_MESSAGE_SIZE = 1600  # Twilio SMS hard limit across concatenated segments

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        sender: str = "",
        webhook_url: str = "",
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._sender = sender
        self._webhook_url = webhook_url
        self._sent_count = 0

    def verify_signature(
        self,
        url: str,
        params: dict[str, str],
        signature: str,
    ) -> bool:
        """Verify Twilio webhook signature.

        Twilio computes HMAC-SHA1 over the full request URL plus the sorted
        form parameters concatenated as key+value, then base64-encodes the
        digest. See https://www.twilio.com/docs/usage/webhooks/webhooks-security.
        """
        if not self._auth_token:
            return False
        canonical_url = url or self._webhook_url
        if not canonical_url:
            return False
        sorted_keys = sorted(params)
        signed = canonical_url
        for key in sorted_keys:
            signed += key + str(params[key])
        digest = hmac.new(
            self._auth_token.encode("utf-8"),
            signed.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        expected = base64.b64encode(digest).decode("ascii")
        return hmac.compare_digest(expected, signature)

    def parse_message(self, params: dict[str, str]) -> GatewayMessage | None:
        """Parse a Twilio inbound-SMS form payload into a GatewayMessage."""
        try:
            sender = str(params.get("From", "")).strip()
            recipient = str(params.get("To", "")).strip()
            body = str(params.get("Body", ""))
            message_sid = str(params.get("MessageSid", "")).strip()
            if not sender or not body or not message_sid:
                return None
            if len(body) > self.MAX_MESSAGE_SIZE:
                body = body[: self.MAX_MESSAGE_SIZE]
            return GatewayMessage(
                message_id=f"sms-{message_sid}",
                channel="sms",
                sender_id=sender,
                body=body,
                conversation_id=sender,
                metadata={
                    "to": recipient,
                    "message_sid": message_sid,
                    "num_media": str(params.get("NumMedia", "0")),
                },
            )
        except (KeyError, TypeError, ValueError):
            return None

    def send(self, recipient_id: str, body: str, **kwargs: Any) -> bool:
        """Record a Twilio Messages.json send intention.

        Production HTTP execution happens through the signed messaging worker.
        """
        self._sent_count += 1
        return True

    def build_send_payload(self, recipient_id: str, body: str) -> str:
        """Build the form body for Twilio Programmable Messaging."""
        return urllib.parse.urlencode({
            "From": self._sender,
            "To": recipient_id,
            "Body": body,
        })

    @property
    def sent_count(self) -> int:
        return self._sent_count
