"""Tests for the Personal Assistant approval-matrix runtime policy.

Purpose: prove runtime approval admission is bound to the checked-in matrix and
does not grant execution authority.
Governance scope: P0-P5 matrix loading, P4/P5 approval gates, P5 blocked mode,
blocked-without-approval coverage, and approval queue integration.
Dependencies: mcoi_runtime.personal_assistant approval-matrix runtime and
foundation approval fixtures.
Invariants:
  - Approval matrix loading is deterministic and no-effect.
  - Approval queue admission consults the matrix before emitting a packet.
  - Approval decision evidence remains separate from execution authority.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    ApprovalProposedAction,
    ApprovalScope,
    PersonalAssistantApprovalMatrix,
    PersonalAssistantApprovalQueue,
    PersonalAssistantInvariantError,
    SkillRiskLevel,
    load_default_personal_assistant_approval_matrix,
)


ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = ROOT / "governance" / "personal_assistant_approval_matrix.yaml"
CREATED_AT = "2026-06-14T00:00:00+00:00"


def test_default_approval_matrix_loads_no_execution_policy() -> None:
    matrix = load_default_personal_assistant_approval_matrix()
    read_model = matrix.read_model()
    p4 = matrix.policy_for(SkillRiskLevel.P4)
    p5 = matrix.policy_for("P5")

    assert matrix.matrix_id == "personal_assistant_approval_matrix.foundation.v1"
    assert read_model["execution_allowed_by_matrix"] is False
    assert read_model["approval_is_execution"] is False
    assert p4.explicit_approval_required is True
    assert p4.effect_bearing is True
    assert "execute_with_approval" in p4.allowed_modes
    assert p5.allowed_modes == ("blocked",)
    assert read_model["overclaim_blocks"]["live_nested_mind_activation_allowed"] is False


def test_approval_queue_packet_records_matrix_ref_without_execution() -> None:
    queue = PersonalAssistantApprovalQueue()
    record = queue.enqueue(
        request_id="pa_request_matrix_email_queue_001",
        plan_id="pa_plan_matrix_email_queue_001",
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
        forbidden_without_approval=("send", "forward", "connector_mutation"),
        evidence_refs=("proof://personal-assistant/approval/matrix-email-001",),
        created_at=CREATED_AT,
    )
    packet = dict(record.packet)
    receipt = dict(record.latest_receipt)

    assert packet["metadata"]["approval_matrix_ref"] == "personal_assistant_approval_matrix.foundation.v1"
    assert receipt["metadata"]["approval_matrix_ref"] == "personal_assistant_approval_matrix.foundation.v1"
    assert packet["approval_state"] == "requested"
    assert packet["metadata"]["execution_allowed"] is False
    assert receipt["metadata"]["approval_is_execution"] is False
    assert "external_message_not_sent" in receipt["actions_not_taken"]


def test_approval_matrix_rejects_p5_execute_with_approval_mode() -> None:
    matrix = load_default_personal_assistant_approval_matrix()

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        matrix.assert_action_admitted(
            risk_level="P5",
            execution_mode="execute_with_approval",
            forbidden_without_approval=("deploy_service", "publish"),
        )

    assert "P5" in str(exc_info.value)
    assert "not allowed by approval matrix" in str(exc_info.value)
    assert "deploy_service" not in str(exc_info.value)


def test_approval_queue_rejects_actions_outside_matrix_blocked_set() -> None:
    queue = PersonalAssistantApprovalQueue()

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        queue.enqueue(
            request_id="pa_request_matrix_unknown_block_001",
            plan_id="pa_plan_matrix_unknown_block_001",
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
            forbidden_without_approval=("send", "unknown_mutation_surface"),
            evidence_refs=("proof://personal-assistant/approval/matrix-unknown-block-001",),
            created_at=CREATED_AT,
        )

    assert "outside matrix" in str(exc_info.value)
    assert "unknown_mutation_surface" in str(exc_info.value)
    assert queue.read_model()["approval_count"] == 0


def test_approval_matrix_rejects_overclaim_and_p5_mode_drift() -> None:
    payload = _load_json(MATRIX_PATH)
    payload["overclaim_blocks"]["production_readiness_claim_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as overclaim_exc:
        PersonalAssistantApprovalMatrix.from_mapping(payload)

    p5_payload = _load_json(MATRIX_PATH)
    for entry in p5_payload["risk_levels"]:
        if entry["level"] == "P5":
            entry["allowed_modes"] = ["execute_with_approval", "blocked"]

    with pytest.raises(PersonalAssistantInvariantError) as p5_exc:
        PersonalAssistantApprovalMatrix.from_mapping(p5_payload)

    assert "production_readiness_claim_allowed" in str(overclaim_exc.value)
    assert "P5" in str(p5_exc.value)
    assert "allowed_modes" in str(p5_exc.value)


def test_duplicate_approval_risk_level_is_rejected() -> None:
    payload = _load_json(MATRIX_PATH)
    payload["risk_levels"].append(deepcopy(payload["risk_levels"][0]))

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        PersonalAssistantApprovalMatrix.from_mapping(payload)

    assert "duplicate risk level" in str(exc_info.value)
    assert "P0" in str(exc_info.value)
    assert len(payload["risk_levels"]) == 7


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
