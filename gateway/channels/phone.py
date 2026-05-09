"""Twilio Voice Channel Adapter.

Handles inbound voice webhook events (status callbacks and IVR-style entry
points) plus outbound TwiML response payloads. Receives form-encoded payloads
from Twilio's Voice API.

Requires: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_VOICE_CALLER_ID,
TWILIO_VOICE_WEBHOOK_URL.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any

from gateway.router import GatewayMessage


class PhoneAdapter:
    """Twilio Voice webhook adapter.

    Webhook receive: parses application/x-www-form-urlencoded voice events
        (CallStatus, RecordingStatus, Gather/Speech results) into a single
        canonical GatewayMessage describing the call event.
    Webhook verification: validates X-Twilio-Signature using the auth token
        and the canonical request URL plus sorted form parameters (same scheme
        as the Twilio SMS adapter).
    Send: Twilio Voice operations (place/transfer/terminate) flow through the
        signed phone worker; this adapter records inbound intentions only.
    """

    channel_name = "phone"
    MAX_BODY_SIZE = 4096

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        caller_id: str = "",
        webhook_url: str = "",
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._caller_id = caller_id
        self._webhook_url = webhook_url
        self._sent_count = 0

    def verify_signature(
        self,
        url: str,
        params: dict[str, str],
        signature: str,
    ) -> bool:
        """Verify Twilio voice webhook signature (HMAC-SHA1 of url + sorted params)."""
        if not self._auth_token:
            return False
        canonical_url = url or self._webhook_url
        if not canonical_url:
            return False
        signed = canonical_url
        for key in sorted(params):
            signed += key + str(params[key])
        digest = hmac.new(
            self._auth_token.encode("utf-8"),
            signed.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        expected = base64.b64encode(digest).decode("ascii")
        return hmac.compare_digest(expected, signature)

    def parse_message(self, params: dict[str, str]) -> GatewayMessage | None:
        """Parse a Twilio voice webhook event into a GatewayMessage."""
        try:
            call_sid = str(params.get("CallSid", "")).strip()
            caller = str(params.get("From", "")).strip()
            callee = str(params.get("To", "")).strip()
            call_status = str(params.get("CallStatus", "")).strip()
            speech = str(params.get("SpeechResult", "")).strip()
            digits = str(params.get("Digits", "")).strip()
            if not call_sid or not caller:
                return None
            body = speech or digits or call_status or "voice_event"
            if len(body) > self.MAX_BODY_SIZE:
                body = body[: self.MAX_BODY_SIZE]
            return GatewayMessage(
                message_id=f"phone-{call_sid}",
                channel="phone",
                sender_id=caller,
                body=body,
                conversation_id=call_sid,
                metadata={
                    "to": callee,
                    "call_sid": call_sid,
                    "call_status": call_status,
                    "speech_result": speech,
                    "digits": digits,
                },
            )
        except (KeyError, TypeError, ValueError):
            return None

    def send(self, recipient_id: str, body: str, **kwargs: Any) -> bool:
        """Record a Twilio Voice send intention.

        Production HTTP execution (place/transfer/terminate) happens through
        the signed phone worker — this adapter only counts intentions.
        """
        self._sent_count += 1
        return True

    def build_say_twiml(self, body: str) -> str:
        """Build a minimal TwiML <Response><Say>…</Say></Response> document."""
        escaped = (
            body.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        return f"<Response><Say>{escaped}</Say></Response>"

    @property
    def sent_count(self) -> int:
        return self._sent_count
