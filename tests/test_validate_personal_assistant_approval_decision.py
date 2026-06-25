"""Tests for personal-assistant approval decision evidence validation.

Purpose: prove approve/reject/revise/expire decision evidence is schema-backed,
receipt-anchored, and unable to execute personal-assistant actions.
Governance scope: PR6 approval decision evidence, expiration handling, approval
separation, receipt conformance, private payload redaction, and Foundation Mode
boundaries.
Dependencies: scripts.validate_personal_assistant_approval_decision.
Invariants:
  - Fixture and runtime envelopes validate.
  - Approval decisions do not send, mutate connectors, write memory, or write systems of record.
  - Expired approvals are terminal evidence and block execution.
  - Raw private payloads and secret-like values are rejected.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from mcoi_runtime.personal_assistant import ApprovalDecision, PersonalAssistantApprovalQueue
from scripts.validate_personal_assistant_approval_decision import (
    DEFAULT_DECISION,
    build_runtime_approval_decision_evidence,
    validate_personal_assistant_approval_decision,
)


def test_personal_assistant_approval_decision_fixture_validates() -> None:
    result = validate_personal_assistant_approval_decision()

    assert result.valid is True
    assert result.decision_path == "examples/personal_assistant_approval_decision_evidence.json"
    assert result.runtime_validated is True
    assert result.decision_count == 4
    assert result.receipt_count == 4
    assert result.assurance_outcome == "SolvedVerified"
    assert result.errors == ()


def test_runtime_approval_decision_blocks_effect_boundaries() -> None:
    envelope = build_runtime_approval_decision_evidence()
    effect_boundary = envelope["effect_boundary"]
    decisions = {item["decision"]: item for item in envelope["decisions"]}

    assert envelope["governed"] is True
    assert envelope["source_projection"] == "operator_supplied_decision_evidence"
    assert effect_boundary["approval_decision_records_allowed"] is True
    assert effect_boundary["execution_allowed"] is False
    assert effect_boundary["approval_is_execution"] is False
    assert effect_boundary["external_send_allowed"] is False
    assert effect_boundary["connector_mutation_allowed"] is False
    assert effect_boundary["memory_write_allowed"] is False
    assert effect_boundary["system_of_record_write_allowed"] is False
    assert decisions["approved"]["receipt"]["decision"] == "deferred"
    assert decisions["revised"]["receipt"]["decision"] == "deferred"
    assert decisions["rejected"]["receipt"]["decision"] == "blocked"
    assert decisions["expired"]["receipt"]["decision"] == "blocked"
    for decision in decisions.values():
        queue_ref = decision["queue_precondition_ref"]
        assert queue_ref["source_projection"] == "personal_assistant_approval_queue_read_model"
        assert queue_ref["approval_id"] == decision["approval_id"]
        assert queue_ref["source_queue_state"] == "requested"
        assert queue_ref["source_receipt_id"].endswith("_request")
        assert queue_ref["source_receipt_id"] != decision["receipt"]["receipt_id"]
        assert queue_ref["payload_digest_only"] is True
        assert queue_ref["decision_precondition_met"] is True
        assert queue_ref["execution_allowed"] is False
        assert queue_ref["approval_is_execution"] is False
        assert queue_ref["connector_mutation_allowed"] is False
        assert queue_ref["system_of_record_write_allowed"] is False


def test_approval_queue_expired_decision_records_receipt_without_execution() -> None:
    envelope = build_runtime_approval_decision_evidence()
    expired = next(item for item in envelope["decisions"] if item["decision"] == "expired")
    receipt = expired["receipt"]
    packet = expired["packet"]

    assert ApprovalDecision.coerce("expired") is ApprovalDecision.EXPIRED
    assert packet["approval_state"] == "expired"
    assert packet["decision_record"]["decision"] == "expired"
    assert receipt["decision"] == "blocked"
    assert "approval_expiration_recorded" in receipt["actions_taken"]
    assert "external_message_not_sent" in receipt["actions_not_taken"]
    assert receipt["metadata"]["approval_is_execution"] is False
    assert receipt["metadata"]["connector_mutation_allowed"] is False


def test_approval_queue_read_model_counts_expired_decisions() -> None:
    queue = PersonalAssistantApprovalQueue()
    record = queue.enqueue(
        request_id="pa_request_expired_queue_001",
        plan_id="pa_plan_expired_queue_001",
        approver_ref="operator:tamirat",
        approval_scope="per_recipient",
        proposed_actions=(
            {
                "action_id": "send_prepared_email_draft",
                "skill_id": "email.send.with_approval",
                "risk_level": "P4",
                "effect_boundary": "external_email_send",
                "summary": "Send one approved email draft to one named recipient.",
            },
        ),
        forbidden_without_approval=("send", "connector_mutation"),
        evidence_refs=("proof://personal-assistant/approval/expired-queue-001",),
        created_at="2026-06-14T00:00:00+00:00",
    )
    queue.record_decision(
        record.approval_id,
        decision="expired",
        reason_codes=("approval_window_elapsed",),
        decided_at="2026-06-14T00:03:00+00:00",
    )
    read_model = queue.read_model()

    assert read_model["state_counts"]["requested"] == 0
    assert read_model["state_counts"]["expired"] == 1
    assert read_model["execution_allowed"] is False
    assert read_model["approval_is_execution"] is False
    assert read_model["metadata"]["approval_decision_executes_action"] is False


def test_approval_decision_validator_rejects_execution_authority(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["effect_boundary"]["external_send_allowed"] = True
    payload["effect_boundary"]["connector_mutation_allowed"] = True
    payload["metadata"]["system_of_record_write_allowed"] = True
    candidate = tmp_path / "unsafe_approval_decision.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_approval_decision(decision_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "effect_boundary.external_send_allowed must be false" in result.errors
    assert "effect_boundary.connector_mutation_allowed must be false" in result.errors
    assert any("metadata.system_of_record_write_allowed" in error for error in result.errors)
    assert result.runtime_validated is False


def test_approval_decision_validator_rejects_receipt_drift(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["decisions"][0]["receipt"]["decision"] = "allowed"
    payload["decisions"][0]["receipt"]["metadata"]["approval_is_execution"] = True
    payload["decisions"][3]["receipt"]["decision"] = "deferred"
    candidate = tmp_path / "receipt_drift_approval_decision.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_approval_decision(decision_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "decisions[0].receipt.decision must be deferred for approved" in result.errors
    assert "decisions[0].receipt.metadata.approval_is_execution must be false" in result.errors
    assert "decisions[3].receipt.decision must be blocked for expired" in result.errors
    assert result.receipt_count == 4


def test_approval_decision_validator_rejects_queue_precondition_drift(tmp_path: Path) -> None:
    payload = _load_fixture()
    queue_ref = payload["decisions"][0]["queue_precondition_ref"]
    queue_ref["source_queue_state"] = "approved"
    queue_ref["source_receipt_id"] = payload["decisions"][0]["receipt"]["receipt_id"]
    queue_ref["source_review_packet_sha256"] = "0" * 64
    queue_ref["payload_digest_only"] = False
    queue_ref["execution_allowed"] = True
    candidate = tmp_path / "queue_precondition_drift_approval_decision.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_approval_decision(decision_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert (
        "decisions[0].queue_precondition_ref.source_queue_state must be requested"
        in result.errors
    )
    assert (
        "decisions[0].queue_precondition_ref.source_receipt_id must differ from decision receipt"
        in result.errors
    )
    assert (
        "decisions[0].queue_precondition_ref.source_review_packet_sha256 does not match approval review packet"
        in result.errors
    )
    assert "decisions[0].queue_precondition_ref.payload_digest_only must be true" in result.errors
    assert "decisions[0].queue_precondition_ref.execution_allowed must be false" in result.errors
    assert (
        "decisions[0].queue_precondition_ref.queue_precondition_sha256 does not match queue precondition fields"
        in result.errors
    )


def test_approval_decision_validator_rejects_missing_decision_state(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["decisions"] = [item for item in payload["decisions"] if item["decision"] != "expired"]
    payload["decision_ids"] = [item["decision_id"] for item in payload["decisions"]]
    payload["approval_ids"] = [item["approval_id"] for item in payload["decisions"]]
    payload["receipt_ids"] = [item["receipt"]["receipt_id"] for item in payload["decisions"]]
    payload["decision_count"] = len(payload["decisions"])
    candidate = tmp_path / "missing_expired_approval_decision.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_approval_decision(decision_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "decisions must include expired" in result.errors
    assert result.decision_count == 3


def test_approval_decision_validator_rejects_raw_payload_and_secret(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["decisions"][0]["packet"]["raw_connector_payload"] = {"message_body": "private"}
    payload["decisions"][1]["packet"]["decision_record"]["reason_codes"] = ["rotate Bearer secret-worker-token"]
    candidate = tmp_path / "raw_payload_approval_decision.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_approval_decision(decision_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "$.decisions[0].packet.raw_connector_payload: raw private or secret field is forbidden" in result.errors
    assert "$.decisions[1].packet.decision_record.reason_codes[0]: secret-like value must not be serialized" in result.errors
    assert result.runtime_validated is False


def _load_fixture() -> dict[str, object]:
    return copy.deepcopy(json.loads(DEFAULT_DECISION.read_text(encoding="utf-8")))
