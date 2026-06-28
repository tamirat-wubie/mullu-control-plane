"""Forge live-runtime evidence acceptance gate validator tests.

Purpose: verify the Forge live-runtime evidence acceptance gate blocks runtime
promotion until signed live evidence exists for every blocker.
Governance scope: signed evidence requirement, local artifact insufficiency,
production authority denial, commit denial, external-effect denial, and fixture
drift rejection.
Dependencies: scripts.validate_forge_live_runtime_evidence_acceptance_gate.
Invariants:
  - The Foundation fixture is deterministic and schema-backed.
  - Signed live evidence remains missing.
  - Local design artifacts are not sufficient for runtime promotion.
  - Runtime, production, commit, external-effect, and terminal closure
    authority remain false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.forge_state_write_admission import build_foundation_forge_live_runtime_evidence_acceptance_gate
from scripts.validate_forge_live_runtime_evidence_acceptance_gate import (
    DEFAULT_GATE,
    DEFAULT_SCHEMA,
    validate_forge_live_runtime_evidence_acceptance_gate,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_checked_in_forge_live_runtime_evidence_acceptance_gate_is_valid() -> None:
    validation, produced_gate = validate_forge_live_runtime_evidence_acceptance_gate()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.gate_id == "forge-live-runtime-evidence-acceptance-gate.v1"
    assert validation.acceptance_status == "blocked_awaiting_signed_live_evidence"
    assert validation.acceptance_item_count == 10
    assert validation.blocked_reason_count == 10
    assert produced_gate["solver_outcome"] == "AwaitingEvidence"
    assert produced_gate["disallowed_authority"]["commit_allowed"] is False


def test_produced_evidence_acceptance_gate_matches_schema() -> None:
    gate = build_foundation_forge_live_runtime_evidence_acceptance_gate()
    errors = _validate_schema_instance(_load_schema(DEFAULT_SCHEMA), gate)

    assert errors == []
    assert gate["admission_decision"] == "block_live_runtime_promotion"
    assert len(gate["acceptance_items"]) == 10
    assert all(item["live_evidence_status"] == "missing" for item in gate["acceptance_items"])
    assert all(item["local_artifact_sufficient"] is False for item in gate["acceptance_items"])


def test_validator_rejects_signed_live_evidence_overclaim(tmp_path: Path) -> None:
    gate = _load_gate()
    gate["acceptance_items"][0]["live_evidence_status"] = "present"
    gate["acceptance_items"][0]["acceptance_status"] = "accepted"
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_evidence_acceptance_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.live_evidence_status" in error for error in validation.errors)
    assert any("managed_key_custody.acceptance_status" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_local_artifact_sufficiency_overclaim(tmp_path: Path) -> None:
    gate = _load_gate()
    gate["acceptance_items"][0]["local_artifact_sufficient"] = True
    gate["acceptance_items"][0]["authority_effect"] = True
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_evidence_acceptance_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.local_artifact_sufficient" in error for error in validation.errors)
    assert any("managed_key_custody.authority_effect" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_runtime_authority_overclaim(tmp_path: Path) -> None:
    gate = _load_gate()
    gate["disallowed_authority"]["state_write_runtime_registered"] = True
    gate["disallowed_authority"]["commit_allowed"] = True
    gate["disallowed_authority"]["terminal_closure"] = True
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_evidence_acceptance_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("state_write_runtime_registered" in error for error in validation.errors)
    assert any("commit_allowed" in error for error in validation.errors)
    assert any("terminal_closure" in error for error in validation.errors)


def test_validator_rejects_order_and_blocker_drift(tmp_path: Path) -> None:
    gate = _load_gate()
    items = gate["acceptance_items"]
    gate["acceptance_items"] = [items[1], items[0], *items[2:]]
    gate["blocked_reasons"] = gate["blocked_reasons"][1:]
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_evidence_acceptance_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("acceptance_items order drift" in error for error in validation.errors)
    assert any("blocked_reasons drift" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_source_local_bundle_hash_drift(tmp_path: Path) -> None:
    gate = _load_gate()
    gate["source_local_evidence_bundle_hash"] = "0" * 64
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_evidence_acceptance_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("source_local_evidence_bundle_hash mismatch" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def _load_gate() -> dict[str, Any]:
    return json.loads(DEFAULT_GATE.read_text(encoding="utf-8"))


def _write_gate(tmp_path: Path, gate: dict[str, Any]) -> Path:
    gate_path = tmp_path / "forge_live_runtime_evidence_acceptance_gate.foundation.json"
    gate_path.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return gate_path
