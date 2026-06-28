"""Forge live-runtime signed receipt population gate validator tests.

Purpose: verify signed live evidence receipt population remains blocked until
reconciled probe outputs and signature evidence exist.
Governance scope: signed receipt refs, signing key and signature evidence,
runtime authority denial, source reconciliation binding, and fixture drift
rejection.
Dependencies: scripts.validate_forge_live_runtime_signed_receipt_population_gate.
Invariants:
  - The Foundation fixture is deterministic and schema-backed.
  - Signed receipt population remains disallowed.
  - Signing and receipt refs remain empty.
  - Runtime, production, commit, external-effect, and terminal closure
    authority remain false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.forge_state_write_admission import (
    build_foundation_forge_live_runtime_signed_receipt_population_gate,
)
from scripts.validate_forge_live_runtime_signed_receipt_population_gate import (
    DEFAULT_GATE,
    DEFAULT_SCHEMA,
    validate_forge_live_runtime_signed_receipt_population_gate,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_checked_in_forge_live_runtime_signed_receipt_population_gate_is_valid() -> None:
    validation, produced_gate = validate_forge_live_runtime_signed_receipt_population_gate()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.gate_id == "forge-live-runtime-signed-receipt-population-gate.v1"
    assert validation.population_status == "blocked_awaiting_reconciled_probe_outputs"
    assert validation.population_item_count == 10
    assert validation.blocked_reason_count == 10
    assert produced_gate["receipt_population_allowed"] is False
    assert produced_gate["signed_receipt_refs_populated"] is False
    assert produced_gate["runtime_authority_effect"] is False


def test_produced_signed_receipt_population_gate_matches_schema() -> None:
    gate = build_foundation_forge_live_runtime_signed_receipt_population_gate()
    errors = _validate_schema_instance(_load_schema(DEFAULT_SCHEMA), gate)

    assert errors == []
    assert gate["population_mode"] == "signed_receipt_population_requires_reconciled_probe_outputs"
    assert len(gate["population_items"]) == 10
    assert all(item["verification_status"] == "not_verified" for item in gate["population_items"])
    assert all(item["population_status"] == "blocked" for item in gate["population_items"])


def test_validator_rejects_signed_receipt_ref_overclaim(tmp_path: Path) -> None:
    gate = _load_gate()
    item = gate["population_items"][0]
    item["signed_receipt_update_ref"] = "receipt-update://forge/live-runtime/managed-key-custody"
    item["signed_live_receipt_ref"] = "signed-receipt://forge/live-runtime/managed-key-custody"
    item["population_status"] = "ready"
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_signed_receipt_population_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.signed_receipt_update_ref" in error for error in validation.errors)
    assert any("managed_key_custody.signed_live_receipt_ref" in error for error in validation.errors)
    assert any("managed_key_custody.population_status" in error for error in validation.errors)


def test_validator_rejects_signature_evidence_overclaim(tmp_path: Path) -> None:
    gate = _load_gate()
    item = gate["population_items"][0]
    item["signing_key_id"] = "forge-key-1"
    item["trust_epoch"] = "foundation-epoch-1"
    item["signature"] = "signature"
    item["verification_status"] = "verified"
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_signed_receipt_population_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.signing_key_id" in error for error in validation.errors)
    assert any("managed_key_custody.trust_epoch" in error for error in validation.errors)
    assert any("managed_key_custody.signature" in error for error in validation.errors)
    assert any("managed_key_custody.verification_status" in error for error in validation.errors)


def test_validator_rejects_top_level_population_overclaim(tmp_path: Path) -> None:
    gate = _load_gate()
    gate["receipt_population_allowed"] = True
    gate["signed_receipt_refs_populated"] = True
    gate["runtime_authority_effect"] = True
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_signed_receipt_population_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("receipt_population_allowed" in error for error in validation.errors)
    assert any("signed_receipt_refs_populated" in error for error in validation.errors)
    assert any("runtime_authority_effect" in error for error in validation.errors)


def test_validator_rejects_runtime_authority_overclaim(tmp_path: Path) -> None:
    gate = _load_gate()
    gate["disallowed_authority"]["live_runtime_authorized"] = True
    gate["disallowed_authority"]["external_effects_allowed"] = True
    gate["disallowed_authority"]["terminal_closure"] = True
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_signed_receipt_population_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("live_runtime_authorized" in error for error in validation.errors)
    assert any("external_effects_allowed" in error for error in validation.errors)
    assert any("terminal_closure" in error for error in validation.errors)


def test_validator_rejects_order_and_blocker_drift(tmp_path: Path) -> None:
    gate = _load_gate()
    items = gate["population_items"]
    gate["population_items"] = [items[1], items[0], *items[2:]]
    gate["blocked_reasons"] = gate["blocked_reasons"][1:]
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_signed_receipt_population_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("population_items order drift" in error for error in validation.errors)
    assert any("blocked_reasons drift" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_source_post_probe_reconciliation_packet_hash_drift(tmp_path: Path) -> None:
    gate = _load_gate()
    gate["source_post_probe_reconciliation_packet_hash"] = "0" * 64
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_signed_receipt_population_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("source_post_probe_reconciliation_packet_hash mismatch" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def _load_gate() -> dict[str, Any]:
    return json.loads(DEFAULT_GATE.read_text(encoding="utf-8"))


def _write_gate(tmp_path: Path, gate: dict[str, Any]) -> Path:
    gate_path = tmp_path / "forge_live_runtime_signed_receipt_population_gate.foundation.json"
    gate_path.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return gate_path
