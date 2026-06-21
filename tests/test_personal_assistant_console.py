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
    PersonalAssistantApprovalQueue,
    PersonalAssistantInvariantError,
    build_governed_team_assistant_pilot_read_model,
    build_personal_assistant_console_read_model,
    build_personal_assistant_readiness_demo,
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
    draft_lane = payload["lane_status"]["lanes"][5]
    assert draft_lane["lane_id"] == "draft_projection"
    assert draft_lane["route_refs"] == [
        "/api/v1/personal-assistant/drafts",
        "/api/v1/personal-assistant/drafts/email/preview",
        "/api/v1/personal-assistant/drafts/calendar/preview",
        "/api/v1/personal-assistant/drafts/task/preview",
    ]
    assert payload["lane_status"]["lanes"][-1]["lane_id"] == "operator_console"
    assert payload["lane_status"]["lanes"][-1]["route_refs"] == [
        "/api/v1/console/personal-assistant",
        "/api/v1/console/personal-assistant/view",
        "/api/v1/console/personal-assistant/readiness",
    ]
    teamops_lane = payload["lane_status"]["lanes"][6]
    assert teamops_lane["lane_id"] == "teamops_shared_inbox"
    assert "/api/v1/personal-assistant/teamops/gmail/live-probe/readiness" in teamops_lane["route_refs"]
    assert payload["skills"]["skill_count"] >= 13
    assert "send_email" in payload["blocked_actions"]
    assert "examples/personal_assistant_skill_registry.json" in payload["evidence_refs"]


def test_readiness_demo_answers_show_my_assistant_readiness_without_effects() -> None:
    console_payload = build_personal_assistant_console_read_model(generated_at=GENERATED_AT)
    demo = build_personal_assistant_readiness_demo(
        generated_at=GENERATED_AT,
        console_payload=console_payload,
    )

    assert demo["demo_id"] == "personal_assistant_readiness_read_only_demo"
    assert demo["user_ask"] == "Show my assistant readiness."
    assert demo["status"] == "foundation_read_only"
    assert demo["solver_outcome"] == "SolvedVerified"
    assert demo["inbox_projection_status"]["skill_id"] == "email.inbox.summarize"
    assert demo["inbox_projection_status"]["live_connector_execution_allowed"] is False
    assert demo["inbox_projection_status"]["mailbox_mutation_allowed"] is False
    assert demo["calendar_projection_status"]["skill_id"] == "calendar.day.brief"
    assert demo["calendar_projection_status"]["calendar_write_allowed"] is False
    assert demo["teamops_gmail_probe_status"]["status"] == "readiness_probe_available"
    assert demo["teamops_gmail_probe_status"]["external_provider_call_allowed"] is False
    assert demo["teamops_gmail_probe_status"]["mailbox_read_allowed"] is False
    assert "read_full_mailbox" in demo["teamops_gmail_probe_status"]["blocked_actions"]
    assert demo["available_skills"]["skill_count"] >= 13
    assert demo["available_skills"]["read_only_skill_ids"] == [
        "email.inbox.summarize",
        "calendar.day.brief",
    ]
    assert "send_email" in demo["blocked_actions"]
    assert demo["required_approvals"]["approval_before_send_required"] is True
    assert demo["required_approvals"]["approval_is_execution"] is False
    assert demo["receipts"]["receipt_count"] == console_payload["receipts"]["receipt_count"]
    assert demo["receipts"]["viewer_binding"]["runtime_dispatch_allowed"] is False
    assert demo["effect_boundary"]["execution_allowed"] is False
    assert demo["effect_boundary"]["external_send_allowed"] is False
    assert demo["effect_boundary"]["calendar_write_allowed"] is False
    assert demo["private_payload_policy"]["raw_private_payload_serialized"] is False


def test_governed_team_assistant_pilot_closes_issue_2067_demo_contract() -> None:
    console_payload = build_personal_assistant_console_read_model(generated_at=GENERATED_AT)
    readiness_payload = build_personal_assistant_readiness_demo(
        generated_at=GENERATED_AT,
        console_payload=console_payload,
    )
    pilot = build_governed_team_assistant_pilot_read_model(
        generated_at=GENERATED_AT,
        console_payload=console_payload,
        readiness_payload=readiness_payload,
    )
    separation = {row["phase"]: row for row in pilot["workflow_separation"]}

    assert pilot["pilot_id"] == "governed_team_assistant_pilot"
    assert pilot["operator_presentation"]["headline"].startswith("Mullu can show")
    assert "blocked-action reasons" in pilot["operator_presentation"]["can_show"]
    assert "send external messages" in pilot["operator_presentation"]["cannot_do_in_demo"]
    assert pilot["dashboard_projection"]["source_contract_ref"] == (
        "examples/agentic_service_harness_read_models.foundation.json"
    )
    assert pilot["dashboard_projection"]["mutation_endpoints_admitted"] is False
    assert pilot["demo_scenario"]["draft_preview"]["external_send_allowed"] is False
    assert pilot["demo_scenario"]["approval_preview"]["approval_is_execution"] is False
    assert pilot["demo_scenario"]["dry_run_receipt_trail"]["live_receipt_append_performed"] is False
    assert separation["observation"]["effect_allowed"] is False
    assert separation["approval"]["approval_is_execution"] is False
    assert separation["execution"]["state"] == "blocked_no_effect"
    assert pilot["pr_2058_review_decision"]["decision"] == "hold_open_do_not_merge"
    assert pilot["pr_2058_review_decision"]["merge_allowed"] is False
    assert pilot["inceptadive_advisory_panel"]["redacted"] is True
    assert pilot["inceptadive_advisory_panel"]["execution_authority_allowed"] is False
    assert pilot["deterministic_replay"]["deterministic_replay_from_fixtures"] is True
    assert pilot["deterministic_replay"]["external_calls_allowed"] is False
    assert "assert_all_effect_flags_false" in pilot["deterministic_replay"]["replay_steps"]
    assert pilot["approval_authority_next_phase"]["signed_operator_identity_required"] is True
    assert pilot["approval_authority_next_phase"]["replay_protection_required"] is True
    assert pilot["approval_authority_next_phase"]["execution_authority_granted_by_demo"] is False


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
    assert "Execution Allowed" in html


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
