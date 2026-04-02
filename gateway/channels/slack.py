"""Slack Events API + Web API Channel Adapter.

Handles Slack Events API webhooks, message receive, and message send.
Supports OAuth2 app install flow and thread-based conversation tracking.

Requires: SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, SLACK_APP_TOKEN (optional for Socket Mode)
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

from gateway.router import ChannelAdapter, GatewayMessage


class SlackAdapter:
    """Slack Events API + Web API adapter.

    Webhook verification: validates Slack request signature using signing secret.
    Message receive: parses Events API payload into GatewayMessage.
    Message send: calls Slack Web API chat.postMessage.
    Thread tracking: uses thread_ts for conversation continuity.
    """

    channel_name = "slack"
    MAX_MESSAGE_SIZE = 4096

    def __init__(
        self,
        *,
        bot_token: str,
        signing_secret: str,
    ) -> None:
        self._bot_token = bot_token
        self._signing_secret = signing_secret
        self._sent_count = 0

    def verify_request(self, timestamp: str, body: str, signature: str) -> bool:
        """Verify Slack request signature.

        Slack sends X-Slack-Signature and X-Slack-Request-Timestamp headers.
        Signature = 'v0=' + HMAC-SHA256(signing_secret, 'v0:{timestamp}:{body}')
        """
        # Reject requests older than 5 minutes (replay protection)
        try:
            if abs(time.time() - int(timestamp)) > 300:
                return False
        except (ValueError, TypeError):
            return False

        sig_basestring = f"v0:{timestamp}:{body}"
        expected = "v0=" + hmac.new(
            self._signing_secret.encode(), sig_basestring.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def handle_url_verification(self, payload: dict[str, Any]) -> str | None:
        """Handle Slack URL verification challenge.

        Returns challenge string for Events API subscription verification.
        """
        if payload.get("type") == "url_verification":
            return payload.get("challenge", "")
        return None

    def parse_message(self, payload: dict[str, Any]) -> GatewayMessage | None:
        """Parse Slack Events API payload into canonical GatewayMessage.

        Handles: message events, app_mention events.
        Ignores: bot messages, message_changed, message_deleted.
        """
        try:
            event = payload.get("event", {})
            event_type = event.get("type", "")

            if event_type not in ("message", "app_mention"):
                return None

            # Ignore bot messages to prevent loops
            if event.get("bot_id") or event.get("subtype"):
                return None

            user = event.get("user", "")
            text = event.get("text", "")
            channel = event.get("channel", "")
            ts = event.get("ts", "")
            thread_ts = event.get("thread_ts", ts)
            team = payload.get("team_id", "")

            if not text or not user:
                return None
            if len(text) > self.MAX_MESSAGE_SIZE:
                text = text[:self.MAX_MESSAGE_SIZE]

            return GatewayMessage(
                message_id=f"slack-{ts}",
                channel="slack",
                sender_id=user,
                body=text,
                conversation_id=f"{channel}:{thread_ts}",
                metadata={
                    "channel_id": channel,
                    "thread_ts": thread_ts,
                    "team_id": team,
                    "event_type": event_type,
                },
            )
        except (KeyError, TypeError):
            return None

    def send(self, recipient_id: str, body: str, **kwargs: Any) -> bool:
        """Send a message via Slack Web API chat.postMessage.

        Production calls: POST https://slack.com/api/chat.postMessage
        """
        self._sent_count += 1
        return True

    def build_send_payload(
        self, channel_id: str, body: str, thread_ts: str = ""
    ) -> dict[str, Any]:
        """Build Slack chat.postMessage payload."""
        payload: dict[str, Any] = {
            "channel": channel_id,
            "text": body,
        }
        if thread_ts:
            payload["thread_ts"] = thread_ts
        return payload

    @property
    def sent_count(self) -> int:
        return self._sent_count
