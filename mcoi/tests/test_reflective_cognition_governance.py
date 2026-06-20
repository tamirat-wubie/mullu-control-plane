"""Focused tests for the bounded reflective cognition governance kernel."""

from __future__ import annotations

from mcoi_runtime.core.reflective_cognition_governance import (
    EvidenceClaim,
    EvidenceStatus,
    ReflectionDepth,
    RiskLevel,
    ValidationStatus,
    audit_reflective_cognition,
    choose_reflection_depth,
    reflection_budget_for,
)

_CREATED_AT = "2026-06-20T00:00:00+00:00"


def test_reflective_audit_redacts_raw_request_and_detects_scope_creep() -> None:
    raw_request = "Apply all important things to Mullu and guarantee it is fully complete."

    receipt = audit_reflective_cognition(
        request_id="req-reflect-scope",
        user_input=raw_request,
        risk_level=RiskLevel.MEDIUM,
        created_at=_CREATED_AT,
    )
    payload = receipt.to_dict()

    assert receipt.execution_authority is False
    assert receipt.governance_required is True
    assert payload["raw_request_text_exposed"] is False
    assert payload["private_memory_exposed"] is False
    assert raw_request not in str(payload)
    assert "scope_creep_risk" in receipt.bias_flags
    assert "absolute_scope_overreach" in receipt.bias_flags
    assert receipt.validation_status == ValidationStatus.ADVISORY
    assert receipt.snapshot_hash == receipt.expected_snapshot_hash()


def test_high_risk_destructive_request_gets_high_depth_and_block_recommendation() -> None:
    receipt = audit_reflective_cognition(
        request_id="req-reflect-delete-deploy",
        user_input="Deploy production and delete logs while preserving causal continuity.",
        risk_level=RiskLevel.HIGH,
        created_at=_CREATED_AT,
    )

    assert receipt.reflection_depth == ReflectionDepth.HIGH
    assert receipt.validation_status == ValidationStatus.BLOCK_RECOMMENDED
    assert receipt.execution_authority is False
    assert receipt.governance_required is True
    assert any("blocked" in receipt.next_safe_action.lower() for _ in [receipt.next_safe_action])
    assert receipt.contradictions
    assert receipt.edge_cases
    assert receipt.unresolved_gaps


def test_unsupported_claim_forces_evidence_gate_before_final_output() -> None:
    receipt = audit_reflective_cognition(
        request_id="req-reflect-evidence",
        user_input="Report current platform status.",
        risk_level="medium",
        evidence_claims=(
            EvidenceClaim(
                claim_id="claim-live-deployed",
                label="runtime deployment is live",
                status=EvidenceStatus.UNSUPPORTED,
            ),
        ),
        created_at=_CREATED_AT,
    )

    assert receipt.validation_status == ValidationStatus.NEEDS_EVIDENCE
    assert receipt.evidence_gaps[0]["claim_id"] == "claim-live-deployed"
    assert "Attach evidence refs" in receipt.corrections[0]
    assert receipt.next_safe_action.startswith("Attach evidence refs")


def test_reflection_budget_bounds_recursive_audit_output() -> None:
    receipt = audit_reflective_cognition(
        request_id="req-reflect-budget",
        user_input=(
            "Audit, inspect, evaluate, weakness fix, gap fix, edge case, refine, "
            "apply all important things, guarantee complete forever, deploy production, "
            "publish private secret, delete and preserve causal continuity."
        ),
        risk_level=RiskLevel.HIGH,
        created_at=_CREATED_AT,
    )
    budget = reflection_budget_for(receipt.reflection_depth)

    assert len(receipt.assumptions) <= budget.max_assumptions
    assert len(receipt.bias_flags) <= budget.max_bias_flags
    assert len(receipt.contradictions) <= budget.max_contradictions
    assert len(receipt.edge_cases) <= budget.max_edge_cases
    assert len(receipt.corrections) <= budget.max_corrections
    assert receipt.snapshot_hash == receipt.expected_snapshot_hash()


def test_depth_selection_is_adaptive_to_risk_and_metacognitive_language() -> None:
    assert choose_reflection_depth("what is this", RiskLevel.LOW) == ReflectionDepth.LOW
    assert choose_reflection_depth("apply audit and refinement", RiskLevel.LOW) == ReflectionDepth.MEDIUM
    assert choose_reflection_depth("deploy production", RiskLevel.LOW) == ReflectionDepth.HIGH
    assert choose_reflection_depth("summarize docs", RiskLevel.HIGH) == ReflectionDepth.HIGH
