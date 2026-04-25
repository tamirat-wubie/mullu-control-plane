"""Webhook signature verification tests.

Purpose: verify bounded signature verification rejection summaries.
Governance scope: webhook authentication observability only.
Dependencies: gateway.signature_verification.
Invariants:
  - Rejection summaries use bounded reason codes.
  - Raw signatures and tokens are not promoted into summary keys.
  - Skip and reject accounting remain separate.
"""

import hashlib
import hmac

from gateway.signature_verification import (
    ChannelVerifierConfig,
    VerificationMethod,
    WebhookVerifier,
)


def _hmac_signature(secret: str, body: str) -> str:
    return hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def test_hmac_rejections_report_bounded_reasons() -> None:
    verifier = WebhookVerifier(clock=lambda: 1000.0)
    verifier.register(
        "slack",
        ChannelVerifierConfig(
            channel="slack",
            method=VerificationMethod.HMAC_SHA256,
            secret="secret",
        ),
    )

    missing = verifier.verify_hmac(channel="slack", body="payload", signature="")
    mismatch = verifier.verify_hmac(channel="slack", body="payload", signature="raw-secret-signature")
    status = verifier.status()

    assert missing.reject_reason == "missing_signature"
    assert mismatch.reject_reason == "signature_mismatch"
    assert status["total_rejected"] == 2
    assert status["reject_reasons"] == {
        "missing_signature": 1,
        "signature_mismatch": 1,
    }
    assert "raw-secret-signature" not in status["reject_reasons"]


def test_hmac_replay_rejections_report_bounded_reasons() -> None:
    verifier = WebhookVerifier(clock=lambda: 1000.0)
    verifier.register(
        "slack",
        ChannelVerifierConfig(
            channel="slack",
            method=VerificationMethod.HMAC_SHA256,
            secret="secret",
            replay_window_seconds=10.0,
        ),
    )

    invalid = verifier.verify_hmac(channel="slack", body="payload", signature="sig", timestamp="not-a-time")
    stale = verifier.verify_hmac(channel="slack", body="payload", signature="sig", timestamp="1")
    status = verifier.status()

    assert invalid.replay_checked is True
    assert invalid.reject_reason == "invalid_timestamp"
    assert stale.reject_reason == "timestamp_out_of_window"
    assert status["reject_reasons"] == {
        "invalid_timestamp": 1,
        "timestamp_out_of_window": 1,
    }


def test_token_rejections_report_bounded_reasons() -> None:
    verifier = WebhookVerifier()
    verifier.register(
        "telegram",
        ChannelVerifierConfig(
            channel="telegram",
            method=VerificationMethod.TOKEN_COMPARE,
            secret="expected-token",
        ),
    )

    missing = verifier.verify_token(channel="telegram", provided_token="")
    mismatch = verifier.verify_token(channel="telegram", provided_token="provided-secret-token")
    status = verifier.status()

    assert missing.reject_reason == "missing_token"
    assert mismatch.reject_reason == "token_mismatch"
    assert status["total_rejected"] == 2
    assert status["reject_reasons"] == {
        "missing_token": 1,
        "token_mismatch": 1,
    }
    assert "provided-secret-token" not in status["reject_reasons"]


def test_verified_and_skipped_requests_do_not_create_reject_reasons() -> None:
    verifier = WebhookVerifier()
    verifier.register(
        "slack",
        ChannelVerifierConfig(
            channel="slack",
            method=VerificationMethod.HMAC_SHA256,
            secret="secret",
        ),
    )
    signature = _hmac_signature("secret", "payload")

    verified = verifier.verify_hmac(channel="slack", body="payload", signature=signature)
    skipped = verifier.verify_hmac(channel="unknown", body="payload", signature="anything")
    status = verifier.status()

    assert verified.verified is True
    assert skipped.skip_reason == "channel_not_configured"
    assert status["total_verified"] == 1
    assert status["total_skipped"] == 1
    assert status["reject_reasons"] == {}
    assert status["skip_reasons"] == {"channel_not_configured": 1}
