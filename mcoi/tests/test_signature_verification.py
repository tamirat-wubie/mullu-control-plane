"""Webhook Signature Verification Tests — Centralized verification for all channels."""

import hashlib
import hmac as hmac_mod
import time

import pytest
from gateway.signature_verification import (
    ChannelVerifierConfig,
    VerificationMethod,
    VerificationResult,
    WebhookVerifier,
)


# ── HMAC-SHA256 verification ──────────────────────────────────

class TestHMACSHA256:
    def _sign(self, secret: str, body: str, prefix: str = "", basestring_fmt: str = "", timestamp: str = "") -> str:
        if basestring_fmt:
            basestring = basestring_fmt.format(timestamp=timestamp, body=body)
        else:
            basestring = body
        sig = hmac_mod.new(secret.encode(), basestring.encode(), hashlib.sha256).hexdigest()
        return f"{prefix}{sig}"

    def test_valid_signature(self):
        v = WebhookVerifier()
        v.register("whatsapp", ChannelVerifierConfig(
            channel="whatsapp",
            method=VerificationMethod.HMAC_SHA256,
            secret="app-secret",
            signature_prefix="sha256=",
        ))
        body = '{"message": "hello"}'
        sig = self._sign("app-secret", body, prefix="sha256=")
        result = v.verify_hmac(channel="whatsapp", body=body, signature=sig)
        assert result.verified is True
        assert result.method == VerificationMethod.HMAC_SHA256

    def test_invalid_signature(self):
        v = WebhookVerifier()
        v.register("whatsapp", ChannelVerifierConfig(
            channel="whatsapp",
            method=VerificationMethod.HMAC_SHA256,
            secret="app-secret",
            signature_prefix="sha256=",
        ))
        result = v.verify_hmac(channel="whatsapp", body="payload", signature="sha256=badbadbad")
        assert result.verified is False
        assert "mismatch" in result.error

    def test_missing_signature_rejected(self):
        v = WebhookVerifier()
        v.register("whatsapp", ChannelVerifierConfig(
            channel="whatsapp",
            method=VerificationMethod.HMAC_SHA256,
            secret="secret",
        ))
        result = v.verify_hmac(channel="whatsapp", body="payload", signature="")
        assert result.verified is False
        assert "missing" in result.error

    def test_slack_style_basestring(self):
        v = WebhookVerifier(clock=lambda: 1234567890.0)  # Match timestamp
        v.register("slack", ChannelVerifierConfig(
            channel="slack",
            method=VerificationMethod.HMAC_SHA256,
            secret="slack-signing-secret",
            signature_prefix="v0=",
            replay_window_seconds=300.0,
        ))
        body = "request body"
        timestamp = "1234567890"
        sig = self._sign(
            "slack-signing-secret", body,
            prefix="v0=",
            basestring_fmt="v0:{timestamp}:{body}",
            timestamp=timestamp,
        )
        result = v.verify_hmac(
            channel="slack", body=body, signature=sig,
            timestamp=timestamp,
            basestring_format="v0:{timestamp}:{body}",
        )
        assert result.verified is True
        assert result.replay_checked is True

    def test_bytes_body(self):
        v = WebhookVerifier()
        v.register("wh", ChannelVerifierConfig(
            channel="wh",
            method=VerificationMethod.HMAC_SHA256,
            secret="sec",
        ))
        body = b'{"key": "value"}'
        sig = self._sign("sec", body.decode())
        result = v.verify_hmac(channel="wh", body=body, signature=sig)
        assert result.verified is True


# ── Replay protection ──────────────────────────────────────────

