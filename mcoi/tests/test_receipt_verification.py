"""Tests for the public verification surface: published_verification_key
and the composed fully_verify_receipt verdict.

This is the "make signing actually consumable" layer — the single
operation a trust boundary / external auditor calls.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from mcoi_runtime.contracts.proof import certify_transition
from mcoi_runtime.contracts.receipt_signing import (
    Ed25519ReceiptSigner,
    Ed25519ReceiptVerifier,
    generate_keypair,
    published_verification_key,
    reset_default_signer_cache,
)
from mcoi_runtime.core.proof_bridge import GOVERNANCE_MACHINE, ProofBridge

_TS = "2026-01-01T00:00:00Z"


def _certify(signer=None):
    return certify_transition(
        GOVERNANCE_MACHINE,
        entity_id="request:t1:/api/x",
        from_state="pending",
        to_state="evaluating",
        action="start_evaluation",
        before_state_hash="b" * 64,
        after_state_hash="a" * 64,
        guards=(),
        actor_id="user1",
        reason="unit test",
        timestamp=_TS,
        signer=signer,
    ).receipt


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_default_signer_cache()
    yield
    reset_default_signer_cache()


# ── published_verification_key (the public trust artifact) ──────────────


def test_published_key_unsigned_mode_is_honest(monkeypatch):
    monkeypatch.delenv("MCOI_RECEIPT_SIGNING_KEY", raising=False)
    reset_default_signer_cache()
    key = published_verification_key()
    assert key["mode"] == "unsigned"
    assert key["public_key_hex"] == ""
    assert key["key_id"] == ""
    # Must be JSON-serializable for an HTTP/CLI surface.
    assert json.loads(json.dumps(key))["algorithm"] == "ed25519"


def test_published_key_signed_mode_exposes_public_half(monkeypatch):
    seed_hex, pub_hex, key_id = generate_keypair()
    monkeypatch.setenv("MCOI_RECEIPT_SIGNING_KEY", seed_hex)
    reset_default_signer_cache()
    key = published_verification_key()
    assert key["mode"] == "signed"
    assert key["public_key_hex"] == pub_hex
    assert key["key_id"] == key_id
    # The published key must actually verify a receipt signed by the
    # configured signer — i.e. it is the real public half.
    receipt = _certify()
    verifier = Ed25519ReceiptVerifier(public_key_hex=key["public_key_hex"])
    assert ProofBridge.fully_verify_receipt(receipt, verifier).fully_trusted


# ── fully_verify_receipt (composed verdict) ─────────────────────────────


def test_unsigned_receipt_is_intact_but_not_fully_trusted():
    v = ProofBridge.fully_verify_receipt(_certify())
    assert v.integrity_ok
    assert v.replay_token_ok
    assert v.signature_status == "unsigned"
    assert v.fully_trusted is False


def test_signed_receipt_with_key_is_fully_trusted():
    seed_hex, pub_hex, _ = generate_keypair()
    signer = Ed25519ReceiptSigner.from_seed_hex(seed_hex)
    receipt = _certify(signer=signer)
    v = ProofBridge.fully_verify_receipt(
        receipt, Ed25519ReceiptVerifier(public_key_hex=pub_hex)
    )
    assert v.fully_trusted is True
    assert v.signature_status == "signed_valid"


def test_signed_receipt_without_verifier_reports_no_key():
    seed_hex, _, _ = generate_keypair()
    receipt = _certify(signer=Ed25519ReceiptSigner.from_seed_hex(seed_hex))
    v = ProofBridge.fully_verify_receipt(receipt)  # no verifier
    assert v.integrity_ok
    assert v.signature_status == "no_verifier_key"
    assert v.fully_trusted is False


def test_tampered_hash_fails_integrity_and_trust():
    receipt = _certify()
    forged = dataclasses.replace(receipt, receipt_hash="f" * 64)
    v = ProofBridge.fully_verify_receipt(forged)
    assert v.integrity_ok is False
    assert v.fully_trusted is False


def test_tampered_replay_token_fails_that_check():
    receipt = _certify()
    forged = dataclasses.replace(receipt, replay_token="replay-deadbeef")
    v = ProofBridge.fully_verify_receipt(forged)
    assert v.integrity_ok is True
    assert v.replay_token_ok is False
    assert v.fully_trusted is False


def test_wrong_key_is_signed_invalid_not_trusted():
    seed_hex, _, _ = generate_keypair()
    receipt = _certify(signer=Ed25519ReceiptSigner.from_seed_hex(seed_hex))
    _, other_pub, _ = generate_keypair()
    v = ProofBridge.fully_verify_receipt(
        receipt, Ed25519ReceiptVerifier(public_key_hex=other_pub)
    )
    assert v.signature_status == "signed_invalid"
    assert v.fully_trusted is False


def test_verification_record_is_json_serializable():
    v = ProofBridge.fully_verify_receipt(_certify())
    blob = json.loads(v.to_json())
    assert blob["receipt_id"].startswith("rcpt-")
    assert blob["signature_status"] == "unsigned"
    assert blob["fully_trusted"] is False
