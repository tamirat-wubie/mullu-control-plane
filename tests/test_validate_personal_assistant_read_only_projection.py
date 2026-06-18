"""Tests for personal-assistant read-only projection validation.

Purpose: prove redacted inbox/calendar projection evidence is schema-backed,
receipt-anchored, and unable to grant live connector, send, or mutation
authority.
Governance scope: PR4 read-only projection schema, private payload redaction,
receipt conformance, and Foundation Mode readiness boundaries.
Dependencies: scripts.validate_personal_assistant_read_only_projection.
Invariants:
  - Fixture and runtime envelopes validate.
  - Live connector execution, mailbox/calendar mutation, and sends remain false.
  - Raw private payloads and secret-like values are rejected.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_personal_assistant_read_only_projection import (
    DEFAULT_PROJECTION,
    build_runtime_read_only_projection,
    validate_personal_assistant_read_only_projection,
)


def test_personal_assistant_read_only_projection_fixture_validates() -> None:
    result = validate_personal_assistant_read_only_projection()

    assert result.valid is True
    assert result.projection_path == "examples/personal_assistant_read_only_projection.json"
    assert result.runtime_validated is True
    assert result.projection_count == 2
    assert result.receipt_count == 2
    assert result.assurance_outcome == "SolvedVerified"
    assert result.errors == ()


def test_runtime_read_only_projection_blocks_all_effect_boundaries() -> None:
    envelope = build_runtime_read_only_projection()
    effect_boundary = envelope["effect_boundary"]

    assert envelope["governed"] is True
    assert envelope["source_projection"] == "operator_supplied_redacted_projection"
    assert effect_boundary["execution_allowed"] is False
    assert effect_boundary["live_connector_execution_allowed"] is False
    assert effect_boundary["mailbox_read_allowed"] is False
    assert effect_boundary["mailbox_mutation_allowed"] is False
    assert effect_boundary["external_send_allowed"] is False
    assert effect_boundary["calendar_write_allowed"] is False
    assert effect_boundary["connector_mutation_allowed"] is False
    assert envelope["assurance"]["ready_for_live_execution"] is False
    assert envelope["assurance"]["ready_for_customer_readiness_claim"] is False


def test_read_only_projection_validator_rejects_execution_authority(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["effect_boundary"]["live_connector_execution_allowed"] = True
    payload["effect_boundary"]["external_send_allowed"] = True
    payload["metadata"]["system_of_record_write_allowed"] = True
    candidate = tmp_path / "unsafe_read_only_projection.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_read_only_projection(projection_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "effect_boundary.live_connector_execution_allowed must be false" in result.errors
    assert "effect_boundary.external_send_allowed must be false" in result.errors
    assert any("metadata.system_of_record_write_allowed" in error for error in result.errors)
    assert result.runtime_validated is False


def test_read_only_projection_validator_rejects_receipt_drift(tmp_path: Path) -> None:
    payload = _load_fixture()
    receipt = payload["projections"][0]["receipt"]
    receipt["actions_not_taken"] = []
    receipt["metadata"]["connector_mutation_allowed"] = True
    candidate = tmp_path / "receipt_drift_projection.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_read_only_projection(projection_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert any("actions_not_taken" in error for error in result.errors)
    assert "projections[0].receipt.metadata.connector_mutation_allowed must be false" in result.errors
    assert result.receipt_count == 2


def test_read_only_projection_validator_rejects_raw_payload_and_secret(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["projections"][0]["summary"]["top_items"][0]["raw_message"] = "private mailbox body"
    payload["projections"][1]["summary"]["events"][0]["title_digest"] = "rotate Bearer secret-worker-token"
    candidate = tmp_path / "raw_payload_projection.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_read_only_projection(projection_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "$.projections[0].summary.top_items[0].raw_message: raw private or secret field is forbidden" in result.errors
    assert "$.projections[1].summary.events[0].title_digest: secret-like value must not be serialized" in result.errors
    assert result.runtime_validated is False


def _load_fixture() -> dict[str, object]:
    return copy.deepcopy(json.loads(DEFAULT_PROJECTION.read_text(encoding="utf-8")))
