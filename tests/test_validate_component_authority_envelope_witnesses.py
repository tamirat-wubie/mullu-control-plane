"""Tests for Component Harness authority envelope witness validation.

Purpose: prove authority envelopes mirror registry authority while denying
live effects, promotions, and terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_authority_envelope_witnesses and
foundation Component Harness fixtures.
Invariants: every registered component has one authority witness, current
authority matches registry state, and live-effect flags remain false.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_component_authority_envelope_witnesses import (
    DEFAULT_OUTPUT,
    DEFAULT_WITNESSES,
    validate_component_authority_envelope_witnesses,
    write_component_authority_envelope_witness_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_WITNESSES.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    witness_path = tmp_path / "component_authority_envelope_witnesses.json"
    witness_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return witness_path


def _witnesses(payload: dict[str, object]) -> list[dict[str, object]]:
    witnesses = payload["authority_witnesses"]
    assert isinstance(witnesses, list)
    return witnesses


def test_component_authority_envelope_witnesses_validate_and_write(tmp_path: Path) -> None:
    validation = validate_component_authority_envelope_witnesses()
    output_path = tmp_path / "component-authority-envelope-witnesses-validation.json"

    written_path = write_component_authority_envelope_witness_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.witness_count == 10
    assert validation.component_count == 10
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "component_authority_envelope_witnesses_validation.json"


def test_component_authority_envelope_witnesses_reject_missing_component_witness(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["authority_witnesses"] = [
        witness for witness in _witnesses(payload) if witness.get("component_id") != "snet"
    ]

    validation = validate_component_authority_envelope_witnesses(witness_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert validation.witness_count == 9
    assert "registered components missing authority witnesses ['snet']" in serialized_errors


def test_component_authority_envelope_witnesses_reject_authority_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    first_witness = _witnesses(payload)[0]
    authority = first_witness["authority"]
    assert isinstance(authority, dict)
    authority["can_execute"] = True
    first_witness["witness_is_not_execution_authority"] = False
    first_witness["external_effect"] = True
    first_witness["blocked_actions"] = ["connector_call"]

    validation = validate_component_authority_envelope_witnesses(witness_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority.can_execute" in serialized_errors
    assert "authority must match registry authority" in serialized_errors
    assert "witness_is_not_execution_authority must be true" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_authority_envelope_witnesses_reject_state_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    witness = _witnesses(payload)[1]
    witness["authority_level"] = "approved_live_action"
    witness["authority_matches_registry"] = False

    validation = validate_component_authority_envelope_witnesses(witness_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_level must match registry" in serialized_errors
    assert "authority_matches_registry must be true" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_component_authority_envelope_witnesses_reject_missing_evidence(tmp_path: Path) -> None:
    payload = _default_payload()
    witness = _witnesses(payload)[2]
    witness["evidence_refs"] = ["docs/missing-component-authority-evidence.md"]

    validation = validate_component_authority_envelope_witnesses(witness_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evidence_ref missing on disk" in serialized_errors
    assert "docs/missing-component-authority-evidence.md" in serialized_errors
