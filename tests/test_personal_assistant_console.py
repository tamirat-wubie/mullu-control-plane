"""Purpose: verify the personal-assistant foundation console read model.
Governance scope: read-only console panels, approval queue visibility, receipt
references, and private payload rejection.
Dependencies: personal-assistant console, approval queue, and registry fixtures.
Invariants: console rendering does not grant connector, write, send, deploy, or
live memory authority.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.personal_assistant import (
    ApprovalProposedAction,
    ApprovalScope,
    GovernedIntent,
    PersonalAssistantApprovalQueue,
    PersonalAssistantInvariantError,
    RequestExecutionMode,
    RequestInterface,
    SkillRiskLevel,
    build_personal_assistant_preview_plan,
    build_personal_assistant_console_read_model,
    prepare_approval_proposal_from_plan,
    render_personal_assistant_console_html,
)


GENERATED_AT = "2026-06-14T00:00:00Z"


def test_console_read_model_exposes_read_only_foundation_sections() -> None:
    payload = build_personal_assistant_console_read_model(generated_at=GENERATED_AT)

    assert payload["status"] == "foundation_read_only"
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["governed"] is True
    assert payload["assurance"]["outcome"] == "SolvedVerified"
    assert payload["assurance"]["authority_drift_detected"] is False
    assert payload["assurance"]["ready_for_live_execution"] is False
    assert payload["assurance"]["ready_for_customer_readiness_claim"] is False
    assert payload["effect_boundary"]["execution_allowed"] is False
    assert payload["effect_boundary"]["live_connector_execution_allowed"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False
    assert payload["effect_boundary"]["nested_mind_live_activation_allowed"] is False
    assert payload["sections"]["chat"]["execution_allowed"] is False
    assert payload["sections"]["tasks"]["task_write_allowed"] is False
    assert payload["sections"]["assistant_readiness"]["item_count"] == 1
    assert payload["sections"]["assistant_readiness"]["execution_allowed"] is False
    assert payload["receipts"]["viewer_binding"]["viewer_state"] == "foundation_read_only"
    assert payload["receipts"]["viewer_binding"]["projection_count"] == 0
    assert payload["receipts"]["viewer_binding"]["read_only_worker_rehearsal_bound"] is False
    assert payload["receipts"]["viewer_binding"]["runtime_dispatch_allowed"] is False
    assert payload["receipts"]["viewer_binding"]["success_claim_allowed"] is False
    assert payload["sections"]["lane_status"]["item_count"] == payload["lane_status"]["lane_count"]
    assert payload["lane_status"]["lane_count"] >= 12
    assert payload["lane_status"]["execution_allowed"] is False
    assert payload["lane_status"]["live_connector_execution_allowed"] is False
    assert payload["lane_status"]["customer_readiness_claim_allowed"] is False
    assert payload["lane_status"]["nested_mind_live_activation_allowed"] is False
    assert payload["lane_status"]["lanes"][-1]["lane_id"] == "operator_console"
    assert payload["lane_status"]["lanes"][-1]["route_refs"] == [
        "/api/v1/console/personal-assistant",
        "/api/v1/console/personal-assistant/view",
    ]
    readiness = payload["assistant_readiness"]
    pilot = payload["governed_team_assistant_pilot"]
    assert readiness["readiness_id"] == "personal_assistant_read_only_readiness_demo"
    assert readiness["user_prompt"] == "Show my assistant readiness."
    assert readiness["mode"] == "read_only"
    assert readiness["outcome"] == "SolvedVerified"
    assert readiness["inbox_projection_status"]["skill_id"] == "email.inbox.summarize"
    assert readiness["calendar_projection_status"]["skill_id"] == "calendar.day.brief"
    assert readiness["available_skills"]["skill_count"] == payload["skills"]["skill_count"]
    assert "email.send.with_approval" in readiness["available_skills"]["approval_required_skill_ids"]
    assert "send_email" in readiness["blocked_actions"]
    assert readiness["required_approvals"][0]["approval_id"] == "external_email_send_approval"
    assert readiness["required_approvals"][0]["approval_is_execution"] is False
    assert readiness["receipts"]["receipt_count"] == payload["receipts"]["receipt_count"]
    assert readiness["live_connector_execution_allowed"] is False
    assert readiness["mailbox_mutation_allowed"] is False
    assert readiness["calendar_write_allowed"] is False
    assert readiness["external_send_allowed"] is False
    assert readiness["raw_private_payload_serialized"] is False
    assert readiness["customer_readiness_claim_allowed"] is False
    assert payload["sections"]["pilot"]["item_count"] == 1
    assert payload["sections"]["pilot"]["execution_allowed"] is False
    assert payload["sections"]["pilot"]["customer_readiness_claim_allowed"] is False
    assert pilot["pilot_id"] == "governed_team_assistant_pilot_v0"
    assert pilot["package_name"] == "Governed Team Assistant Pilot"
    assert pilot["stage"] == "controlled_demo_productization"
    assert pilot["positioning"] == "Mullu is a governed assistant control plane."
    assert pilot["operator_prompt"] == "Show my assistant readiness."
    assert pilot["included_lane_ids"] == [lane["lane_id"] for lane in payload["lane_status"]["lanes"]]
    assert "/api/v1/personal-assistant/send-write/eligibility/preview" in pilot["demo_surface_refs"]
    assert "show_what_did_not_happen" in pilot["operator_promises"]
    assert "live_gmail_send_enabled" in pilot["blocked_claims"]
    assert pilot["pilot_readiness"]["send_write_preflight_ready"] is True
    assert pilot["pilot_readiness"]["live_execution_ready"] is False
    assert pilot["approval_boundary"]["approval_required_before_send"] is True
    assert pilot["approval_boundary"]["approval_is_execution"] is False
    assert pilot["receipt_boundary"]["receipt_required_for_actions"] is True
    assert pilot["receipt_boundary"]["runtime_dispatch_allowed"] is False
    assert pilot["effect_boundary"]["external_send_allowed"] is False
    assert pilot["operator_presentation"]["cannot_do_in_demo"] == [
        "call_live_connectors",
        "read_or_mutate_mailbox",
        "send_external_messages",
        "write_repositories",
        "dispatch_workers",
        "append_live_receipts",
        "claim_production_readiness",
    ]
    assert pilot["dashboard_projection"]["read_only"] is True
    assert pilot["dashboard_projection"]["fixture_backed"] is True
    assert pilot["dashboard_projection"]["worker_dispatch_allowed"] is False
    assert pilot["demo_scenario"]["draft_preview"]["preview_only"] is True
    assert pilot["demo_scenario"]["approval_preview"]["approval_is_execution"] is False
    assert pilot["demo_scenario"]["dry_run_receipt_trail"]["actions_not_taken_recorded"] is True
    assert all(phase["effect_allowed"] is False for phase in pilot["workflow_separation"])
    assert pilot["pr_2058_review_decision"]["decision"] == "hold_open_do_not_merge"
    assert pilot["pr_2058_review_decision"]["merge_allowed"] is False
    assert pilot["pr_2058_review_decision"]["issue_2067_decision_satisfied"] is True
    assert pilot["inceptadive_advisory_panel"]["redacted"] is True
    assert pilot["inceptadive_advisory_panel"]["execution_authority_allowed"] is False
    assert pilot["deterministic_replay"]["deterministic_replay_from_fixtures"] is True
    assert pilot["deterministic_replay"]["external_calls_allowed"] is False
    assert pilot["approval_authority_next_phase"]["status"] == "AwaitingEvidence"
    assert pilot["approval_authority_next_phase"]["execution_authority_granted_by_demo"] is False
    assert pilot["execution_allowed"] is False
    assert pilot["repository_write_allowed"] is False
    assert pilot["worker_dispatch_allowed"] is False
    assert pilot["live_receipt_append_allowed"] is False
    assert pilot["customer_readiness_claim_allowed"] is False
    assert payload["skills"]["skill_count"] >= 13
    assert "send_email" in payload["blocked_actions"]
    assert "examples/personal_assistant_skill_registry.json" in payload["evidence_refs"]


def test_console_composes_approval_records_receipts_and_escaped_html() -> None:
    queue = PersonalAssistantApprovalQueue()
    record = queue.enqueue(
        request_id="pa_request_console_approval_001",
        plan_id="pa_plan_console_approval_001",
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
        evidence_refs=("proof://personal-assistant/console/approval-001",),
        created_at=GENERATED_AT,
    )
    payload = build_personal_assistant_console_read_model(
        generated_at=GENERATED_AT,
        approval_queue=queue,
        recent_requests=(
            {
                "request_id": "pa_request_console_chat_001",
                "summary": "<script>alert(1)</script>",
                "status": "preview_only",
            },
        ),
        receipts=(
            {
                "receipt_id": "pa_receipt_console_preview_001",
                "receipt_kind": "personal_assistant_receipt",
                "source_receipt_ref": "examples/personal_assistant_receipt_draft_only.json",
                "skill_id": "email.response.draft",
                "decision": "allowed",
            },
        ),
    )
    html = render_personal_assistant_console_html(payload)

    assert payload["approval_queue"]["approval_count"] == 1
    assert payload["approval_queue"]["records"][0]["approval_id"] == record.approval_id
    assert payload["approval_queue"]["records"][0]["review_packet_ref"]["payload_digest_only"] is True
    assert payload["approval_queue"]["records"][0]["review_packet_ref"]["execution_allowed"] is False
    assert payload["memory"]["raw_private_payload_storage_allowed"] is False
    assert payload["memory"]["secret_value_storage_allowed"] is False
    assert payload["memory"]["metadata"]["raw_private_payload_storage_allowed"] is False
    assert payload["memory"]["metadata"]["secret_value_storage_allowed"] is False
    assert payload["receipts"]["viewer_binding"]["projection_count"] == 1
    assert payload["receipts"]["viewer_binding"]["projected_receipt_ids"] == ["pa_receipt_console_preview_001"]
    assert payload["receipts"]["viewer_binding"]["source_receipt_refs"] == [
        "examples/personal_assistant_receipt_draft_only.json"
    ]
    assert payload["receipts"]["viewer_binding"]["read_only_worker_rehearsal_bound"] is False
    assert payload["receipts"]["viewer_binding"]["terminal_closure_allowed"] is False
    assert record.latest_receipt["receipt_id"] in payload["receipt_refs"]
    assert "pa_receipt_console_preview_001" in payload["receipt_refs"]
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "Assistant Readiness" in html
    assert "Show my assistant readiness." in html
    assert "Execution Allowed" in html


def test_console_projects_approval_proposals_without_enqueue_or_execution() -> None:
    intent = GovernedIntent(
        request_id="pa_request_console_proposal_001",
        submitted_at=GENERATED_AT,
        interface=RequestInterface.OPERATOR_CONSOLE,
        user_goal="Send one approved email draft to Daniel.",
        requested_capabilities=("email.send.with_approval",),
        requested_skill_ids=("email.send.with_approval",),
        risk_level=SkillRiskLevel.P4,
        requires_approval=True,
        execution_mode=RequestExecutionMode.EXECUTE_WITH_APPROVAL,
        approval_scope=ApprovalScope.PER_RECIPIENT,
        blocked_actions=("send", "forward", "connector_mutation"),
        evidence_refs=("proof://personal-assistant/console/proposal-001",),
    )
    envelope = build_personal_assistant_preview_plan(
        intent,
        plan_id="pa_plan_console_proposal_001",
        created_at=GENERATED_AT,
    )
    proposal = prepare_approval_proposal_from_plan(
        envelope.plan,
        approval_scope=ApprovalScope.PER_RECIPIENT,
    )
    payload = build_personal_assistant_console_read_model(
        generated_at=GENERATED_AT,
        approval_proposals=(proposal.as_dict(),),
    )
    html = render_personal_assistant_console_html(payload)

    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["approval_queue"]["approval_count"] == 0
    assert payload["approval_queue"]["proposal_count"] == 1
    assert payload["approval_queue"]["proposal_ids"] == ["pa_plan_console_proposal_001"]
    assert payload["approval_queue"]["proposal_execution_allowed"] is False
    assert payload["approval_queue"]["proposals"][0]["execution_allowed"] is False
    assert payload["approval_queue"]["proposals"][0]["approval_is_execution"] is False
    assert payload["approval_queue"]["proposals"][0]["approval_matrix_ref"] == proposal.approval_matrix_ref
    assert payload["assurance"]["authority_drift_detected"] is False
    assert "Approval Proposals" in html
    assert "pa_plan_console_proposal_001" in html


def test_console_fails_closed_when_approval_proposal_claims_execution() -> None:
    payload = build_personal_assistant_console_read_model(
        generated_at=GENERATED_AT,
        approval_proposals=(
            {
                "request_id": "pa_request_console_unsafe_proposal_001",
                "plan_id": "pa_plan_console_unsafe_proposal_001",
                "approval_scope": "per_plan",
                "risk_level": "P4",
                "proposed_actions": [],
                "forbidden_without_approval": ["send"],
                "evidence_refs": ["proof://personal-assistant/console/unsafe-proposal-001"],
                "approval_matrix_ref": "personal_assistant_approval_matrix.foundation.v1",
                "execution_allowed": True,
                "approval_is_execution": True,
            },
        ),
    )

    assert payload["solver_outcome"] == "GovernanceBlocked"
    assert payload["assurance"]["authority_drift_detected"] is True
    assert "approval_proposals[0].execution_allowed" in payload["assurance"]["blocking_reasons"]
    assert "approval_proposals[0].approval_is_execution" in payload["assurance"]["blocking_reasons"]
    assert payload["approval_queue"]["proposal_execution_allowed"] is False
    assert payload["approval_queue"]["proposals"][0]["execution_allowed"] is False
    assert payload["approval_queue"]["proposals"][0]["approval_is_execution"] is False


def test_console_rejects_raw_private_fields_and_secret_like_values() -> None:
    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        build_personal_assistant_console_read_model(
            generated_at=GENERATED_AT,
            recent_requests=(
                {
                    "request_id": "pa_request_console_raw_001",
                    "raw_connector_payload": {"subject": "private"},
                    "status": "blocked",
                },
            ),
        )
    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_console_read_model(
            generated_at=GENERATED_AT,
            task_items=(
                {
                    "task_id": "pa_task_console_secret_001",
                    "summary": "rotate Bearer secret-worker-token",
                    "status": "blocked",
                },
            ),
        )

    assert "raw private field" in str(raw_exc.value)
    assert "secret-like value" in str(secret_exc.value)
    assert "raw_connector_payload" in str(raw_exc.value)


def test_console_fails_closed_when_approval_read_model_claims_execution() -> None:
    class UnsafeApprovalQueue:
        def read_model(self) -> dict[str, object]:
            return {
                "approval_count": 1,
                "approval_ids": ["pa_approval_unsafe_001"],
                "state_counts": {"requested": 1, "approved": 0, "rejected": 0, "revised": 0, "blocked": 0},
                "receipt_ids": [],
                "execution_allowed": True,
                "live_connector_execution_allowed": True,
                "external_send_allowed": True,
                "connector_mutation_allowed": True,
                "system_of_record_write_allowed": True,
                "approval_is_execution": True,
                "records": [],
                "metadata": {
                    "foundation_only": True,
                    "queue_projection": "read_model",
                    "live_connector_execution_allowed": True,
                    "approval_decision_executes_action": True,
                },
            }

    payload = build_personal_assistant_console_read_model(
        generated_at=GENERATED_AT,
        approval_queue=UnsafeApprovalQueue(),  # type: ignore[arg-type]
    )

    assert payload["solver_outcome"] == "GovernanceBlocked"
    assert payload["assurance"]["authority_drift_detected"] is True
    assert "approval_queue.execution_allowed" in payload["assurance"]["blocking_reasons"]
    assert "approval_queue.approval_is_execution" in payload["assurance"]["blocking_reasons"]
    assert "approval_queue.metadata.approval_decision_executes_action" in payload["assurance"]["blocking_reasons"]
    assert payload["sections"]["approvals"]["execution_allowed"] is False
    assert payload["approval_queue"]["execution_allowed"] is False
    assert payload["approval_queue"]["external_send_allowed"] is False
    assert payload["approval_queue"]["connector_mutation_allowed"] is False
    assert payload["approval_queue"]["metadata"]["approval_decision_executes_action"] is False


def test_console_fails_closed_when_memory_read_model_claims_live_activation() -> None:
    class UnsafeMemoryLedger:
        def read_model(self) -> dict[str, object]:
            return {
                "candidate_count": 1,
                "memory_observation_ids": ["pa_memory_unsafe_001"],
                "memory_types": ["preference"],
                "live_memory_write_allowed": True,
                "nested_mind_live_activation_allowed": True,
                "raw_private_payload_storage_allowed": True,
                "secret_value_storage_allowed": True,
                "candidate_only": False,
                "candidates": [],
                "metadata": {
                    "foundation_only": True,
                    "ledger_projection": "read_model",
                    "live_memory_write_allowed": True,
                    "nested_mind_live_activation_allowed": True,
                    "raw_private_payload_storage_allowed": True,
                    "secret_value_storage_allowed": True,
                },
            }

    payload = build_personal_assistant_console_read_model(
        generated_at=GENERATED_AT,
        memory_ledger=UnsafeMemoryLedger(),  # type: ignore[arg-type]
    )

    assert payload["solver_outcome"] == "GovernanceBlocked"
    assert payload["assurance"]["authority_drift_detected"] is True
    assert "memory.live_memory_write_allowed" in payload["assurance"]["blocking_reasons"]
    assert "memory.nested_mind_live_activation_allowed" in payload["assurance"]["blocking_reasons"]
    assert "memory.metadata.secret_value_storage_allowed" in payload["assurance"]["blocking_reasons"]
    assert payload["sections"]["memory"]["live_memory_write_allowed"] is False
    assert payload["memory"]["live_memory_write_allowed"] is False
    assert payload["memory"]["nested_mind_live_activation_allowed"] is False
    assert payload["memory"]["raw_private_payload_storage_allowed"] is False
    assert payload["memory"]["metadata"]["secret_value_storage_allowed"] is False


def test_console_fails_closed_when_teamops_plan_claims_live_probe() -> None:
    payload = build_personal_assistant_console_read_model(
        generated_at=GENERATED_AT,
        teamops_plans=(
            {
                "request_id": "pa_teamops_unsafe_001",
                "skill_id": "teamops.shared_inbox.plan",
                "status": "preview_only",
                "live_probe_allowed": True,
                "mailbox_mutation_allowed": True,
                "provider_call_allowed": True,
            },
        ),
    )

    assert payload["solver_outcome"] == "GovernanceBlocked"
    assert payload["assurance"]["authority_drift_detected"] is True
    assert "teamops_plans[0].live_probe_allowed" in payload["assurance"]["blocking_reasons"]
    assert "teamops_plans[0].mailbox_mutation_allowed" in payload["assurance"]["blocking_reasons"]
    assert "teamops_plans[0].provider_call_allowed" in payload["assurance"]["blocking_reasons"]
    assert payload["teamops"]["live_probe_allowed"] is False
    assert payload["teamops"]["mailbox_mutation_allowed"] is False
    assert payload["teamops"]["provider_call_allowed"] is False
