"""Tests for Component Harness evidence submission intake validation.

Purpose: prove submission intake remains queue-bound, observation-only, and
non-accepting.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_evidence_submission_intake and
foundation Component Harness fixtures.
Invariants: submitted refs are observations only and never imply acceptance,
authority, promotion, execution, or terminal closure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.app.component_evidence_request_queue import build_component_evidence_request_queue
from mcoi_runtime.app.component_evidence_submission_intake import (
    ComponentEvidenceSubmissionIntakeError,
    build_component_evidence_submission_intake,
)
from scripts.validate_component_evidence_submission_intake import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_evidence_submission_intake,
    write_component_evidence_submission_intake_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_evidence_submission_intake.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _intake_slots(payload: dict[str, object]) -> list[dict[str, object]]:
    slots = payload["intake_slots"]
    assert isinstance(slots, list)
    return slots


def test_component_evidence_submission_intake_schema_valid_and_write(tmp_path: Path) -> None:
    validation = validate_component_evidence_submission_intake()
    output_path = tmp_path / "component-evidence-submission-intake-validation.json"

    written_path = write_component_evidence_submission_intake_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.request_slot_count == 7
    assert validation.submitted_slot_count == 0
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "component_evidence_submission_intake_validation.json"


def test_component_evidence_submission_intake_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_evidence_submission_intake()

    assert example == projection
    assert example["intake_is_not_evidence_acceptance"] is True
    assert example["evidence_accepted"] is False
    assert example["authority_granted"] is False
    assert example["summary"]["request_slot_count"] == 7


def test_component_evidence_submission_intake_observes_submitted_refs_without_acceptance() -> None:
    queue = build_component_evidence_request_queue()
    request_id = queue["request_slots"][0]["request_id"]
    projection = build_component_evidence_submission_intake(
        evidence_request_queue=queue,
        submitted_evidence_by_request_id={request_id: ["operator_packet.gmail_account_binding_receipt.v1"]},
    )
    slot = projection["intake_slots"][0]

    assert projection["summary"]["submitted_slot_count"] == 1
    assert projection["summary"]["accepted_evidence_count"] == 0
    assert slot["submitted_evidence_observed"] is True
    assert slot["submission_state"] == "submitted_not_verified"
    assert slot["evidence_accepted"] is False
    assert slot["authority_granted"] is False
    assert slot["terminal_closure_allowed"] is False


def test_component_evidence_submission_intake_rejects_acceptance_and_closure_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["evidence_accepted"] = True
    payload["terminal_closure_allowed"] = True
    slot = _intake_slots(payload)[0]
    slot["accepted_evidence_refs"] = ["accepted.ref.v1"]
    slot["evidence_accepted"] = True
    slot["promotion_approved"] = True

    validation = validate_component_evidence_submission_intake(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evidence_accepted must be false" in serialized_errors
    assert "terminal_closure_allowed must be false" in serialized_errors
    assert "promotion_approved must be false" in serialized_errors


def test_component_evidence_submission_intake_runtime_rejects_unknown_request_id() -> None:
    with pytest.raises(ComponentEvidenceSubmissionIntakeError, match="unknown submitted request IDs"):
        build_component_evidence_submission_intake(
            submitted_evidence_by_request_id={"component_evidence_request_queue.unknown.v1": ["evidence.ref.v1"]},
        )


def test_component_evidence_submission_intake_runtime_rejects_unsafe_queue_source() -> None:
    queue = build_component_evidence_request_queue()
    queue["can_execute"] = True

    with pytest.raises(ComponentEvidenceSubmissionIntakeError, match="queue can_execute must be false"):
        build_component_evidence_submission_intake(evidence_request_queue=queue)
