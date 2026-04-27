"""Business process domain adapter tests."""
from __future__ import annotations

import pytest

from mcoi_runtime.domain_adapters import (
    BusinessActionKind,
    BusinessRequest,
    business_run_with_ucja,
    business_translate_from_universal,
    business_translate_to_universal,
)
from mcoi_runtime.domain_adapters.software_dev import UniversalResult
from uuid import uuid4


def _basic_request(**overrides) -> BusinessRequest:
    base = dict(
        kind=BusinessActionKind.APPROVAL,
        summary="approve marketing budget Q3",
        process_id="proc-001",
        initiator="alice",
        approval_chain=("manager-bob", "director-carol"),
        sla_deadline_hours=24.0,
        affected_systems=("erp", "finance_db"),
        acceptance_criteria=("budget_within_cap", "policy_compliance"),
        dollar_impact=50_000.0,
        blast_radius="department",
    )
    base.update(overrides)
    return BusinessRequest(**base)


# ---- translate_to_universal ----


def test_translate_purpose_for_each_kind():
    for kind in BusinessActionKind:
        req = _basic_request(kind=kind, summary="x")
        uni = business_translate_to_universal(req)
        assert ":" in uni.purpose_statement
        # First token before colon is the verb-style phrase
        assert "_" in uni.purpose_statement.split(":")[0]


def test_translate_approval_chain_becomes_authority():
    req = _basic_request()
    uni = business_translate_to_universal(req)
    assert "approver:manager-bob" in uni.authority_required
    assert "approver:director-carol" in uni.authority_required
    assert "approval_recorder" in uni.observer_required


def test_translate_no_approval_chain_falls_back_to_initiator():
    req = _basic_request(approval_chain=())
    uni = business_translate_to_universal(req)
    assert uni.authority_required == ("initiator:alice",)
    assert "audit_log" in uni.observer_required


def test_translate_sla_creates_escalation_constraint():
    req = _basic_request(sla_deadline_hours=8.0)
    uni = business_translate_to_universal(req)
    sla_constraints = [
        c for c in uni.constraint_set
        if c["domain"] == "sla"
    ]
    assert len(sla_constraints) == 1
    assert sla_constraints[0]["violation_response"] == "escalate"
    assert "8.0h" in sla_constraints[0]["restriction"]


def test_translate_no_sla_no_sla_constraint():
    req = _basic_request(sla_deadline_hours=None)
    uni = business_translate_to_universal(req)
    sla_constraints = [
        c for c in uni.constraint_set
        if c["domain"] == "sla"
    ]
    assert sla_constraints == []


def test_translate_rejects_negative_dollar_impact():
    req = _basic_request(dollar_impact=-1.0)
    with pytest.raises(ValueError, match="non-negative"):
        business_translate_to_universal(req)


def test_translate_rejects_non_positive_sla():
    req = _basic_request(sla_deadline_hours=0.0)
    with pytest.raises(ValueError, match="positive"):
        business_translate_to_universal(req)


def test_translate_blast_radius_to_permeability():
    cases = {
        "team":       "closed",
        "department": "selective",
        "division":   "selective",
        "enterprise": "open",
    }
    for blast, expected in cases.items():
        req = _basic_request(blast_radius=blast)
        uni = business_translate_to_universal(req)
        assert uni.boundary_specification["permeability"] == expected


# ---- translate_from_universal ----


def test_translate_from_pass_state_approves():
    req = _basic_request()
    result = UniversalResult(
        job_definition_id=uuid4(),
        construct_graph_summary={
            "observation": 1, "inference": 1, "decision": 1,
            "transformation": 1, "validation": 1, "execution": 1,
        },
        cognitive_cycles_run=2,
        converged=True,
        proof_state="Pass",
    )
    out = business_translate_from_universal(result, req)
    assert out.governance_status == "approved"
    assert out.required_approvals == req.approval_chain


def test_translate_high_dollar_flags_dual_approval():
    req = _basic_request(dollar_impact=250_000.0)
    result = UniversalResult(
        job_definition_id=uuid4(),
        construct_graph_summary={},
        cognitive_cycles_run=1,
        converged=True,
        proof_state="Pass",
    )
    out = business_translate_from_universal(result, req)
    assert any("dual approval" in f for f in out.risk_flags)


def test_translate_enterprise_blast_radius_flags_broadcast():
    req = _basic_request(blast_radius="enterprise")
    result = UniversalResult(
        job_definition_id=uuid4(),
        construct_graph_summary={},
        cognitive_cycles_run=1,
        converged=True,
        proof_state="Pass",
    )
    out = business_translate_from_universal(result, req)
    assert any("enterprise_blast_radius" in f for f in out.risk_flags)


def test_translate_tight_sla_flags_escalation():
    req = _basic_request(sla_deadline_hours=2.0)
    result = UniversalResult(
        job_definition_id=uuid4(),
        construct_graph_summary={},
        cognitive_cycles_run=1,
        converged=True,
        proof_state="Pass",
    )
    out = business_translate_from_universal(result, req)
    assert any("tight_sla" in f for f in out.risk_flags)


def test_translate_workflow_steps_from_constructs():
    req = _basic_request()
    result = UniversalResult(
        job_definition_id=uuid4(),
        construct_graph_summary={
            "observation": 1, "inference": 1, "decision": 1,
            "transformation": 1, "validation": 1, "execution": 1,
        },
        cognitive_cycles_run=2,
        converged=True,
        proof_state="Pass",
    )
    out = business_translate_from_universal(result, req)
    # Includes both approver routings + the SLA tracking step
    assert any("manager-bob" in s for s in out.workflow_steps)
    assert any("director-carol" in s for s in out.workflow_steps)
    assert any("SLA" in s for s in out.workflow_steps)


# ---- run_with_ucja end-to-end ----


def test_run_with_ucja_complete_request_passes():
    req = _basic_request()
    out = business_run_with_ucja(req)
    assert out.governance_status == "approved"
    assert any("Capture initial state" in s for s in out.workflow_steps)
    assert any("manager-bob" in s for s in out.workflow_steps)


def test_run_with_ucja_no_acceptance_criteria_blocks_at_l9():
    req = _basic_request(acceptance_criteria=())
    out = business_run_with_ucja(req)
    assert "Unknown" in out.governance_status


def test_run_with_ucja_offboarding_marks_irreversible():
    """OFFBOARDING produces an irreversible Transformation. The result
    is still approved but the governance trace records the irreversibility.
    """
    req = _basic_request(
        kind=BusinessActionKind.OFFBOARDING,
        summary="terminate vendor access",
    )
    out = business_run_with_ucja(req)
    assert out.governance_status == "approved"


def test_run_with_ucja_high_impact_flags_risk():
    req = _basic_request(dollar_impact=500_000.0)
    out = business_run_with_ucja(req)
    assert any("high_dollar_impact" in f for f in out.risk_flags)
