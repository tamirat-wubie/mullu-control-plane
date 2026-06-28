"""Forge live-runtime readiness gate validator tests.

Purpose: verify the Forge live-runtime gate blocks state-write runtime
registration until explicit evidence exists.
Governance scope: production authority denial, runtime registration denial,
commit denial, external-effect denial, and missing-evidence traceability.
Dependencies: scripts.validate_forge_live_runtime_readiness_gate.
Invariants:
  - The Foundation fixture is blocked and deterministic.
  - Required evidence remains absent and ordered.
  - Runtime, production, commit, and external-effect overclaims fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.forge_state_write_admission import build_foundation_forge_live_runtime_readiness_gate
from scripts.validate_forge_live_runtime_readiness_gate import (
    DEFAULT_GATE,
    DEFAULT_SCHEMA,
    validate_forge_live_runtime_readiness_gate,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_checked_in_forge_live_runtime_readiness_gate_is_valid() -> None:
    validation, produced_gate = validate_forge_live_runtime_readiness_gate()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.gate_id == "forge-live-runtime-readiness-gate.v1"
    assert validation.readiness_status == "blocked_awaiting_evidence"
    assert validation.evidence_count == 10
    assert validation.blocked_reason_count == 10
    assert produced_gate["commit_allowed"] is False
    assert produced_gate["live_runtime_authorized"] is False


def test_produced_readiness_gate_matches_schema() -> None:
    gate = build_foundation_forge_live_runtime_readiness_gate()
    errors = _validate_schema_instance(_load_schema(DEFAULT_SCHEMA), gate)

    assert errors == []
    assert gate["solver_outcome"] == "AwaitingEvidence"
    assert gate["admission_decision"] == "block_live_runtime"
    assert all(item["present"] is False for item in gate["required_evidence"])
    assert all(item["evidence_ref"] == "" for item in gate["required_evidence"])


def test_validator_rejects_runtime_authority_overclaim(tmp_path: Path) -> None:
    gate = _load_gate()
    gate["live_runtime_authorized"] = True
    gate["state_write_runtime_registered"] = True
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_readiness_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("live_runtime_authorized" in error for error in validation.errors)
    assert any("state_write_runtime_registered" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_commit_and_production_overclaim(tmp_path: Path) -> None:
    gate = _load_gate()
    gate["commit_allowed"] = True
    gate["production_authorized"] = True
    gate["external_effects_allowed"] = True
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_readiness_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("commit_allowed" in error for error in validation.errors)
    assert any("production_authorized" in error for error in validation.errors)
    assert any("external_effects_allowed" in error for error in validation.errors)


def test_validator_rejects_evidence_presence_without_new_gate(tmp_path: Path) -> None:
    gate = _load_gate()
    gate["required_evidence"][0]["present"] = True
    gate["required_evidence"][0]["evidence_ref"] = "proof://runtime/key-custody"
    gate["blocked_reasons"] = gate["blocked_reasons"][1:]
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_readiness_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.present" in error for error in validation.errors)
    assert any("blocked_reasons drift" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_required_evidence_reorder(tmp_path: Path) -> None:
    gate = _load_gate()
    evidence = gate["required_evidence"]
    gate["required_evidence"] = [evidence[1], evidence[0], *evidence[2:]]
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_readiness_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("required_evidence order drift" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def _load_gate() -> dict[str, Any]:
    return json.loads(DEFAULT_GATE.read_text(encoding="utf-8"))


def _write_gate(tmp_path: Path, gate: dict[str, Any]) -> Path:
    gate_path = tmp_path / "forge_live_runtime_readiness_gate.foundation.json"
    gate_path.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return gate_path
