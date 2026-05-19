"""Tests for cryptographic authenticity of transition receipts.

Covers: graceful unsigned default, Ed25519 sign/verify roundtrip,
tamper detection, missing/loud-misconfigured keys, JSONL roundtrip of
the new fields, and conditional wire-format emission.
"""

from __future__ import annotations

import dataclasses

import pytest

from mcoi_runtime.contracts.proof import certify_transition
from mcoi_runtime.contracts.receipt_signing import (
    Ed25519ReceiptSigner,
    Ed25519ReceiptVerifier,
    NullReceiptSigner,
    ReceiptSignatureStatus,
    default_signer,
    generate_keypair,
    reset_default_signer_cache,
)
from mcoi_runtime.contracts.receipt_store import JsonlReceiptStore
from mcoi_runtime.core.proof_bridge import GOVERNANCE_MACHINE, ProofBridge

_TS = "2026-01-01T00:00:00Z"


def _clock() -> str:
    return _TS


def _certify(signer=None):
    """A single legal transition, optionally signed."""
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
def _clear_signer_cache():
    reset_default_signer_cache()
    yield
    reset_default_signer_cache()


# ── graceful unsigned default ───────────────────────────────────────────


def test_default_signer_is_null_without_env(monkeypatch):
    monkeypatch.delenv("MCOI_RECEIPT_SIGNING_KEY", raising=False)
    monkeypatch.delenv("MCOI_RECEIPT_SIGNING_KEY_FILE", raising=False)
    reset_default_signer_cache()
    assert isinstance(default_signer(), NullReceiptSigner)


def test_unsigned_receipt_has_empty_signature_fields(monkeypatch):
    monkeypatch.delenv("MCOI_RECEIPT_SIGNING_KEY", raising=False)
    reset_default_signer_cache()
    receipt = _certify()
    assert receipt.signature == ""
    assert receipt.signing_key_id == ""
    # Integrity path unaffected.
    bridge = ProofBridge(clock=_clock)
    assert bridge.verify_receipt(receipt) is True


def test_verifier_reports_unsigned():
    _, pub_hex, _ = generate_keypair()
    verifier = Ed25519ReceiptVerifier(public_key_hex=pub_hex)
    receipt = _certify()  # unsigned
    assert verifier.verify(receipt) is ReceiptSignatureStatus.UNSIGNED


# ── Ed25519 sign / verify roundtrip ─────────────────────────────────────


def test_sign_verify_roundtrip():
    seed_hex, pub_hex, key_id = generate_keypair()
    signer = Ed25519ReceiptSigner.from_seed_hex(seed_hex)
    receipt = _certify(signer=signer)

    assert receipt.signature != ""
    assert receipt.signing_key_id == key_id

    verifier = Ed25519ReceiptVerifier(public_key_hex=pub_hex)
    assert verifier.verify(receipt) is ReceiptSignatureStatus.SIGNED_VALID
    # Signing must not disturb hash integrity.
    assert ProofBridge(clock=_clock).verify_receipt(receipt) is True


def test_keyring_selection_by_key_id():
    seed_hex, pub_hex, key_id = generate_keypair()
    signer = Ed25519ReceiptSigner.from_seed_hex(seed_hex)
    receipt = _certify(signer=signer)
    verifier = Ed25519ReceiptVerifier(key_ring={key_id: pub_hex})
    assert verifier.verify(receipt) is ReceiptSignatureStatus.SIGNED_VALID


# ── tamper detection ────────────────────────────────────────────────────


def test_tampered_receipt_hash_fails_signature():
    seed_hex, pub_hex, _ = generate_keypair()
    signer = Ed25519ReceiptSigner.from_seed_hex(seed_hex)
    receipt = _certify(signer=signer)
    forged = dataclasses.replace(receipt, receipt_hash="f" * 64)
    verifier = Ed25519ReceiptVerifier(public_key_hex=pub_hex)
    assert verifier.verify(forged) is ReceiptSignatureStatus.SIGNED_INVALID


def test_wrong_key_fails_signature():
    seed_hex, _, _ = generate_keypair()
    signer = Ed25519ReceiptSigner.from_seed_hex(seed_hex)
    receipt = _certify(signer=signer)
    _, other_pub, _ = generate_keypair()
    verifier = Ed25519ReceiptVerifier(public_key_hex=other_pub)
    assert verifier.verify(receipt) is ReceiptSignatureStatus.SIGNED_INVALID


