"""Insurance domain adapter tests."""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from mcoi_runtime.domain_adapters import (
    InsuranceActionKind,
    InsuranceRequest,
    UniversalResult,
    insurance_run_with_ucja,
    insurance_translate_from_universal,
    insurance_translate_to_universal,
)


def _request(**overrides) -> InsuranceRequest:
    base = dict(
        kind=InsuranceActionKind.UNDERWRITING,
        summary="auto policy review",
        case_id="POL-001",
        responsible_agent="alice",
        approver_chain=("senior-uw",),
        policyholder="john-doe",
        line_of_business="auto",
        jurisdiction="US-CA",
        regulatory_regime=("CA-DOI",),
        policy_number="POL-001",
        claim_number="",
        sum_insured=Decimal("25000"),
        claim_amount=Decimal("0"),
        affected_policies=("POL-001",),
        acceptance_criteria=("risk_acceptable",),
        sanctions_screened=True,
        sanctions_hits=(),
        reinsurance_required=False,
        reinsurance_engaged=False,
        is_emergency=False,
        blast_radius="policy",
    )
    base.update(overrides)
    return InsuranceRequest(**base)


def test_translate_purpose_for_each_kind():
    for kind in InsuranceActionKind:
        # claims actions need claim_number
        claim_no = "CLM-001" if kind in (
            InsuranceActionKind.CLAIM_INTAKE,
            InsuranceActionKind.CLAIM_ADJUDICATION,
            InsuranceActionKind.CLAIM_PAYMENT,
        ) else ""
        uni = insurance_translate_to_universal(
            _request(kind=kind, claim_number=claim_no),
        )
        assert ":" in uni.purpose_statement


def test_translate_authority_includes_agent_and_approvers():
    uni = insurance_translate_to_universal(
        _request(approver_chain=("senior-uw", "vp")),
    )
    assert "agent:alice" in uni.authority_required
    assert "approver:senior-uw" in uni.authority_required
    assert "approver:vp" in uni.authority_required


def test_translate_observers_include_lob_jurisdiction_regulator():
    uni = insurance_translate_to_universal(_request())
    assert "policy_audit" in uni.observer_required
    assert "line_of_business:auto" in uni.observer_required
    assert "jurisdiction:US-CA" in uni.observer_required
    assert "regulator:CA-DOI" in uni.observer_required
    assert "policyholder:john-doe" in uni.observer_required
    assert "sanctions_compliance" in uni.observer_required


def test_translate_actuarial_review_for_large_sum():
    uni = insurance_translate_to_universal(
        _request(sum_insured=Decimal("5000000")),
    )
    assert "actuarial_review" in uni.observer_required


def test_translate_actuarial_review_for_claim_adjudication():
    uni = insurance_translate_to_universal(
        _request(
            kind=InsuranceActionKind.CLAIM_ADJUDICATION,
            claim_number="CLM-001",
        ),
    )
    assert "actuarial_review" in uni.observer_required


def test_translate_reinsurer_observer_when_engaged():
    uni = insurance_translate_to_universal(
        _request(reinsurance_required=True, reinsurance_engaged=True),
    )
    assert "reinsurer" in uni.observer_required


def test_translate_catastrophe_observer_when_emergency():
    uni = insurance_translate_to_universal(_request(is_emergency=True))
    assert "catastrophe_response_log" in uni.observer_required


def test_translate_sanctions_per_hit_blocks():
    uni = insurance_translate_to_universal(
        _request(sanctions_hits=("OFAC_match", "PEP_match")),
    )
    sanc = [c for c in uni.constraint_set if c["domain"] == "sanctions"]
    assert len(sanc) == 2
    assert all(c["violation_response"] == "block" for c in sanc)


def test_translate_sanctions_block_not_relaxed_by_emergency():
    uni = insurance_translate_to_universal(
        _request(sanctions_hits=("OFAC_match",), is_emergency=True),
    )
    sanc = [c for c in uni.constraint_set if c["domain"] == "sanctions"]
    assert sanc[0]["violation_response"] == "block"


def test_translate_over_limit_claim_blocks():
    uni = insurance_translate_to_universal(
        _request(
            kind=InsuranceActionKind.CLAIM_PAYMENT,
            claim_number="CLM-001",
            sum_insured=Decimal("10000"),
            claim_amount=Decimal("15000"),
        ),
    )
    pl = [c for c in uni.constraint_set if c["domain"] == "policy_limit"]
    assert len(pl) == 1
    assert pl[0]["violation_response"] == "block"


def test_translate_within_limit_claim_no_constraint():
    uni = insurance_translate_to_universal(
        _request(
            kind=InsuranceActionKind.CLAIM_PAYMENT,
            claim_number="CLM-001",
            sum_insured=Decimal("25000"),
            claim_amount=Decimal("10000"),
        ),
    )
    pl = [c for c in uni.constraint_set if c["domain"] == "policy_limit"]
    assert pl == []


def test_translate_reinsurance_required_unengaged_escalates():
    uni = insurance_translate_to_universal(
        _request(reinsurance_required=True, reinsurance_engaged=False),
    )
    re = [c for c in uni.constraint_set if c["domain"] == "reinsurance"]
    assert len(re) == 1
    assert re[0]["violation_response"] == "escalate"


