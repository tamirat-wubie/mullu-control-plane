"""Retry Policy — Per-channel configurable retry behavior.

Purpose: Different channels have different reliability characteristics.
    WhatsApp may need 5 retries with long backoff; Slack may need 2 with
    short backoff.  This module defines per-channel retry configurations.
Governance scope: retry configuration only.
Dependencies: none (pure configuration).
Invariants:
  - Each channel has an independent retry policy.
  - Default policy applies when no channel-specific policy exists.
  - Policies are immutable after creation.
  - Backoff is always bounded (max_delay cap).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry configuration for a delivery channel."""

    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    backoff_factor: float = 2.0  # Exponential multiplier
    jitter: bool = True  # Add randomness to prevent thundering herd
    retry_on_status: frozenset[int] = frozenset({429, 500, 502, 503, 504})

    def delay_for_attempt(self, attempt: int) -> float:
        """Calculate delay for a given retry attempt (0-indexed)."""
        delay = min(
            self.base_delay_seconds * (self.backoff_factor ** attempt),
            self.max_delay_seconds,
        )
        if self.jitter:
            delay *= (0.5 + 0.5 * random.random())
        return delay

    def should_retry(self, attempt: int, status_code: int = 0) -> bool:
        """Check if a retry should be attempted."""
        if attempt >= self.max_retries:
            return False
        if status_code and status_code not in self.retry_on_status:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_retries": self.max_retries,
            "base_delay_seconds": self.base_delay_seconds,
            "max_delay_seconds": self.max_delay_seconds,
            "backoff_factor": self.backoff_factor,
            "jitter": self.jitter,
        }


# ── Predefined channel policies ───────────────────────────────

WHATSAPP_POLICY = RetryPolicy(
    max_retries=5,
    base_delay_seconds=2.0,
    max_delay_seconds=120.0,
    backoff_factor=2.0,
)

TELEGRAM_POLICY = RetryPolicy(
    max_retries=3,
    base_delay_seconds=1.0,
    max_delay_seconds=30.0,
    backoff_factor=2.0,
)

SLACK_POLICY = RetryPolicy(
    max_retries=3,
    base_delay_seconds=0.5,
    max_delay_seconds=15.0,
    backoff_factor=2.0,
)

DISCORD_POLICY = RetryPolicy(
    max_retries=3,
    base_delay_seconds=1.0,
    max_delay_seconds=30.0,
    backoff_factor=2.0,
    retry_on_status=frozenset({429, 500, 502, 503, 504}),
)

WEB_POLICY = RetryPolicy(
    max_retries=1,
    base_delay_seconds=0.5,
    max_delay_seconds=5.0,
)

DEFAULT_POLICY = RetryPolicy()

CHANNEL_POLICIES: dict[str, RetryPolicy] = {
    "whatsapp": WHATSAPP_POLICY,
    "telegram": TELEGRAM_POLICY,
    "slack": SLACK_POLICY,
    "discord": DISCORD_POLICY,
    "web": WEB_POLICY,
}


class RetryPolicyRegistry:
    """Registry of per-channel retry policies.

    Usage:
        registry = RetryPolicyRegistry()
        policy = registry.get("whatsapp")
        delay = policy.delay_for_attempt(2)
    """

    def __init__(self) -> None:
        self._policies: dict[str, RetryPolicy] = dict(CHANNEL_POLICIES)
        self._default = DEFAULT_POLICY

    def get(self, channel: str) -> RetryPolicy:
        return self._policies.get(channel, self._default)

    def set(self, channel: str, policy: RetryPolicy) -> None:
        self._policies[channel] = policy

    def list_channels(self) -> list[str]:
        return sorted(self._policies.keys())

    def summary(self) -> dict[str, Any]:
        return {
            "channels": {ch: p.to_dict() for ch, p in sorted(self._policies.items())},
            "default": self._default.to_dict(),
        }