class TestReplayProtection:
    def test_old_timestamp_rejected(self):
        v = WebhookVerifier(clock=lambda: 1000.0)
        v.register("slack", ChannelVerifierConfig(
            channel="slack",
            method=VerificationMethod.HMAC_SHA256,
            secret="secret",
            replay_window_seconds=60.0,
        ))
        result = v.verify_hmac(
            channel="slack", body="body",
            signature="v0=abc", timestamp="500",  # 500s old
        )
        assert result.verified is False
        assert "too old" in result.error
        assert result.replay_checked is True

    def test_fresh_timestamp_passes(self):
        v = WebhookVerifier(clock=lambda: 1000.0)
        v.register("slack", ChannelVerifierConfig(
            channel="slack",
            method=VerificationMethod.HMAC_SHA256,
            secret="secret",
            replay_window_seconds=60.0,
        ))
        body = "body"
        sig = hmac_mod.new(b"secret", body.encode(), hashlib.sha256).hexdigest()
        result = v.verify_hmac(
            channel="slack", body=body,
            signature=sig, timestamp="995",
        )
        assert result.verified is True
        assert result.replay_checked is True

    def test_invalid_timestamp_rejected(self):
        v = WebhookVerifier()
        v.register("ch", ChannelVerifierConfig(
            channel="ch",
            method=VerificationMethod.HMAC_SHA256,
            secret="secret",
        ))
        result = v.verify_hmac(
            channel="ch", body="body",
            signature="abc", timestamp="not-a-number",
        )
        assert result.verified is False
        assert "invalid timestamp" in result.error


# ── Token comparison (Telegram-style) ─────────────────────────

class TestTokenComparison:
    def test_valid_token(self):
        v = WebhookVerifier()
        v.register("telegram", ChannelVerifierConfig(
            channel="telegram",
            method=VerificationMethod.TOKEN_COMPARE,
            secret="bot-secret-token",
        ))
        result = v.verify_token(channel="telegram", provided_token="bot-secret-token")
        assert result.verified is True

    def test_invalid_token(self):
        v = WebhookVerifier()
        v.register("telegram", ChannelVerifierConfig(
            channel="telegram",
            method=VerificationMethod.TOKEN_COMPARE,
            secret="real-token",
        ))
        result = v.verify_token(channel="telegram", provided_token="fake-token")
        assert result.verified is False
        assert "mismatch" in result.error

    def test_missing_token(self):
        v = WebhookVerifier()
        v.register("telegram", ChannelVerifierConfig(
            channel="telegram",
            method=VerificationMethod.TOKEN_COMPARE,
            secret="real-token",
        ))
        result = v.verify_token(channel="telegram", provided_token="")
        assert result.verified is False
        assert "missing" in result.error


# ── Ed25519 verification (Discord-style) ──────────────────────

class TestEd25519:
    def test_nacl_not_installed_fails_closed(self):
        """If nacl is not installed but key is configured, fail closed."""
        v = WebhookVerifier()
        v.register("discord", ChannelVerifierConfig(
            channel="discord",
            method=VerificationMethod.ED25519,
            secret="aabbccdd" * 8,  # 64 hex chars
        ))
        # This will either work (if nacl installed) or fail closed
        result = v.verify_ed25519(
            channel="discord", body="test",
            signature="00" * 64, timestamp="12345",
        )
        # Either nacl is installed and signature is wrong, or nacl missing
        assert result.verified is False

    def test_missing_signature_rejected(self):
        v = WebhookVerifier()
        v.register("discord", ChannelVerifierConfig(
            channel="discord",
            method=VerificationMethod.ED25519,
            secret="aabb" * 16,
        ))
        result = v.verify_ed25519(channel="discord", body="test", signature="")
        assert result.verified is False
        assert "missing" in result.error


# ── Unconfigured channels ─────────────────────────────────────

class TestUnconfiguredChannels:
    def test_unconfigured_channel_passes(self):
        v = WebhookVerifier()
        result = v.verify_hmac(channel="unknown", body="body", signature="sig")
        assert result.verified is True  # Fail-open for unconfigured

    def test_empty_secret_passes(self):
        v = WebhookVerifier()
        v.register("web", ChannelVerifierConfig(
            channel="web",
            method=VerificationMethod.HMAC_SHA256,
            secret="",  # No secret configured
        ))
        result = v.verify_hmac(channel="web", body="body", signature="")
        assert result.verified is True

    def test_is_configured(self):
        v = WebhookVerifier()
        assert v.is_configured("slack") is False
        v.register("slack", ChannelVerifierConfig(
            channel="slack",
            method=VerificationMethod.HMAC_SHA256,
            secret="secret",
        ))
        assert v.is_configured("slack") is True


# ── Auto-dispatch verify() ────────────────────────────────────

