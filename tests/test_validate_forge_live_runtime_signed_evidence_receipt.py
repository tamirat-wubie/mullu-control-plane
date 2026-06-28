"""Forge live-runtime signed evidence receipt validator tests.

Purpose: verify the signed evidence receipt remains a Foundation Mode shape
until real signed live evidence is supplied through an approved probe.
Governance scope: signed receipt absence, verification denial, authority
denial, source acceptance gate binding, and fixture drift rejection.
Dependencies: scripts.validate_forge_live_runtime_signed_evidence_receipt.
Invariants:
  - The Foundation fixture is deterministic and schema-backed.
  - Signed live evidence remains not present.
  - Signature verification remains not_verified.
  - Runtime, production, commit, external-effect, and terminal closure
    authority remain false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.forge_state_write_admission import build_foundation_forge_live_runtime_signed_evidence_receipt
from scripts.validate_forge_live_runtime_signed_evidence_receipt import (
    DEFAULT_RECEIPT,
    DEFAULT_SCHEMA,
    validate_forge_live_runtime_signed_evidence_receipt,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_checked_in_forge_live_runtime_signed_evidence_receipt_is_valid() -> None:
    validation, produced_receipt = validate_forge_live_runtime_signed_evidence_receipt()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.receipt_id == "forge-live-runtime-signed-evidence-receipt.v1"
    assert validation.receipt_status == "awaiting_signed_live_evidence"
    assert validation.evidence_receipt_count == 10
    assert validation.blocked_reason_count == 10
    assert produced_receipt["solver_outcome"] == "AwaitingEvidence"
    assert produced_receipt["disallowed_authority"]["commit_allowed"] is False


def test_produced_signed_evidence_receipt_matches_schema() -> None:
    receipt = build_foundation_forge_live_runtime_signed_evidence_receipt()
    errors = _validate_schema_instance(_load_schema(DEFAULT_SCHEMA), receipt)

    assert errors == []
    assert receipt["receipt_status"] == "awaiting_signed_live_evidence"
    assert len(receipt["evidence_receipts"]) == 10
    assert all(item["signed_live_receipt_status"] == "not_present" for item in receipt["evidence_receipts"])
    assert all(item["verification_status"] == "not_verified" for item in receipt["evidence_receipts"])


def test_validator_rejects_signed_live_receipt_overclaim(tmp_path: Path) -> None:
    receipt = _load_receipt()
    item = receipt["evidence_receipts"][0]
    item["signed_live_receipt_status"] = "present"
    item["signed_live_receipt_ref"] = "receipt://forge/live-runtime/managed-key-custody"
    item["signed_live_receipt_hash"] = "0" * 64
    receipt_path = _write_receipt(tmp_path, receipt)

    validation, _produced_receipt = validate_forge_live_runtime_signed_evidence_receipt(
        schema_path=DEFAULT_SCHEMA,
        receipt_path=receipt_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.signed_live_receipt_status" in error for error in validation.errors)
    assert any("managed_key_custody.signed_live_receipt_ref" in error for error in validation.errors)
    assert any("managed_key_custody.signed_live_receipt_hash" in error for error in validation.errors)


def test_validator_rejects_verification_and_signature_overclaim(tmp_path: Path) -> None:
    receipt = _load_receipt()
    item = receipt["evidence_receipts"][0]
    item["verification_status"] = "verified"
    item["signing_key_id"] = "forge-live-key-1"
    item["trust_epoch"] = "runtime-epoch-1"
    item["signature"] = "ed25519:runtime_signature"
    receipt_path = _write_receipt(tmp_path, receipt)

    validation, _produced_receipt = validate_forge_live_runtime_signed_evidence_receipt(
        schema_path=DEFAULT_SCHEMA,
        receipt_path=receipt_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.verification_status" in error for error in validation.errors)
    assert any("managed_key_custody.signing_key_id" in error for error in validation.errors)
    assert any("managed_key_custody.signature" in error for error in validation.errors)


def test_validator_rejects_probe_and_recovery_ref_overclaim(tmp_path: Path) -> None:
    receipt = _load_receipt()
    item = receipt["evidence_receipts"][0]
    item["dependency_or_credential_probe_ref"] = "evidence://forge/live-runtime/managed-key-custody/credential-probe"
    item["recovery_or_revocation_ref"] = "evidence://forge/live-runtime/managed-key-custody/revocation-path"
    receipt_path = _write_receipt(tmp_path, receipt)

    validation, _produced_receipt = validate_forge_live_runtime_signed_evidence_receipt(
        schema_path=DEFAULT_SCHEMA,
        receipt_path=receipt_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.dependency_or_credential_probe_ref" in error for error in validation.errors)
    assert any("managed_key_custody.recovery_or_revocation_ref" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_runtime_authority_overclaim(tmp_path: Path) -> None:
    receipt = _load_receipt()
    receipt["disallowed_authority"]["state_write_runtime_registered"] = True
    receipt["disallowed_authority"]["commit_allowed"] = True
    receipt["disallowed_authority"]["terminal_closure"] = True
    receipt_path = _write_receipt(tmp_path, receipt)

    validation, _produced_receipt = validate_forge_live_runtime_signed_evidence_receipt(
        schema_path=DEFAULT_SCHEMA,
        receipt_path=receipt_path,
    )

    assert validation.ok is False
    assert any("state_write_runtime_registered" in error for error in validation.errors)
    assert any("commit_allowed" in error for error in validation.errors)
    assert any("terminal_closure" in error for error in validation.errors)


def test_validator_rejects_order_and_blocker_drift(tmp_path: Path) -> None:
    receipt = _load_receipt()
    items = receipt["evidence_receipts"]
    receipt["evidence_receipts"] = [items[1], items[0], *items[2:]]
    receipt["blocked_reasons"] = receipt["blocked_reasons"][1:]
    receipt_path = _write_receipt(tmp_path, receipt)

    validation, _produced_receipt = validate_forge_live_runtime_signed_evidence_receipt(
        schema_path=DEFAULT_SCHEMA,
        receipt_path=receipt_path,
    )

    assert validation.ok is False
    assert any("evidence_receipts order drift" in error for error in validation.errors)
    assert any("blocked_reasons drift" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_source_acceptance_gate_hash_drift(tmp_path: Path) -> None:
    receipt = _load_receipt()
    receipt["source_acceptance_gate_hash"] = "0" * 64
    receipt_path = _write_receipt(tmp_path, receipt)

    validation, _produced_receipt = validate_forge_live_runtime_signed_evidence_receipt(
        schema_path=DEFAULT_SCHEMA,
        receipt_path=receipt_path,
    )

    assert validation.ok is False
    assert any("source_acceptance_gate_hash mismatch" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def _load_receipt() -> dict[str, Any]:
    return json.loads(DEFAULT_RECEIPT.read_text(encoding="utf-8"))


def _write_receipt(tmp_path: Path, receipt: dict[str, Any]) -> Path:
    receipt_path = tmp_path / "forge_live_runtime_signed_evidence_receipt.foundation.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path