def test_garbage_signature_is_invalid_not_crash():
    receipt = _certify()
    forged = dataclasses.replace(receipt, signature="zz", signing_key_id="x")
    _, pub_hex, _ = generate_keypair()
    verifier = Ed25519ReceiptVerifier(public_key_hex=pub_hex)
    assert verifier.verify(forged) is ReceiptSignatureStatus.SIGNED_INVALID


def test_signed_receipt_without_matching_key_is_no_verifier_key():
    seed_hex, _, _ = generate_keypair()
    signer = Ed25519ReceiptSigner.from_seed_hex(seed_hex)
    receipt = _certify(signer=signer)
    verifier = Ed25519ReceiptVerifier(key_ring={"ed25519:other": "00" * 32})
    assert verifier.verify(receipt) is ReceiptSignatureStatus.NO_VERIFIER_KEY


# ── loud misconfiguration vs silent absence ─────────────────────────────


def test_malformed_env_key_raises_not_silently_unsigned(monkeypatch):
    monkeypatch.setenv("MCOI_RECEIPT_SIGNING_KEY", "not-hex-at-all")
    reset_default_signer_cache()
    with pytest.raises(ValueError):
        default_signer()


def test_wrong_length_seed_raises():
    with pytest.raises(ValueError):
        Ed25519ReceiptSigner.from_seed_hex("ab" * 8)  # 8 bytes, not 32


def test_env_key_drives_default_signed_path(monkeypatch):
    seed_hex, pub_hex, key_id = generate_keypair()
    monkeypatch.setenv("MCOI_RECEIPT_SIGNING_KEY", seed_hex)
    reset_default_signer_cache()
    receipt = _certify()  # no explicit signer -> default from env
    assert receipt.signing_key_id == key_id
    verifier = Ed25519ReceiptVerifier(public_key_hex=pub_hex)
    assert verifier.verify(receipt) is ReceiptSignatureStatus.SIGNED_VALID


# ── persistence + wire-format ───────────────────────────────────────────


def test_jsonl_roundtrip_preserves_signature(tmp_path):
    seed_hex, pub_hex, key_id = generate_keypair()
    signer = Ed25519ReceiptSigner.from_seed_hex(seed_hex)
    receipt = _certify(signer=signer)

    path = tmp_path / "receipts.jsonl"
    JsonlReceiptStore(path).record_receipt(receipt)
    reloaded = JsonlReceiptStore(path).get_receipt(receipt.receipt_id)

    assert reloaded is not None
    assert reloaded.signature == receipt.signature
    assert reloaded.signing_key_id == key_id
    verifier = Ed25519ReceiptVerifier(public_key_hex=pub_hex)
    assert verifier.verify(reloaded) is ReceiptSignatureStatus.SIGNED_VALID


def test_serialize_proof_omits_signature_when_unsigned(monkeypatch):
    monkeypatch.delenv("MCOI_RECEIPT_SIGNING_KEY", raising=False)
    reset_default_signer_cache()
    bridge = ProofBridge(clock=_clock)
    proof = bridge.certify_governance_decision(
        tenant_id="t1", endpoint="/api/x",
        guard_results=[{"guard_name": "g", "allowed": True, "reason": ""}],
        decision="allowed",
    )
    receipt_json = bridge.serialize_proof(proof)["receipt"]
    assert "signature" not in receipt_json
    assert "signing_key_id" not in receipt_json


def test_serialize_proof_includes_signature_when_signed(monkeypatch):
    seed_hex, _, key_id = generate_keypair()
    monkeypatch.setenv("MCOI_RECEIPT_SIGNING_KEY", seed_hex)
    reset_default_signer_cache()
    bridge = ProofBridge(clock=_clock)
    proof = bridge.certify_governance_decision(
        tenant_id="t1", endpoint="/api/x",
        guard_results=[{"guard_name": "g", "allowed": True, "reason": ""}],
        decision="allowed",
    )
    receipt_json = bridge.serialize_proof(proof)["receipt"]
    assert receipt_json["signature"] != ""
    assert receipt_json["signing_key_id"] == key_id


def test_bridge_verify_receipt_signature_helper():
    seed_hex, pub_hex, _ = generate_keypair()
    signer = Ed25519ReceiptSigner.from_seed_hex(seed_hex)
    receipt = _certify(signer=signer)
    verifier = Ed25519ReceiptVerifier(public_key_hex=pub_hex)
    assert (
        ProofBridge.verify_receipt_signature(receipt, verifier)
        is ReceiptSignatureStatus.SIGNED_VALID
    )
