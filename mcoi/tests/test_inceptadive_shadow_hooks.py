"""Focused tests for non-executing InceptaDive Shadow Pass hooks."""

from __future__ import annotations

from mcoi_runtime.app.inceptadive_shadow_integration import build_inceptadive_shadow_runtime
from mcoi_runtime.core.inceptadive_shadow_hooks import (
    ShadowHookStatus,
    run_interpretation_shadow_hook,
    run_planning_shadow_hook,
    run_preflight_shadow_hook,
    run_workflow_shadow_hook,
)
from mcoi_runtime.core.inceptadive_shadow_types import ShadowSeverity

_CREATED_AT = "2026-05-31T00:00:00+00:00"


def test_interpretation_hook_repairs_ambiguous_deploy_without_executing() -> None:
    runtime = build_inceptadive_shadow_runtime({})

    outcome = run_interpretation_shadow_hook(
        runtime,
        request_id="req-hook-interpret-deploy",
        user_input="deploy it",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
        created_at=_CREATED_AT,
    )
    payload = outcome.to_dict()

    assert outcome.status in {ShadowHookStatus.REPAIR_REQUIRED, ShadowHookStatus.BLOCK_RECOMMENDED}
    assert outcome.allowed_to_continue is False
    assert outcome.governance_required is True
    assert outcome.execution_authority is False
    assert outcome.finding_count >= 1
    assert outcome.receipt_id.startswith("shadow-receipt-")
    assert payload["execution_authority"] is False
    assert payload["raw_request_text_exposed"] is False
    assert payload["private_memory_exposed"] is False
    assert "deploy it" not in str(payload)


def test_planning_hook_blocks_high_impact_plan_without_evidence() -> None:
    runtime = build_inceptadive_shadow_runtime({})

    outcome = run_planning_shadow_hook(
        runtime,
        request_id="req-hook-plan-deploy",
        user_input="deploy dashboard",
        normal_intent="release dashboard",
        plan_steps=("build dashboard", "deploy production dashboard"),
        explicit_target="dashboard",
        scope="production",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
        created_at=_CREATED_AT,
    )

    assert outcome.status == ShadowHookStatus.BLOCK_RECOMMENDED
    assert outcome.block_recommended is True
    assert outcome.allowed_to_continue is False
    assert outcome.governance_required is True
    assert outcome.execution_authority is False
    assert outcome.fracture_delta_count >= 1


def test_workflow_hook_allows_low_risk_read_only_workflow_to_continue_to_governance() -> None:
    runtime = build_inceptadive_shadow_runtime({})

    outcome = run_workflow_shadow_hook(
        runtime,
        request_id="req-hook-workflow-readonly",
        user_input="summarize release notes",
        normal_intent="summarize notes",
        workflow_steps=("read release notes", "summarize release notes"),
        explicit_target="release notes",
        scope="docs",
        created_at=_CREATED_AT,
    )

    assert outcome.status == ShadowHookStatus.CLEAR
    assert outcome.allowed_to_continue is True
    assert outcome.governance_required is True
    assert outcome.execution_authority is False
    assert outcome.constructive_delta_count >= 1


def test_preflight_hook_blocks_destructive_candidate_without_scope_or_evidence() -> None:
    runtime = build_inceptadive_shadow_runtime({})

    outcome = run_preflight_shadow_hook(
        runtime,
        request_id="req-hook-preflight-delete",
        user_input="delete logs",
        candidate_action="delete production logs",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
        created_at=_CREATED_AT,
    )

    assert outcome.status == ShadowHookStatus.BLOCK_RECOMMENDED
    assert outcome.block_recommended is True
    assert outcome.allowed_to_continue is False
    assert outcome.governance_required is True
    assert outcome.execution_authority is False
    assert outcome.finding_count >= 2


def test_disabled_runtime_hook_is_still_redacted_and_non_executing() -> None:
    runtime = build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_ENABLED": "0"})

    outcome = run_interpretation_shadow_hook(
        runtime,
        request_id="req-hook-disabled",
        user_input="deploy it",
        created_at=_CREATED_AT,
    )
    payload = outcome.to_dict()

    assert outcome.status == ShadowHookStatus.CLEAR
    assert outcome.allowed_to_continue is True
    assert outcome.execution_authority is False
    assert payload["raw_request_text_exposed"] is False
    assert payload["private_memory_exposed"] is False
    assert "deploy it" not in str(payload)
    assert outcome.snapshot_hash == outcome.expected_snapshot_hash()


def test_hook_redacts_secret_shaped_request_id_before_runtime_activity() -> None:
    runtime = build_inceptadive_shadow_runtime({})
    raw_request_id = "hook-private-token-request-001"

    outcome = run_interpretation_shadow_hook(
        runtime,
        request_id=raw_request_id,
        user_input="summarize release notes",
        explicit_target="release notes",
        scope="docs",
        created_at=_CREATED_AT,
    )
    payload = outcome.to_dict()
    recent_results, recent_receipts = runtime.recent_activity(limit=5)

    assert outcome.request_id.startswith("shadow_hook_request_")
    assert payload["request_id"] == outcome.request_id
    assert raw_request_id not in str(payload)
    assert raw_request_id not in str(recent_results[0].to_dict())
    assert raw_request_id not in str(recent_receipts[0].to_dict())
    assert recent_results[0].request_id == outcome.request_id
    assert recent_receipts[0].request_id == outcome.request_id
    assert outcome.execution_authority is False
