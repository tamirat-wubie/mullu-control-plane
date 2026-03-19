"""Purpose: SMTP email communication provider — governed outbound email for approvals/escalations.
Governance scope: communication adapter only.
Dependencies: communication contracts, Python smtplib.
Invariants:
  - Only structured channel messages (approval/escalation/notification/explanation).
  - No free-form email composition.
  - Delivery result is always produced.
  - SMTP credentials are never stored in contracts or traces.
"""

from __future__ import annotations

from typing import Callable

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from mcoi_runtime.contracts.communication import (
    CommunicationChannel,
    CommunicationMessage,
    DeliveryResult,
    DeliveryStatus,
)
from mcoi_runtime.core.invariants import ensure_non_empty_text, stable_identifier


@dataclass(frozen=True, slots=True)
class SmtpConfig:
    """SMTP connection configuration. Credential values are runtime-only, never persisted."""

    host: str
    port: int
    sender_email: str
    use_tls: bool = True
    username: str | None = None
    password: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "host", ensure_non_empty_text("host", self.host))
        object.__setattr__(self, "sender_email", ensure_non_empty_text("sender_email", self.sender_email))
        if not isinstance(self.port, int) or self.port <= 0:
            raise ValueError("port must be a positive integer")


# Channel -> email subject prefix mapping
_CHANNEL_SUBJECTS = {
    CommunicationChannel.APPROVAL: "[APPROVAL REQUIRED]",
    CommunicationChannel.ESCALATION: "[ESCALATION]",
    CommunicationChannel.NOTIFICATION: "[NOTIFICATION]",
    CommunicationChannel.EXPLANATION: "[EXPLANATION]",
}


def _build_email_body(message: CommunicationMessage) -> str:
    """Build a structured email body from a communication message."""
    lines = [
        f"Channel: {message.channel.value}",
        f"Type: {message.message_type}",
        f"From: {message.sender_id}",
        f"Correlation: {message.correlation_id}",
        f"Created: {message.created_at}",
        "",
    ]
    for key, value in message.payload.items():
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


class SmtpCommunicationAdapter:
    """SMTP email adapter for governed communication messages.

    Sends structured emails for approval, escalation, notification, and explanation channels.
    Does NOT support free-form email composition.
    """

    def __init__(self, *, config: SmtpConfig, clock: Callable[[], str]) -> None:
        self._config = config
        self._clock = clock

    def deliver(self, message: CommunicationMessage) -> DeliveryResult:
        delivery_id = stable_identifier("smtp-delivery", {
            "message_id": message.message_id,
        })

        subject_prefix = _CHANNEL_SUBJECTS.get(message.channel, "[MULLU]")
        subject = f"{subject_prefix} {message.message_type} — {message.correlation_id}"
        body = _build_email_body(message)

        email = EmailMessage()
        email["From"] = self._config.sender_email
        email["To"] = message.recipient_id  # recipient_id is the email address
        email["Subject"] = subject
        email.set_content(body)

        try:
            if self._config.use_tls:
                with smtplib.SMTP(self._config.host, self._config.port, timeout=30) as server:
                    server.starttls()
                    if self._config.username and self._config.password:
                        server.login(self._config.username, self._config.password)
                    server.send_message(email)
            else:
                with smtplib.SMTP(self._config.host, self._config.port, timeout=30) as server:
                    if self._config.username and self._config.password:
                        server.login(self._config.username, self._config.password)
                    server.send_message(email)

            return DeliveryResult(
                delivery_id=delivery_id,
                message_id=message.message_id,
                status=DeliveryStatus.DELIVERED,
                channel=message.channel,
                delivered_at=self._clock(),
                metadata={"smtp_host": self._config.host, "recipient": message.recipient_id},
            )
        except smtplib.SMTPException as exc:
            return DeliveryResult(
                delivery_id=delivery_id,
                message_id=message.message_id,
                status=DeliveryStatus.FAILED,
                channel=message.channel,
                error_code=f"smtp_error:{type(exc).__name__}",
            )
        except (OSError, TimeoutError) as exc:
            return DeliveryResult(
                delivery_id=delivery_id,
                message_id=message.message_id,
                status=DeliveryStatus.FAILED,
                channel=message.channel,
                error_code=f"connection_error:{type(exc).__name__}",
            )
