"""Verify universal governed capability fabric v2 contracts.

Purpose: validate event, risk, episode, receipt, memory-gate, and passport
contracts for surface-neutral governed workroom episodes.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: universal_capability_fabric contracts, JSON schemas, and fabric fixtures.
Invariants:
  - Universal events carry idempotency, authority, risk, and context refs.
  - Risk tiers fail closed before capability routing.
  - Causal episodes follow the canonical stage order.
  - Receipts cannot claim non-blocked completion without evidence.
  - Durable memory cannot be stored without validation and audit scope.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.validate_schemas import _validate_schema_instance
from mcoi_runtime.contracts.universal_capability_fabric import (
    CAUSAL_EPISODE_STAGE_ORDER,
    CausalCapabilityReceipt,
    CausalEpisodePlan,
    CausalEpisodeStage,
    CausalEpisodeStep,
    FabricMemoryClass,
    FabricMemoryDecisionStatus,
    FabricPolicyDecision,
    FabricRiskClass,
    FabricSensitivity,
    MemoryGateDecision,
    RiskPolicyResult,
    UniversalCapabilityPassport,
    UniversalGovernedEvent,
    default_policy_decision_for_risk,
    derive_universal_event_idempotency_key,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schemas"
FIXTURE_DIR = REPO_ROOT / "integration" / "governed_capability_fabric" / "fixtures"
NOW = "2026-06-28T12:05:00+00:00"


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _schema(name: str) -> dict[str, object]:
    return _load_json(SCHEMA_DIR / name)


def _fixture(name: str) -> dict[str, object]:
    return _load_json(FIXTURE_DIR / name)


def test_universal_governed_event_schema_and_contract_round_trip() -> None:
    schema = _schema("universal_governed_event.schema.json")
    fixture = _fixture("universal_governed_event.json")
    event = UniversalGovernedEvent.from_mapping(fixture)

    errors = _validate_schema_instance(schema, fixture)

    assert errors == []
    assert event.risk_class is FabricRiskClass.CLASS_1_PREPARE
    assert event.idempotency_key == fixture["idempotency_key"]
    assert event.metadata["surface_adapter_action"] == "normalize_only"
    assert event.to_json_dict() == fixture


def test_universal_event_idempotency_key_is_deterministic() -> None:
    first = derive_universal_event_idempotency_key(
        surface="github",
        surface_event_id="github-pr-42-comment-1",
        actor_id="actor:tamirat",
        occurred_at="2026-06-28T12:00:00+00:00",
        intent="github.pr.review_merge_safety",
    )
    second = derive_universal_event_idempotency_key(
        surface="github",
        surface_event_id="github-pr-42-comment-1",
        actor_id="actor:tamirat",
        occurred_at="2026-06-28T12:00:00+00:00",
        intent="github.pr.review_merge_safety",
    )
    changed = derive_universal_event_idempotency_key(
        surface="github",
        surface_event_id="github-pr-43-comment-1",
        actor_id="actor:tamirat",
        occurred_at="2026-06-28T12:00:00+00:00",
        intent="github.pr.review_merge_safety",
    )

    assert first == second
    assert first.startswith("ueid:")
    assert len(first) == len("ueid:") + 64
    assert changed != first


def test_risk_tier_default_governance_fails_closed() -> None:
    assert default_policy_decision_for_risk(FabricRiskClass.CLASS_0_OBSERVE) is FabricPolicyDecision.ALLOW_READ_ONLY
    assert default_policy_decision_for_risk(FabricRiskClass.CLASS_1_PREPARE) is FabricPolicyDecision.ALLOW_DRAFT_ONLY
    assert default_policy_decision_for_risk(FabricRiskClass.CLASS_2_REVERSIBLE) is FabricPolicyDecision.ALLOW
    assert default_policy_decision_for_risk(FabricRiskClass.CLASS_3_SENSITIVE) is FabricPolicyDecision.REQUIRE_APPROVAL
    assert default_policy_decision_for_risk(FabricRiskClass.CLASS_4_EXTERNAL_OBLIGATION) is FabricPolicyDecision.REQUIRE_APPROVAL
    assert default_policy_decision_for_risk(FabricRiskClass.CLASS_5_BLOCKED) is FabricPolicyDecision.BLOCK


def test_external_obligation_policy_cannot_allow_direct_execution() -> None:
    with pytest.raises(ValueError, match="class_4_external_obligation"):
        RiskPolicyResult(
            policy_result_id="policy:bad-release",
            event_id="event:release",
            risk_class=FabricRiskClass.CLASS_4_EXTERNAL_OBLIGATION,
            decision=FabricPolicyDecision.ALLOW,
            allowed_tools=("github.merge",),
            blocked_actions=("merge_without_approval",),
            required_approvals=(),
            policy_refs=("policy.github.release",),
            reason="bad direct execution",
            decided_at=NOW,
        )


def test_capability_passport_contract_declares_non_authority() -> None:
    passport = UniversalCapabilityPassport(
        passport_id="passport:github-pr-safety-review",
        name="GitHub Pull Request Safety Review",
        domain="software_governance",
        inputs=("repo", "pull_request_number", "actor_id", "requested_action"),
        outputs=("merge_safety_judgment", "risk_summary", "receipt"),
        required_evidence=("pr_diff", "ci_status", "changed_files", "policy_match"),
        allowed_tools=("github.read", "ci.read", "diff.read"),
        blocked_actions=("merge_without_approval", "deploy_without_release_witness"),
        risk_class=FabricRiskClass.CLASS_1_PREPARE,
        verification_rules=("no_merge_judgment_without_diff", "no_completion_without_receipt"),
        receipt_fields=("actor", "repo", "pr", "evidence", "judgment", "blocked_actions"),
        memory_policy="store validated PR outcome only",
    )

    assert passport.passport_is_not_execution_authority is True
    assert "github.read" in passport.allowed_tools
    assert "merge_without_approval" in passport.blocked_actions


def test_capability_passport_rejects_authority_overclaim() -> None:
    with pytest.raises(ValueError, match="passport_is_not_execution_authority"):
        UniversalCapabilityPassport(
            passport_id="passport:unsafe",
            name="Unsafe Passport",
            domain="software_governance",
            inputs=("repo",),
            outputs=("result",),
            required_evidence=("diff",),
            allowed_tools=("github.write",),
            blocked_actions=("none",),
            risk_class=FabricRiskClass.CLASS_3_SENSITIVE,
            verification_rules=("receipt_required",),
            receipt_fields=("actor",),
            memory_policy="receipt only",
            passport_is_not_execution_authority=False,
        )


def test_causal_episode_plan_enforces_stage_order() -> None:
    steps = tuple(
        CausalEpisodeStep(
            stage=stage,
            status="completed",
            input_refs=("event:github-pr-42-review",),
            output_refs=(f"stage:{stage.value}",),
            reason=f"{stage.value} recorded",
        )
        for stage in CAUSAL_EPISODE_STAGE_ORDER
    )
    plan = CausalEpisodePlan(
        episode_id="episode:github-pr-42-review",
        event_id="event:github-pr-42-review",
        capability_id="software_dev.pr_safety_review",
        steps=steps,
        planned_at=NOW,
    )
    bad_steps = (steps[1], steps[0], *steps[2:])

    assert plan.steps[0].stage is CausalEpisodeStage.CAUSE
    assert plan.steps[-1].stage is CausalEpisodeStage.MEMORY_GATE
    assert len(plan.steps) == 10
    with pytest.raises(ValueError, match="canonical causal episode stage order"):
        CausalEpisodePlan(
            episode_id="episode:bad",
            event_id="event:github-pr-42-review",
            capability_id="software_dev.pr_safety_review",
            steps=bad_steps,
            planned_at=NOW,
        )


def test_causal_receipt_schema_contract_and_evidence_rules() -> None:
    schema = _schema("causal_capability_receipt.schema.json")
    fixture = _fixture("causal_capability_receipt.json")
    receipt = CausalCapabilityReceipt.from_mapping(fixture)
    invalid = copy.deepcopy(fixture)
    invalid["evidence_used"] = []

    errors = _validate_schema_instance(schema, fixture)

    assert errors == []
    assert receipt.policy_decision is FabricPolicyDecision.ALLOW_DRAFT_ONLY
    assert "merge_without_explicit_approval" in receipt.actions_blocked
    assert receipt.to_json_dict() == fixture
    with pytest.raises(ValueError, match="non-blocked receipt requires evidence_used"):
        CausalCapabilityReceipt.from_mapping(invalid)


def test_memory_gate_schema_contract_and_durable_validation_rule() -> None:
    schema = _schema("memory_gate_decision.schema.json")
    fixture = _fixture("memory_gate_decision.json")
    errors = _validate_schema_instance(schema, fixture)
    decision = MemoryGateDecision(
        decision_id=str(fixture["decision_id"]),
        event_id=str(fixture["event_id"]),
        receipt_id=str(fixture["receipt_id"]),
        memory_class=FabricMemoryClass.RECEIPT,
        status=FabricMemoryDecisionStatus.STORE,
        scope_ref=str(fixture["scope_ref"]),
        validated=bool(fixture["validated"]),
        durable=bool(fixture["durable"]),
        sensitivity=FabricSensitivity.OPERATIONAL,
        reasons=tuple(fixture["reasons"]),  # type: ignore[arg-type]
        decided_at=str(fixture["decided_at"]),
        can_delete=bool(fixture["can_delete"]),
        audit_ref=str(fixture["audit_ref"]),
    )

    assert errors == []
    assert decision.status is FabricMemoryDecisionStatus.STORE
    assert decision.durable is True
    assert decision.audit_ref == "audit://receipts/github-pr-42-review"
    with pytest.raises(ValueError, match="durable memory requires validated evidence"):
        MemoryGateDecision(
            decision_id="memory-gate:bad",
            event_id="event:github-pr-42-review",
            receipt_id="receipt:github-pr-42-review",
            memory_class=FabricMemoryClass.PROJECT,
            status=FabricMemoryDecisionStatus.STORE,
            scope_ref="scope://project/mullusi-control-plane",
            validated=False,
            durable=True,
            sensitivity=FabricSensitivity.OPERATIONAL,
            reasons=("attempted unvalidated durable memory",),
            decided_at=NOW,
            audit_ref="audit://bad",
        )
