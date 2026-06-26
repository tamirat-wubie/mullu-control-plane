"""Tests for personal-assistant approval decision runtime envelopes.

Purpose: prove runtime approval decision evidence is schema-backed, receipt
anchored, and unable to execute personal-assistant actions.
Governance scope: PR6 approval decision evidence, queue precondition binding,
approval separation, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant approval decision builders and
schema validation helpers.
Invariants:
  - Runtime envelope output validates against approval decision semantics.
  - Approval, packet, receipt, and queue precondition identities remain aligned.
  - Duplicate decisions, receipt drift, raw private fields, and secret-like
    values are rejected before envelope emission.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

import pytest

from mcoi_runtime.personal_assistant import (
    ApprovalDecision,
    ApprovalProposedAction,
    ApprovalScope,
    PersonalAssistantApprovalQueue,
    PersonalAssistantInvariantError,
    build_default_personal_assistant_approval_decision_evidence,
    build_personal_assistant_approval_decision_evidence_envelope,
)
from scripts.validate_personal_assistant_approval_decision import _validate_decision_semantics
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
DECISION_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_approval_decision.schema.json"
APPROVAL_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_approval.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_approval_decision_envelope_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_approval_decision_evidence()
    decision_schema = _load_schema(DECISION_SCHEMA_PATH)
    approval_schema = _load_schema(APPROVAL_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    decisions = {item["decision"]: item for item in envelope["decisions"]}

    assert _validate_schema_instance(decision_schema, envelope) == []
    assert _validate_decision_semantics(envelope, approval_schema, receipt_schema) == ()
    assert envelope["decision_count"] == 4
    assert sorted(decisions) == ["approved", "expired", "rejected", "revised"]
    assert envelope["effect_boundary"]["approval_decision_records_allowed"] is True
    assert envelope["effect_boundary"]["execution_allowed"] is False
    assert envelope["effect_boundary"]["external_send_allowed"] is False
    assert envelope["metadata"]["system_of_record_write_allowed"] is False
    assert decisions["approved"]["receipt"]["decision"] == "deferred"
    assert decisions["revised"]["receipt"]["decision"] == "deferred"
    assert decisions["rejected"]["receipt"]["decision"] == "blocked"
    assert decisions["expired"]["receipt"]["decision"] == "blocked"


def test_runtime_approval_decision_envelope_rejects_empty_and_duplicate_decisions() -> None:
    decision_records = _decision_records()

    with pytest.raises(PersonalAssistantInvariantError) as empty_exc:
        build_personal_assistant_approval_decision_evidence_envelope(
            generated_at="2026-06-14T00:03:00+00:00",
            decision_records=(),
        )
    with pytest.raises(PersonalAssistantInvariantError) as duplicate_exc:
        build_personal_assistant_approval_decision_evidence_envelope(
            generated_at="2026-06-14T00:03:00+00:00",
            decision_records=(decision_records[0], decision_records[0]),
        )

    assert "at least one" in str(empty_exc.value)
    assert "duplicate decision_id" in str(duplicate_exc.value)
    assert "pa_approval_decision_approved_001" in str(duplicate_exc.value)


def test_runtime_approval_decision_envelope_rejects_receipt_drift() -> None:
    decision_records = list(_decision_records())
    decision_id, source_record, record = copy.deepcopy(decision_records[0])
    record["receipts"][-1]["decision"] = "allowed"
    decision_records[0] = (decision_id, source_record, record)

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_approval_decision_evidence_envelope(
            generated_at="2026-06-14T00:03:00+00:00",
            decision_records=tuple(decision_records),
        )

    assert "receipt.decision must be deferred for approved" in str(exc_info.value)
    assert "pa_approval_decision_approved_001" in str(exc_info.value)
    assert "private mailbox" not in str(exc_info.value)


def test_runtime_approval_decision_envelope_rejects_raw_private_fields_and_secret_values() -> None:
    raw_records = list(_decision_records())
    secret_records = list(_decision_records())
    raw_decision_id, raw_source, raw_record = copy.deepcopy(raw_records[0])
    secret_decision_id, secret_source, secret_record = copy.deepcopy(secret_records[1])
    raw_record["packet"]["raw_connector_payload"] = {"message_body": "private mailbox body"}
    secret_record["packet"]["decision_record"]["reason_codes"] = ["rotate Bearer secret-worker-token"]
    raw_records[0] = (raw_decision_id, raw_source, raw_record)
    secret_records[1] = (secret_decision_id, secret_source, secret_record)

    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        build_personal_assistant_approval_decision_evidence_envelope(
            generated_at="2026-06-14T00:03:00+00:00",
            decision_records=tuple(raw_records),
        )
    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_approval_decision_evidence_envelope(
            generated_at="2026-06-14T00:03:00+00:00",
            decision_records=tuple(secret_records),
        )

    assert "raw private or secret field is forbidden" in str(raw_exc.value)
    assert "secret-like values" in str(secret_exc.value)
    assert "private mailbox body" not in str(raw_exc.value)


def _decision_records() -> tuple[tuple[str, Mapping[str, Any], Mapping[str, Any]], ...]:
    records: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
    for index, decision in enumerate(("approved", "rejected", "revised", "expired"), start=1):
        queue = PersonalAssistantApprovalQueue()
        approval_id = f"pa_approval_decision_{decision}_{index:03d}"
        record = queue.enqueue(
            request_id=f"pa_request_decision_{decision}_{index:03d}",
            plan_id=f"pa_plan_decision_{decision}_{index:03d}",
            approver_ref="operator:tamirat",
            approval_scope=ApprovalScope.PER_RECIPIENT,
            proposed_actions=(
                ApprovalProposedAction(
                    action_id="send_prepared_email_draft",
                    skill_id="email.send.with_approval",
                    risk_level="P4",
                    effect_boundary="external_email_send",
                    summary="Send one approved email draft to one named recipient.",
                ),
            ),
            forbidden_without_approval=("send", "forward", "recipient_unapproved", "connector_mutation"),
            evidence_refs=(f"proof://personal-assistant/approval/{decision}-{index:03d}",),
            created_at="2026-06-14T00:00:00+00:00",
            approval_id=approval_id,
        )
        updated = queue.record_decision(
            record.approval_id,
            decision=ApprovalDecision.coerce(decision),
            reason_codes=(f"operator_{decision}_preview",),
            decided_at="2026-06-14T00:03:00+00:00",
            decision_evidence_ref=f"proof://personal-assistant/approval/operator-{decision}-{index:03d}",
            revision_request="Revise the draft before any future approval." if decision == "revised" else "",
        )
        records.append((f"pa_approval_decision_{decision}_{index:03d}", record.as_dict(), updated.as_dict()))
    return tuple(records)
