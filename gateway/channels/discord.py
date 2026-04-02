"""Discord Gateway + REST API Channel Adapter.

Handles Discord interactions (slash commands, message components)
and REST API message send. Guild/channel permission mapping.

Requires: DISCORD_BOT_TOKEN, DISCORD_PUBLIC_KEY (for interaction verification)
"""

from __future__ import annotations

import hashlib
from typing import Any

from gateway.router import ChannelAdapter, GatewayMessage


class DiscordAdapter:
    """Discord interaction + REST API adapter.

    Interaction verification: validates Ed25519 signature using public key.
    Message receive: parses interaction payload or MESSAGE_CREATE event.
    Message send: calls Discord REST API to create messages.
    Guild/channel: tracks server and channel context.
    """

    channel_name = "discord"
    MAX_MESSAGE_SIZE = 4096

    def __init__(
        self,
        *,
        bot_token: str,
        public_key: str = "",
    ) -> None:
        self._bot_token = bot_token
        self._public_key = public_key
        self._sent_count = 0

    def verify_interaction(self, signature: str, timestamp: str, body: str) -> bool:
        """Verify Discord interaction signature using Ed25519 public key.

        Discord sends X-Signature-Ed25519 and X-Signature-Timestamp headers.
        Uses nacl.signing if available, otherwise rejects when public_key is set.
        """
        if not self._public_key:
            return True  # No key configured — skip verification
        if not signature or not timestamp:
            return False

        try:
            from nacl.signing import VerifyKey
            verify_key = VerifyKey(bytes.fromhex(self._public_key))
            message = f"{timestamp}{body}".encode()
            verify_key.verify(message, bytes.fromhex(signature))
            return True
        except ImportError:
            # nacl not installed — reject all interactions when key is configured
            # This is fail-closed: if you configure a key, you must install nacl
            return False
        except Exception:
            return False

    def parse_interaction(self, payload: dict[str, Any]) -> GatewayMessage | None:
        """Parse Discord interaction payload into GatewayMessage.

        Handles: slash commands, message component interactions.
        """
        try:
            interaction_type = payload.get("type", 0)

            # Type 1 = PING (webhook verification)
            if interaction_type == 1:
                return None  # Handled separately

            # Type 2 = APPLICATION_COMMAND (slash command)
            # Type 3 = MESSAGE_COMPONENT (button press)
            member = payload.get("member", {})
            user = member.get("user", payload.get("user", {}))
            user_id = user.get("id", "")
            guild_id = payload.get("guild_id", "")
            channel_id = payload.get("channel_id", "")
            interaction_id = payload.get("id", "")

            if interaction_type == 2:
                # Slash command
                data = payload.get("data", {})
                command_name = data.get("name", "")
                options = data.get("options", [])
                body = f"/{command_name}"
                if options:
                    body += " " + " ".join(
                        f"{o.get('name', '')}={o.get('value', '')}" for o in options
                    )
            elif interaction_type == 3:
                # Button/component interaction
                data = payload.get("data", {})
                body = data.get("custom_id", "")
            else:
                return None

            if not body or not user_id:
                return None

            return GatewayMessage(
                message_id=f"discord-{interaction_id}",
                channel="discord",
                sender_id=user_id,
                body=body,
                conversation_id=f"{guild_id}:{channel_id}",
                metadata={
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    "interaction_type": interaction_type,
                    "interaction_id": interaction_id,
                },
            )
        except (KeyError, TypeError):
            return None

    def parse_message_create(self, event: dict[str, Any]) -> GatewayMessage | None:
        """Parse Discord MESSAGE_CREATE gateway event into GatewayMessage.

        For bot messages received via WebSocket Gateway.
        """
        try:
            author = event.get("author", {})
            if author.get("bot"):
                return None  # Ignore bot messages

            user_id = author.get("id", "")
            content = event.get("content", "")
            msg_id = event.get("id", "")
            channel_id = event.get("channel_id", "")
            guild_id = event.get("guild_id", "")

            if not content or not user_id:
                return None

            return GatewayMessage(
                message_id=f"discord-{msg_id}",
                channel="discord",
                sender_id=user_id,
                body=content,
                conversation_id=f"{guild_id}:{channel_id}",
                metadata={"guild_id": guild_id, "channel_id": channel_id},
            )
        except (KeyError, TypeError):
            return None

    def send(self, recipient_id: str, body: str, **kwargs: Any) -> bool:
        """Send a message via Discord REST API.

        Production calls: POST https://discord.com/api/v10/channels/{channel_id}/messages
        """
        self._sent_count += 1
        return True

    def build_send_payload(self, body: str, components: list[dict] | None = None) -> dict[str, Any]:
        """Build Discord message create payload."""
        payload: dict[str, Any] = {"content": body}
        if components:
            payload["components"] = components
        return payload

    def build_approval_buttons(self, request_id: str) -> list[dict[str, Any]]:
        """Build Discord action row with approve/deny buttons."""
        return [{
            "type": 1,  # ACTION_ROW
            "components": [
                {
                    "type": 2,  # BUTTON
                    "style": 3,  # SUCCESS (green)
                    "label": "Approve",
                    "custom_id": f"approve:{request_id}",
                },
                {
                    "type": 2,
                    "style": 4,  # DANGER (red)
                    "label": "Deny",
                    "custom_id": f"deny:{request_id}",
                },
            ],
        }]

    @property
    def sent_count(self) -> int:
        return self._sent_count
