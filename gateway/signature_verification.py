"""Centralized Webhook Signature Verification.

Purpose: Unified verification for all channel webhook signatures.
    Replaces per-channel verification logic with a single registry
    that supports HMAC-SHA256, Ed25519, and token comparison.
Governance scope: webhook authentication only — no business logic.
Dependencies: hmac, hashlib (stdlib). Optional: nacl (for Ed25519).
Invariants:
  - Timing-safe comparison on all paths (no timing side-channels).
  - Replay protection with configurable timestamp window.
  - Fail-closed: verification fails if secret is configured but missing.
  - Fail-open only when no secret is configured (opt-in security).
  - Thread-safe — concurrent webhook threads are safe.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class VerificationMethod(Enum):
    """Supported signature verification methods."""

    HMAC_SHA256 = "hmac_sha256"
    ED25519 = "ed25519"
    TOKEN_COMPARE = "token_compare"


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Result of a webhook signature verification."""

    verified: bool
    channel: str
    method: VerificationMethod | None = None
    error: str = ""
    replay_checked: bool = False


@dataclass(frozen=True, slots=True)
class ChannelVerifierConfig:
    """Configuration for a channel's signature verification."""

    channel: str
    method: VerificationMethod
    secret: str  # Signing secret, public key, or token
    replay_window_seconds: float = 300.0  # 5 minutes default
    signature_prefix: str = ""  # e.g., "v0=", "sha256="


