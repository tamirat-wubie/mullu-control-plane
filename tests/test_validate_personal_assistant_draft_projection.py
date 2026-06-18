"""Tests for personal-assistant draft projection validation.

Purpose: prove email/calendar/task draft projection evidence is schema-backed,
receipt-anchored, and unable to grant send, invite, write, memory, connector,
or readiness authority.
Governance scope: PR5 draft-only projection schema, approval separation,
private payload redaction, receipt conformance, and Foundation Mode boundaries.
Dependencies: scripts.validate_personal_assistant_draft_projection.
Invariants:
  - Fixture and runtime envelopes validate.
  - Draft preparation does not become external execution authority.
  - Raw private payloads and secret-like values are rejected.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_personal_assistant_draft_projection import (
    DEFAULT_PROJECTION,
    build_runtime_draft_projection,
    validate_personal_assistant_draft_projection,
)


def test_personal_assistant_draft_projection_fixture_validates() -> None:
    result = validate_personal_assistant_draft_projection()

    assert result.valid is True
    assert result.projection_path == "examples/personal_assistant_draft_projection.json"
    assert result.runtime_validated is True
    assert result.draft_count == 3
    assert result.receipt_count == 3
    assert result.assurance_outcome == "SolvedVerified"
    assert result.errors == ()


def test_runtime_draft_projection_blocks_effect_boundaries() -> None:
    envelope = build_runtime_draft_projection()
    effect_boundary = envelope["effect_boundary"]
    approval_boundary = envelope["approval_boundary"]

    assert envelope["governed"] is True
    assert envelope["source_projection"] == "operator_supplied_redacted_projection"
    assert effect_boundary["draft_preparation_allowed"] is True
    assert effect_boundary["execution_allowed"] is False
    assert effect_boundary["live_connector_execution_allowed"] is False
    assert effect_boundary["external_send_allowed"] is False
    assert effect_boundary["calendar_write_allowed"] is False
    assert effect_boundary["task_write_allowed"] is False
    assert effect_boundary["memory_write_allowed"] is False
    assert effect_boundary["connector_mutation_allowed"] is False
    assert approval_boundary["risk_level"] == "P2"
    assert approval_boundary["approval_required_before_external_action"] is True
    assert envelope["assurance"]["ready_for_live_execution"] is False
    assert envelope["assurance"]["ready_for_customer_readiness_claim"] is False


def test_draft_projection_validator_rejects_execution_authority(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["effect_boundary"]["external_send_allowed"] = True
    payload["effect_boundary"]["calendar_write_allowed"] = True
    payload["effect_boundary"]["task_write_allowed"] = True
    payload["metadata"]["system_of_record_write_allowed"] = True
    candidate = tmp_path / "unsafe_draft_projection.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_draft_projection(projection_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "effect_boundary.external_send_allowed must be false" in result.errors
    assert "effect_boundary.calendar_write_allowed must be false" in result.errors
    assert "effect_boundary.task_write_allowed must be false" in result.errors
    assert any("metadata.system_of_record_write_allowed" in error for error in result.errors)
    assert result.runtime_validated is False


def test_draft_projection_validator_rejects_approval_boundary_drift(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["approval_boundary"]["approval_required_before_external_action"] = False
    payload["drafts"][0]["draft"]["approval_required_before_send"] = False
    payload["drafts"][1]["draft"]["effect_boundary"] = "draft_only_email_not_sent"
    candidate = tmp_path / "approval_drift_draft_projection.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_draft_projection(projection_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "approval_boundary.approval_required_before_external_action must be true" in result.errors
    assert "drafts[0].draft.approval_required_before_send must be true" in result.errors
    assert "drafts[1].draft.effect_boundary must be draft_only_event_not_created" in result.errors
    assert result.receipt_count == 3


def test_draft_projection_validator_rejects_receipt_drift(tmp_path: Path) -> None:
    payload = _load_fixture()
    receipt = payload["drafts"][2]["receipt"]
    receipt["actions_not_taken"] = []
    receipt["metadata"]["memory_write_allowed"] = True
    candidate = tmp_path / "receipt_drift_draft_projection.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_draft_projection(projection_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert any("actions_not_taken" in error for error in result.errors)
    assert "drafts[2].receipt.metadata.memory_write_allowed must be false" in result.errors
    assert result.receipt_count == 3


def test_draft_projection_validator_rejects_raw_payload_and_secret(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["drafts"][0]["draft"]["message_body"] = "private mailbox body"
    payload["drafts"][2]["draft"]["task_goal"] = "rotate Bearer secret-worker-token"
    candidate = tmp_path / "raw_payload_draft_projection.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_draft_projection(projection_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "$.drafts[0].draft.message_body: raw private or secret field is forbidden" in result.errors
    assert "$.drafts[2].draft.task_goal: secret-like value must not be serialized" in result.errors
    assert result.runtime_validated is False


def _load_fixture() -> dict[str, object]:
    return copy.deepcopy(json.loads(DEFAULT_PROJECTION.read_text(encoding="utf-8")))
