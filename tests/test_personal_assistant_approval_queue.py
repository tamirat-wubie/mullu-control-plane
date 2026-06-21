"""Tests for the personal-assistant approval queue foundation.

Purpose: prove PR6 approval packets and decisions are recorded as governed
evidence without executing proposed effect-bearing actions.
Governance scope: P4 approval packets, approve/reject/revise decisions,
receipt emission, explicit approval evidence, and private payload denial.
Dependencies: mcoi_runtime.personal_assistant approval queue helpers.
Invariants:
  - Approval queue records evidence only and does not send or mutate state.
  - Approved packets still require a future execution gate.
  - Receipts record actions taken and actions not taken.
  - Raw private payloads and secret-like values are rejected.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    ApprovalDecision,
    ApprovalProposedAction,
    ApprovalScope,
    GovernedIntent,
    PersonalAssistantApprovalQueue,
    PersonalAssistantInvariantError,
    RequestExecutionMode,
    RequestInterface,
    SkillRiskLevel,
    build_personal_assistant_preview_plan,
    interpret_user_request,
    prepare_approval_proposal_from_plan,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload
from scripts.validate_personal_assistant_approval_queue import (
    DEFAULT_QUEUE,
    validate_personal_assistant_approval_queue,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
APPROVAL_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_approval.schema.json"
APPROVAL_REVIEW_PACKET_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_approval_review_packet.schema.json"
APPROVAL_QUEUE_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_approval_queue.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"
CREATED_AT = "2026-06-14T00:00:00+00:00"
DECIDED_AT = "2026-06-14T00:03:00+00:00"


def test_approval_queue_enqueues_p4_packet_without_execution() -> None:
    queue = PersonalAssistantApprovalQueue()
    record = _enqueue_email_send(queue)
    packet = dict(record.packet)
    receipt = dict(record.latest_receipt)
    serialized = json.dumps(record.as_dict(), sort_keys=True)

    assert _validate_schema_instance(_load_schema(APPROVAL_SCHEMA_PATH), packet) == []
    assert _validate_schema_instance(_load_schema(RECEIPT_SCHEMA_PATH), receipt) == []
    assert validate_personal_assistant_receipt_payload(receipt) == ()
    assert packet["approval_state"] == "requested"
    assert packet["explicit_approval_required"] is True
    assert record.as_dict()["review_packet_ref"]["source_ref"] == "examples/personal_assistant_approval_review_packet.json"
    assert record.as_dict()["review_packet_ref"]["payload_digest_only"] is True
    assert record.as_dict()["review_packet_ref"]["execution_allowed"] is False
    assert receipt["decision"] == "approval_required"
    assert receipt["approval_required"] is True
    assert "proposed_action_not_executed" in receipt["actions_not_taken"]
    assert queue.read_model()["execution_allowed"] is False
    assert "raw_connector_payload" not in serialized


def test_approval_queue_read_model_matches_schema_and_denies_execution() -> None:
    queue = PersonalAssistantApprovalQueue()
    record = _enqueue_email_send(queue)
    read_model = queue.read_model()

    assert _validate_schema_instance(_load_schema(APPROVAL_QUEUE_SCHEMA_PATH), read_model) == []
    assert read_model["approval_count"] == 1
    assert read_model["approval_ids"] == [record.approval_id]
    assert read_model["receipt_ids"] == [record.latest_receipt["receipt_id"]]
    assert read_model["execution_allowed"] is False
    assert read_model["live_connector_execution_allowed"] is False
    assert read_model["external_send_allowed"] is False
    assert read_model["connector_mutation_allowed"] is False
    assert read_model["approval_is_execution"] is False
    assert read_model["metadata"]["approval_decision_executes_action"] is False
    workflow = read_model["workflow_v0"]
    workflow_item = workflow["items"][0]
    assert workflow["workflow_id"] == "personal_assistant_approval_queue_v0"
    assert workflow["stage_order"] == [
        "draft_action",
        "risk_class",
        "requested_approval",
        "operator_decision",
        "receipt",
    ]
    assert workflow["decision_controls"] == ["approve", "reject", "revise"]
    assert workflow["draft_action_count"] == 1
    assert workflow["requested_approval_count"] == 1
    assert workflow["pending_decision_count"] == 1
    assert workflow["terminal_decision_count"] == 0
    assert workflow["receipt_count"] == 1
    assert workflow["approval_decision_executes_action"] is False
    assert workflow["execution_allowed"] is False
    assert workflow_item["draft_actions"][0]["action_id"] == "send_prepared_email_draft"
    assert workflow_item["review_packet_ref"] == read_model["records"][0]["review_packet_ref"]
    assert workflow_item["review_packet_ref"]["review_packet_id"] == "pa_approval_review_approval_review_packet_001"
    assert workflow_item["review_packet_ref"]["approval_enqueued"] is False
    assert workflow_item["risk_class"]["risk_level"] == "P4"
    assert workflow_item["requested_approval"]["approval_state"] == "requested"
    assert workflow_item["decision"]["current_decision"] == "pending"
    assert workflow_item["decision"]["approval_is_execution"] is False
    assert workflow_item["receipt"]["latest_receipt_id"] == record.latest_receipt["receipt_id"]
    assert workflow_item["effect_boundary"]["external_send_allowed"] is False


def test_approved_decision_links_evidence_and_still_defers_execution() -> None:
    queue = PersonalAssistantApprovalQueue()
    record = _enqueue_email_send(queue)
    updated = queue.record_decision(
        record.approval_id,
        decision=ApprovalDecision.APPROVED,
        reason_codes=("operator_explicitly_approved_named_recipient",),
        decided_at=DECIDED_AT,
        decision_evidence_ref="proof://personal-assistant/approval/operator-click-001",
    )
    packet = dict(updated.packet)
    receipt = dict(updated.latest_receipt)

    assert _validate_schema_instance(_load_schema(APPROVAL_SCHEMA_PATH), packet) == []
    assert _validate_schema_instance(_load_schema(RECEIPT_SCHEMA_PATH), receipt) == []
    assert validate_personal_assistant_receipt_payload(receipt) == ()
    assert packet["approval_state"] == "approved"
    assert packet["decision_record"]["decision"] == "approved"
    assert "proof://personal-assistant/approval/operator-click-001" in packet["evidence_refs"]
    assert receipt["decision"] == "deferred"
    assert receipt["approval_ref"] == record.approval_id
    assert "approval_decision_recorded" in receipt["actions_taken"]
    assert "external_message_not_sent" in receipt["actions_not_taken"]
    assert receipt["metadata"]["approval_is_execution"] is False
    workflow = queue.read_model()["workflow_v0"]
    assert workflow["pending_decision_count"] == 0
    assert workflow["terminal_decision_count"] == 1
    assert workflow["receipt_count"] == 2
    assert workflow["items"][0]["decision"]["current_decision"] == "approved"
    assert workflow["items"][0]["receipt"]["latest_receipt_decision"] == "deferred"
    assert workflow["items"][0]["effect_boundary"]["approval_decision_executes_action"] is False


def test_reject_and_revise_decisions_record_reason_without_execution() -> None:
    rejected_queue = PersonalAssistantApprovalQueue()
    rejected = _enqueue_email_send(rejected_queue, approval_id="pa_approval_reject_email_001")
    rejected_update = rejected_queue.record_decision(
        rejected.approval_id,
        decision="rejected",
        reason_codes=("recipient_not_confirmed",),
        decided_at=DECIDED_AT,
    )
    revised_queue = PersonalAssistantApprovalQueue()
    revised = _enqueue_email_send(revised_queue, approval_id="pa_approval_revise_email_001")
    revised_update = revised_queue.record_decision(
        revised.approval_id,
        decision=ApprovalDecision.REVISED,
        reason_codes=("body_needs_operator_revision",),
        decided_at=DECIDED_AT,
        revision_request="Revise the draft to remove deployment readiness wording.",
    )

    assert rejected_update.packet["approval_state"] == "rejected"
    assert rejected_update.latest_receipt["decision"] == "blocked"
    assert "approval_rejection_recorded" in rejected_update.latest_receipt["actions_taken"]
    assert "connector_state_not_mutated" in rejected_update.latest_receipt["actions_not_taken"]
    assert revised_update.packet["approval_state"] == "revised"
    assert revised_update.latest_receipt["decision"] == "deferred"
    assert revised_update.packet["metadata"]["revision_request"].startswith("Revise the draft")
    assert "approval_revision_requested" in revised_update.latest_receipt["actions_taken"]
    assert revised_queue.read_model()["state_counts"]["revised"] == 1
    rejected_workflow = rejected_queue.read_model()["workflow_v0"]
    revised_workflow = revised_queue.read_model()["workflow_v0"]
    assert rejected_workflow["items"][0]["decision"]["current_decision"] == "rejected"
    assert rejected_workflow["items"][0]["receipt"]["latest_receipt_decision"] == "blocked"
    assert revised_workflow["items"][0]["decision"]["current_decision"] == "revised"
    assert revised_workflow["items"][0]["decision"]["revision_request"].startswith("Revise the draft")
    assert revised_workflow["items"][0]["receipt"]["latest_receipt_decision"] == "deferred"


def test_approval_queue_rejects_non_approval_skill_and_duplicate_decisions() -> None:
    queue = PersonalAssistantApprovalQueue()
    record = _enqueue_email_send(queue)
    queue.record_decision(
        record.approval_id,
        decision="approved",
        reason_codes=("operator_explicitly_approved_named_recipient",),
        decided_at=DECIDED_AT,
        decision_evidence_ref="proof://personal-assistant/approval/operator-click-002",
    )

    with pytest.raises(PersonalAssistantInvariantError) as non_approval_exc:
        queue.enqueue(
            request_id="pa_request_draft_only_queue_001",
            plan_id="pa_plan_draft_only_queue_001",
            approver_ref="operator:tamirat",
            approval_scope=ApprovalScope.PER_ACTION,
            proposed_actions=(
                ApprovalProposedAction(
                    action_id="draft_email_response",
                    skill_id="email.response.draft",
                    risk_level="P2",
                    effect_boundary="draft_only_no_send",
                    summary="Prepare a draft-only email response.",
                ),
            ),
            forbidden_without_approval=("send",),
            evidence_refs=("proof://personal-assistant/approval/draft-only-001",),
            created_at=CREATED_AT,
        )

    with pytest.raises(PersonalAssistantInvariantError) as duplicate_exc:
        queue.record_decision(
            record.approval_id,
            decision="rejected",
            reason_codes=("second_decision_not_allowed",),
            decided_at=DECIDED_AT,
        )

    assert "does not require approval" in str(non_approval_exc.value)
    assert "already recorded" in str(duplicate_exc.value)
    assert queue.read_model()["state_counts"]["approved"] == 1


def test_approval_queue_rejects_raw_payload_fields_and_secret_like_values() -> None:
    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        ApprovalProposedAction.from_mapping(
            {
                "action_id": "send_prepared_email_draft",
                "skill_id": "email.send.with_approval",
                "risk_level": "P4",
                "effect_boundary": "external_email_send",
                "summary": "Send one prepared draft.",
                "raw_connector_payload": {"message_body": "private"},
            }
        )

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        ApprovalProposedAction(
            action_id="send_prepared_email_draft",
            skill_id="email.send.with_approval",
            risk_level="P4",
            effect_boundary="external_email_send",
            summary="Use Bearer secret-token-value as proof.",
        )

    assert "raw_connector_payload" in str(raw_exc.value)
    assert "secret-like values" in str(secret_exc.value)
    assert "message_body" not in str(raw_exc.value)


def test_approval_queue_fixture_validates_workflow_v0() -> None:
    result = validate_personal_assistant_approval_queue()

    assert result.valid is True
    assert result.queue_path == "examples/personal_assistant_approval_queue_read_model.json"
    assert result.approval_count == 1
    assert result.receipt_count == 1
    assert result.errors == ()


def test_approval_queue_validator_rejects_workflow_authority_drift(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_QUEUE.read_text(encoding="utf-8"))
    payload["workflow_v0"]["approval_decision_executes_action"] = True
    payload["workflow_v0"]["items"][0]["decision"]["approval_is_execution"] = True
    payload["workflow_v0"]["items"][0]["effect_boundary"]["external_send_allowed"] = True
    payload["workflow_v0"]["items"][0]["receipt"]["latest_receipt_id"] = "pa_receipt_forged"
    candidate = tmp_path / "unsafe_approval_queue.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_approval_queue(queue_path=candidate)

    assert result.valid is False
    assert "workflow_v0.approval_decision_executes_action must be false" in result.errors
    assert "workflow_v0.items[0].decision.approval_is_execution must be false" in result.errors
    assert "workflow_v0.items[0].effect_boundary.external_send_allowed must be false" in result.errors
    assert "workflow_v0.items[0].receipt.latest_receipt_id must match latest receipt" in result.errors


def test_approval_queue_validator_rejects_review_packet_ref_drift(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_QUEUE.read_text(encoding="utf-8"))
    payload["records"][0]["review_packet_ref"]["source_sha256"] = "0" * 64
    payload["records"][0]["review_packet_ref"]["payload_digest_only"] = False
    payload["records"][0]["review_packet_ref"]["execution_allowed"] = True
    payload["workflow_v0"]["items"][0]["review_packet_ref"]["review_packet_id"] = "pa_approval_review_drifted"
    candidate = tmp_path / "review_drift_approval_queue.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_approval_queue(queue_path=candidate)

    assert result.valid is False
    assert "records[0].review_packet_ref.source_sha256 does not match approval review packet" in result.errors
    assert "records[0].review_packet_ref.payload_digest_only must be true" in result.errors
    assert "records[0].review_packet_ref.execution_allowed must be false" in result.errors
    assert "workflow_v0.items[0].review_packet_ref must match record review_packet_ref" in result.errors


def test_approval_proposal_from_p4_plan_can_enqueue_without_execution() -> None:
    intent = GovernedIntent(
        request_id="pa_request_approval_proposal_p4_001",
        submitted_at=CREATED_AT,
        interface=RequestInterface.OPERATOR_CONSOLE,
        user_goal="Send one approved email draft to Daniel.",
        requested_capabilities=("email.send.with_approval",),
        requested_skill_ids=("email.send.with_approval",),
        risk_level=SkillRiskLevel.P4,
        requires_approval=True,
        execution_mode=RequestExecutionMode.EXECUTE_WITH_APPROVAL,
        approval_scope=ApprovalScope.PER_RECIPIENT,
        blocked_actions=("send", "forward", "connector_mutation"),
        evidence_refs=("proof://personal-assistant/request/approval-proposal-p4-001",),
    )
    envelope = build_personal_assistant_preview_plan(
        intent,
        plan_id="pa_plan_approval_proposal_p4_001",
        created_at=CREATED_AT,
    )
    proposal = prepare_approval_proposal_from_plan(
        envelope.plan,
        approval_scope=ApprovalScope.PER_RECIPIENT,
    )
    review_packet = proposal.as_review_packet(
        generated_at=CREATED_AT,
        reviewer_ref="operator:tamirat",
    )
    queue = PersonalAssistantApprovalQueue()
    record = queue.enqueue(
        **proposal.as_enqueue_kwargs(
            approver_ref="operator:tamirat",
            created_at=CREATED_AT,
        )
    )

    assert _validate_schema_instance(_load_schema(APPROVAL_REVIEW_PACKET_SCHEMA_PATH), review_packet) == []
    assert review_packet["review_state"] == "preview_only"
    assert review_packet["effect_boundary"]["execution_allowed"] is False
    assert review_packet["effect_boundary"]["approval_enqueued"] is False
    assert len(review_packet["source_closure_refs"]) == 2
    assert review_packet["source_closure_refs"][0]["source_kind"] == "dry_run_packet"
    assert review_packet["metadata"]["source_closure_binding"] == "digest_verified_closed_packets"
    assert review_packet["metadata"]["source_payloads_serialized"] is False
    assert "confirm_external_recipient_or_target_scope" in review_packet["required_operator_checks"]
    assert {denial["authority"] for denial in review_packet["authority_denials"]} >= {
        "execution",
        "approval_enqueue",
        "connector_mutation",
        "memory_write",
        "external_send",
    }
    assert proposal.execution_allowed is False
    assert proposal.approval_matrix_ref == "personal_assistant_approval_matrix.foundation.v1"
    assert proposal.risk_level is SkillRiskLevel.P4
    assert proposal.proposed_actions[0].skill_id == "email.send.with_approval"
    assert "send" in proposal.forbidden_without_approval
    assert "connector_mutation" in proposal.forbidden_without_approval
    assert record.packet["approval_state"] == "requested"
    assert record.packet["metadata"]["approval_matrix_ref"] == proposal.approval_matrix_ref
    assert record.latest_receipt["metadata"]["approval_is_execution"] is False
    assert queue.read_model()["execution_allowed"] is False


def test_approval_proposal_from_p5_plan_remains_blocked_and_enqueueable() -> None:
    intent = GovernedIntent(
        request_id="pa_request_approval_proposal_p5_001",
        submitted_at=CREATED_AT,
        interface=RequestInterface.OPERATOR_CONSOLE,
        user_goal="Review deployment publication readiness without deploying.",
        requested_capabilities=("deployment.publish.review",),
        requested_skill_ids=("deployment.publish.review",),
        risk_level=SkillRiskLevel.P5,
        requires_approval=True,
        execution_mode=RequestExecutionMode.EXECUTE_WITH_APPROVAL,
        approval_scope=ApprovalScope.PER_PLAN,
        blocked_actions=("deploy_service", "publish", "live_nested_mind_activation"),
        evidence_refs=("proof://personal-assistant/request/approval-proposal-p5-001",),
    )
    envelope = build_personal_assistant_preview_plan(
        intent,
        plan_id="pa_plan_approval_proposal_p5_001",
        created_at=CREATED_AT,
    )
    proposal = prepare_approval_proposal_from_plan(envelope.plan)
    review_packet = proposal.as_review_packet(
        generated_at=CREATED_AT,
        reviewer_ref="operator:tamirat",
    )
    queue = PersonalAssistantApprovalQueue()
    record = queue.enqueue(
        **proposal.as_enqueue_kwargs(
            approver_ref="operator:tamirat",
            created_at=CREATED_AT,
        )
    )

    assert envelope.plan["mode"] == "blocked"
    assert proposal.risk_level is SkillRiskLevel.P5
    assert _validate_schema_instance(_load_schema(APPROVAL_REVIEW_PACKET_SCHEMA_PATH), review_packet) == []
    assert review_packet["source_closure_refs"][1]["source_kind"] == "foundation_closure_packet"
    assert review_packet["metadata"]["all_source_closure_refs_closed"] is True
    assert review_packet["metadata"]["source_payloads_serialized"] is False
    assert "confirm_money_legal_public_deployment_boundary_blocked" in review_packet["required_operator_checks"]
    assert {denial["authority"] for denial in review_packet["authority_denials"]} >= {
        "money_legal_public_action",
        "deployment_mutation",
    }
    assert proposal.proposed_actions[0].skill_id == "deployment.publish.review"
    assert "deploy_service" in proposal.forbidden_without_approval
    assert "publish" in proposal.forbidden_without_approval
    assert "live_nested_mind_activation" in proposal.forbidden_without_approval
    assert record.packet["risk_level"] == "P5"
    assert record.latest_receipt["metadata"]["money_legal_public_action_allowed"] is False
    assert record.latest_receipt["metadata"]["live_connector_execution_allowed"] is False


def test_approval_proposal_rejects_non_approval_plan() -> None:
    intent = interpret_user_request(
        "Check important inbox items and prepare response drafts only.",
        request_id="pa_request_approval_proposal_read_only_001",
        submitted_at=CREATED_AT,
    )
    envelope = build_personal_assistant_preview_plan(
        intent,
        plan_id="pa_plan_approval_proposal_read_only_001",
        created_at=CREATED_AT,
    )

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        prepare_approval_proposal_from_plan(envelope.plan)

    assert "does not require approval" in str(exc_info.value)
    assert envelope.plan["execution_allowed"] is False
    assert envelope.receipt["approval_required"] is False
    assert envelope.receipt["metadata"]["execution_allowed"] is False


def test_approval_proposal_rejects_plan_matrix_metadata_drift() -> None:
    intent = GovernedIntent(
        request_id="pa_request_approval_proposal_drift_001",
        submitted_at=CREATED_AT,
        interface=RequestInterface.OPERATOR_CONSOLE,
        user_goal="Send one approved email draft to Daniel.",
        requested_capabilities=("email.send.with_approval",),
        requested_skill_ids=("email.send.with_approval",),
        risk_level=SkillRiskLevel.P4,
        requires_approval=True,
        execution_mode=RequestExecutionMode.EXECUTE_WITH_APPROVAL,
        approval_scope=ApprovalScope.PER_RECIPIENT,
        blocked_actions=("send", "forward", "connector_mutation"),
        evidence_refs=("proof://personal-assistant/request/approval-proposal-drift-001",),
    )
    envelope = build_personal_assistant_preview_plan(
        intent,
        plan_id="pa_plan_approval_proposal_drift_001",
        created_at=CREATED_AT,
    )
    drifted_plan = deepcopy(dict(envelope.plan))
    drifted_metadata = dict(drifted_plan["metadata"])
    drifted_matrix = dict(drifted_metadata["approval_matrix"])
    drifted_matrix["matrix_id"] = "personal_assistant_approval_matrix.drifted"
    drifted_metadata["approval_matrix"] = drifted_matrix
    drifted_plan["metadata"] = drifted_metadata

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        prepare_approval_proposal_from_plan(drifted_plan)

    assert "does not match runtime" in str(exc_info.value)
    assert "personal_assistant_approval_matrix.drifted" in str(exc_info.value)
    assert "personal_assistant_approval_matrix.foundation.v1" in str(exc_info.value)


def _enqueue_email_send(
    queue: PersonalAssistantApprovalQueue,
    *,
    approval_id: str | None = None,
):
    return queue.enqueue(
        request_id="pa_request_email_send_queue_001",
        plan_id="pa_plan_email_send_queue_001",
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
        evidence_refs=("proof://personal-assistant/approval/email-send-queue-001",),
        created_at=CREATED_AT,
        approval_id=approval_id,
    )