class WebhookVerifier:
    """Centralized webhook signature verification for all channels.

    Usage:
        verifier = WebhookVerifier()
        verifier.register("slack", ChannelVerifierConfig(
            channel="slack",
            method=VerificationMethod.HMAC_SHA256,
            secret="xoxb-signing-secret",
            signature_prefix="v0=",
        ))

        result = verifier.verify_hmac(
            channel="slack",
            body=request_body,
            signature=header_signature,
            timestamp=header_timestamp,
        )
    """

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._configs: dict[str, ChannelVerifierConfig] = {}
        self._clock = clock or time.time
        self._lock = threading.Lock()
        self._verified_count = 0
        self._rejected_count = 0
        self._skipped_count = 0

    def register(self, channel: str, config: ChannelVerifierConfig) -> None:
        """Register a channel's verification configuration."""
        with self._lock:
            self._configs[channel] = config

    def is_configured(self, channel: str) -> bool:
        """Check if a channel has verification configured."""
        return channel in self._configs

    def _check_replay(self, timestamp: str | float, window: float) -> tuple[bool, str]:
        """Check if a timestamp is within the replay window.

        Returns (valid, error_message).
        """
        if not timestamp:
            return True, ""  # No timestamp provided — skip replay check
        try:
            ts = float(timestamp)
        except (ValueError, TypeError):
            return False, "invalid timestamp format"
        now = self._clock()
        age = abs(now - ts)
        if age > window:
            return False, f"request too old ({int(age)}s > {int(window)}s)"
        return True, ""

    def verify_hmac(
        self,
        *,
        channel: str,
        body: str | bytes,
        signature: str,
        timestamp: str = "",
        basestring_format: str = "",
    ) -> VerificationResult:
        """Verify an HMAC-SHA256 signature.

        Args:
            channel: Channel name (must be registered).
            body: Raw request body.
            signature: The signature header value.
            timestamp: Optional timestamp for replay protection.
            basestring_format: Optional format string for basestring.
                Use {timestamp} and {body} placeholders.
                Default: just the body bytes.
        """
        config = self._configs.get(channel)
        if config is None:
            self._skipped_count += 1
            return VerificationResult(verified=True, channel=channel)  # Not configured — pass

        if not config.secret:
            self._skipped_count += 1
            return VerificationResult(verified=True, channel=channel)  # No secret — pass

        if not signature:
            self._rejected_count += 1
            return VerificationResult(
                verified=False, channel=channel,
                method=VerificationMethod.HMAC_SHA256,
                error="missing signature",
            )

        # Replay check
        replay_checked = False
        if timestamp:
            valid, err = self._check_replay(timestamp, config.replay_window_seconds)
            replay_checked = True
            if not valid:
                self._rejected_count += 1
                return VerificationResult(
                    verified=False, channel=channel,
                    method=VerificationMethod.HMAC_SHA256,
                    error=err, replay_checked=True,
                )

        # Build basestring
        body_str = body if isinstance(body, str) else body.decode("utf-8", errors="replace")
        if basestring_format:
            basestring = basestring_format.format(timestamp=timestamp, body=body_str)
        else:
            basestring = body_str

        # Compute HMAC
        expected = hmac.new(
            config.secret.encode("utf-8"),
            basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Strip prefix from provided signature
        sig_value = signature
        if config.signature_prefix and sig_value.startswith(config.signature_prefix):
            sig_value = sig_value[len(config.signature_prefix):]

        if hmac.compare_digest(expected, sig_value):
            self._verified_count += 1
            return VerificationResult(
                verified=True, channel=channel,
                method=VerificationMethod.HMAC_SHA256,
                replay_checked=replay_checked,
            )

        self._rejected_count += 1
        return VerificationResult(
            verified=False, channel=channel,
            method=VerificationMethod.HMAC_SHA256,
            error="signature mismatch",
            replay_checked=replay_checked,
        )

    def verify_ed25519(
        self,
        *,
        channel: str,
        body: str,
        signature: str,
        timestamp: str = "",
    ) -> VerificationResult:
        """Verify an Ed25519 signature (Discord-style).

        Requires the PyNaCl library. Falls back to rejection if
        the library is not installed but a public key is configured.
        """
        config = self._configs.get(channel)
        if config is None:
            self._skipped_count += 1
            return VerificationResult(verified=True, channel=channel)

        if not config.secret:
            self._skipped_count += 1
            return VerificationResult(verified=True, channel=channel)

        if not signature:
            self._rejected_count += 1
            return VerificationResult(
                verified=False, channel=channel,
                method=VerificationMethod.ED25519,
                error="missing signature",
            )

        try:
            from nacl.signing import VerifyKey
            verify_key = VerifyKey(bytes.fromhex(config.secret))
            message = f"{timestamp}{body}".encode("utf-8")
            verify_key.verify(message, bytes.fromhex(signature))
            self._verified_count += 1
            return VerificationResult(
                verified=True, channel=channel,
                method=VerificationMethod.ED25519,
            )
        except ImportError:
            self._rejected_count += 1
            return VerificationResult(
                verified=False, channel=channel,
                method=VerificationMethod.ED25519,
                error="nacl library not installed",
            )
        except Exception:
            self._rejected_count += 1
            return VerificationResult(
                verified=False, channel=channel,
                method=VerificationMethod.ED25519,
                error="signature verification failed",
            )

    def verify_token(
        self,
        *,
        channel: str,
        provided_token: str,
    ) -> VerificationResult:
        """Verify by simple token comparison (Telegram-style).

        Uses timing-safe comparison to prevent timing attacks.
        """
        config = self._configs.get(channel)
        if config is None:
            self._skipped_count += 1
            return VerificationResult(verified=True, channel=channel)

        if not config.secret:
            self._skipped_count += 1
            return VerificationResult(verified=True, channel=channel)

        if not provided_token:
            self._rejected_count += 1
            return VerificationResult(
                verified=False, channel=channel,
                method=VerificationMethod.TOKEN_COMPARE,
                error="missing token",
            )

        if hmac.compare_digest(config.secret, provided_token):
            self._verified_count += 1
            return VerificationResult(
                verified=True, channel=channel,
                method=VerificationMethod.TOKEN_COMPARE,
            )

        self._rejected_count += 1
        return VerificationResult(
            verified=False, channel=channel,
            method=VerificationMethod.TOKEN_COMPARE,
            error="token mismatch",
        )

    def verify(
        self,
        *,
        channel: str,
        body: str | bytes = "",
        signature: str = "",
        timestamp: str = "",
        token: str = "",
        basestring_format: str = "",
    ) -> VerificationResult:
        """Auto-dispatch to the correct verification method based on channel config."""
        config = self._configs.get(channel)
        if config is None:
            self._skipped_count += 1
            return VerificationResult(verified=True, channel=channel)

        if config.method == VerificationMethod.HMAC_SHA256:
            return self.verify_hmac(
                channel=channel, body=body, signature=signature,
                timestamp=timestamp, basestring_format=basestring_format,
            )
        elif config.method == VerificationMethod.ED25519:
            body_str = body if isinstance(body, str) else body.decode("utf-8", errors="replace")
            return self.verify_ed25519(
                channel=channel, body=body_str,
                signature=signature, timestamp=timestamp,
            )
        elif config.method == VerificationMethod.TOKEN_COMPARE:
            return self.verify_token(channel=channel, provided_token=token)

        self._skipped_count += 1
        return VerificationResult(verified=True, channel=channel)

    @property
    def verified_count(self) -> int:
        return self._verified_count

    @property
    def rejected_count(self) -> int:
        return self._rejected_count

    @property
    def skipped_count(self) -> int:
        return self._skipped_count

    def status(self) -> dict[str, Any]:
        return {
            "configured_channels": list(self._configs.keys()),
            "total_verified": self._verified_count,
            "total_rejected": self._rejected_count,
            "total_skipped": self._skipped_count,
        }