class TestAutoDispatch:
    def test_dispatch_hmac(self):
        v = WebhookVerifier()
        v.register("whatsapp", ChannelVerifierConfig(
            channel="whatsapp",
            method=VerificationMethod.HMAC_SHA256,
            secret="secret",
            signature_prefix="sha256=",
        ))
        body = "payload"
        sig = "sha256=" + hmac_mod.new(b"secret", body.encode(), hashlib.sha256).hexdigest()
        result = v.verify(channel="whatsapp", body=body, signature=sig)
        assert result.verified is True

    def test_dispatch_token(self):
        v = WebhookVerifier()
        v.register("telegram", ChannelVerifierConfig(
            channel="telegram",
            method=VerificationMethod.TOKEN_COMPARE,
            secret="my-token",
        ))
        result = v.verify(channel="telegram", token="my-token")
        assert result.verified is True

    def test_dispatch_ed25519(self):
        v = WebhookVerifier()
        v.register("discord", ChannelVerifierConfig(
            channel="discord",
            method=VerificationMethod.ED25519,
            secret="aa" * 32,
        ))
        result = v.verify(channel="discord", body="test", signature="00" * 64)
        assert result.verified is False  # Wrong signature

    def test_dispatch_unconfigured(self):
        v = WebhookVerifier()
        result = v.verify(channel="unknown", body="test")
        assert result.verified is True


# ── Counters and status ───────────────────────────────────────

class TestCountersAndStatus:
    def test_verified_count(self):
        v = WebhookVerifier()
        v.register("ch", ChannelVerifierConfig(
            channel="ch",
            method=VerificationMethod.HMAC_SHA256,
            secret="sec",
        ))
        body = "test"
        sig = hmac_mod.new(b"sec", body.encode(), hashlib.sha256).hexdigest()
        v.verify_hmac(channel="ch", body=body, signature=sig)
        assert v.verified_count == 1

    def test_rejected_count(self):
        v = WebhookVerifier()
        v.register("ch", ChannelVerifierConfig(
            channel="ch",
            method=VerificationMethod.HMAC_SHA256,
            secret="sec",
        ))
        v.verify_hmac(channel="ch", body="test", signature="bad")
        assert v.rejected_count == 1

    def test_skipped_count(self):
        v = WebhookVerifier()
        v.verify_hmac(channel="unknown", body="test", signature="sig")
        assert v.skipped_count == 1

    def test_status(self):
        v = WebhookVerifier()
        v.register("slack", ChannelVerifierConfig(
            channel="slack",
            method=VerificationMethod.HMAC_SHA256,
            secret="sec",
        ))
        status = v.status()
        assert "slack" in status["configured_channels"]
        assert "total_verified" in status
        assert "total_rejected" in status


# ── Multi-channel registry ────────────────────────────────────

class TestMultiChannel:
    def test_register_multiple_channels(self):
        v = WebhookVerifier()
        v.register("slack", ChannelVerifierConfig(
            channel="slack", method=VerificationMethod.HMAC_SHA256, secret="s1",
        ))
        v.register("telegram", ChannelVerifierConfig(
            channel="telegram", method=VerificationMethod.TOKEN_COMPARE, secret="t1",
        ))
        v.register("discord", ChannelVerifierConfig(
            channel="discord", method=VerificationMethod.ED25519, secret="aa" * 32,
        ))
        assert len(v.status()["configured_channels"]) == 3

    def test_channels_independent(self):
        v = WebhookVerifier()
        v.register("slack", ChannelVerifierConfig(
            channel="slack", method=VerificationMethod.HMAC_SHA256, secret="slack-secret",
        ))
        v.register("whatsapp", ChannelVerifierConfig(
            channel="whatsapp", method=VerificationMethod.HMAC_SHA256, secret="wa-secret",
        ))
        body = "test"
        slack_sig = hmac_mod.new(b"slack-secret", body.encode(), hashlib.sha256).hexdigest()
        wa_sig = hmac_mod.new(b"wa-secret", body.encode(), hashlib.sha256).hexdigest()
        # Slack sig should not verify on WhatsApp channel
        r1 = v.verify_hmac(channel="whatsapp", body=body, signature=slack_sig)
        assert r1.verified is False
        # Correct sig per channel
        r2 = v.verify_hmac(channel="whatsapp", body=body, signature=wa_sig)
        assert r2.verified is True