def test_translate_negative_sum_insured_rejected():
    with pytest.raises(ValueError, match="sum_insured"):
        insurance_translate_to_universal(_request(sum_insured=Decimal("-1")))


def test_translate_claims_action_without_claim_number_rejected():
    with pytest.raises(ValueError, match="claim_number"):
        insurance_translate_to_universal(
            _request(kind=InsuranceActionKind.CLAIM_PAYMENT, claim_number=""),
        )


def test_translate_blast_radius_to_permeability():
    cases = {
        "policy":       "closed",
        "policyholder": "selective",
        "book":         "selective",
        "systemic":     "open",
    }
    for blast, expected in cases.items():
        uni = insurance_translate_to_universal(_request(blast_radius=blast))
        assert uni.boundary_specification["permeability"] == expected


def _result(state: str = "Pass") -> UniversalResult:
    return UniversalResult(
        job_definition_id=uuid4(),
        construct_graph_summary={
            "observation": 1, "inference": 1, "decision": 1,
            "transformation": 1, "validation": 1, "execution": 1,
        },
        cognitive_cycles_run=1,
        converged=True,
        proof_state=state,
    )


def test_sanctions_hits_flagged():
    out = insurance_translate_from_universal(
        _result(),
        _request(sanctions_hits=("OFAC_match",)),
    )
    assert any("sanctions_hits_present" in f for f in out.risk_flags)


def test_over_limit_claim_flagged():
    out = insurance_translate_from_universal(
        _result(),
        _request(
            kind=InsuranceActionKind.CLAIM_PAYMENT,
            claim_number="CLM-001",
            sum_insured=Decimal("10000"),
            claim_amount=Decimal("15000"),
        ),
    )
    assert any("claim_exceeds_sum_insured" in f for f in out.risk_flags)


def test_missing_reinsurance_flagged():
    out = insurance_translate_from_universal(
        _result(),
        _request(reinsurance_required=True, reinsurance_engaged=False),
    )
    assert any(
        "reinsurance_required_but_not_engaged" in f for f in out.risk_flags
    )


def test_emergency_mode_flagged():
    out = insurance_translate_from_universal(
        _result(),
        _request(is_emergency=True),
    )
    assert any("catastrophe_response_posture" in f for f in out.risk_flags)


def test_irreversible_action_flagged():
    out = insurance_translate_from_universal(
        _result(),
        _request(kind=InsuranceActionKind.BIND_POLICY),
    )
    assert any("bind_policy_irreversible" in f for f in out.risk_flags)


def test_systemic_blast_flagged():
    out = insurance_translate_from_universal(
        _result(),
        _request(blast_radius="systemic"),
    )
    assert any("systemic_blast_radius" in f for f in out.risk_flags)


def test_filing_without_regime_flagged():
    out = insurance_translate_from_universal(
        _result(),
        _request(
            kind=InsuranceActionKind.REGULATORY_FILING,
            regulatory_regime=(),
        ),
    )
    assert any(
        "regulatory_filing_without_regime" in f for f in out.risk_flags
    )


def test_protocol_includes_sanctions_clear_step():
    out = insurance_translate_from_universal(
        _result(),
        _request(sanctions_screened=True, sanctions_hits=()),
    )
    assert any("Sanctions screening clear" in s for s in out.handling_protocol)


def test_protocol_blocks_on_sanctions_hits():
    out = insurance_translate_from_universal(
        _result(),
        _request(sanctions_screened=True, sanctions_hits=("OFAC_match",)),
    )
    assert any(
        "Block: sanctions hit(s) present" in s for s in out.handling_protocol
    )


def test_protocol_bind_policy_includes_dec_page():
    out = insurance_translate_from_universal(
        _result(),
        _request(kind=InsuranceActionKind.BIND_POLICY),
    )
    assert any(
        "declaration page" in s for s in out.handling_protocol
    )


def test_protocol_claim_payment_includes_disbursement():
    out = insurance_translate_from_universal(
        _result(),
        _request(
            kind=InsuranceActionKind.CLAIM_PAYMENT,
            claim_number="CLM-001",
        ),
    )
    assert any(
        "Disburse indemnity" in s for s in out.handling_protocol
    )


# ---- run_with_ucja ----


def test_run_complete_request_passes():
    out = insurance_run_with_ucja(_request())
    assert out.governance_status == "approved"
    assert "agent: alice" in out.required_signoffs


def test_run_no_acceptance_criteria_blocks_at_l9():
    out = insurance_run_with_ucja(_request(acceptance_criteria=()))
    assert "Unknown" in out.governance_status


def test_run_large_bind_with_reinsurance_passes():
    out = insurance_run_with_ucja(
        _request(
            kind=InsuranceActionKind.BIND_POLICY,
            sum_insured=Decimal("5000000"),
            reinsurance_required=True,
            reinsurance_engaged=True,
            line_of_business="commercial",
            acceptance_criteria=(
                "risk_acceptable",
                "treaty_capacity_available",
            ),
        ),
    )
    assert out.governance_status == "approved"


def test_result_carries_sanctions_clear_and_emergency_flags():
    out = insurance_run_with_ucja(
        _request(
            sanctions_screened=True,
            sanctions_hits=(),
            is_emergency=False,
        ),
    )
    assert out.sanctions_clear is True
    assert out.is_emergency is False
