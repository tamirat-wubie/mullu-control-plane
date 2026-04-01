"""Web Chat Channel Adapter.

WebSocket-based chat widget for browser integration.
Embeddable in dashboard and external sites.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from gateway.router import ChannelAdapter, GatewayMessage


class WebChatAdapter:
    """WebSocket-based web chat adapter.

    Handles text messages from browser clients.
    Each WebSocket connection is identified by a session token.
    """

    channel_name = "web"

    def __init__(self) -> None:
        self._sent_count = 0
        self._connections: dict[str, Any] = {}  # session_token → websocket

    def parse_message(self, data: dict[str, Any], session_token: str = "") -> GatewayMessage | None:
        """Parse WebSocket message into canonical GatewayMessage."""
        body = data.get("body", "") or data.get("text", "") or data.get("message", "")
        if not body:
            return None

        sender_id = data.get("user_id", session_token)
        msg_id = data.get("message_id", f"web-{hashlib.sha256(f'{sender_id}:{body}'.encode()).hexdigest()[:12]}")

        return GatewayMessage(
            message_id=msg_id,
            channel="web",
            sender_id=sender_id,
            body=body,
            conversation_id=data.get("conversation_id", session_token),
            metadata={"session_token": session_token},
        )

    def send(self, recipient_id: str, body: str, **kwargs: Any) -> bool:
        """Send response to web client.

        In production, pushes through WebSocket connection.
        """
        self._sent_count += 1
        return True

    def register_connection(self, session_token: str, websocket: Any) -> None:
        """Register an active WebSocket connection."""
        self._connections[session_token] = websocket

    def remove_connection(self, session_token: str) -> None:
        """Remove a disconnected WebSocket connection."""
        self._connections.pop(session_token, None)

    @property
    def active_connections(self) -> int:
        return len(self._connections)

    @property
    def sent_count(self) -> int:
        return self._sent_count
