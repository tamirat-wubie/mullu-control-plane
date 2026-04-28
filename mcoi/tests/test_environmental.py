"""Environmental / ESG domain adapter tests."""
from __future__ import annotations

from uuid import uuid4

import pytest

from mcoi_runtime.domain_adapters import (
    EnvironmentalActionKind,
    EnvironmentalRequest,
    UniversalResult,
    environmental_run_with_ucja,
    environmental_translate_from_universal,
    environmental_translate_to_universal,
)


def _request(**overrides) -> EnvironmentalRequest:
    base = dict(
        kind=EnvironmentalActionKind.PERMIT_COMPLIANCE_CHECK,
        summary="quarterly permit check",
        facility_id="FAC-001",
        responsible_officer="alice",
        reviewer_chain=("internal-audit",),
        operator="acme-mfg",
        regulatory_authority="EPA",
        regulatory_regime=("CAA",),
        jurisdiction="US-FED",
        affected_media=("air",),
        affected_communities=(),
        acceptance_criteria=("permit_terms_met",),
        exceedance_present=False,
        environmental_justice_concern=False,
        third_party_verified=False,
        is_emergency=False,
        blast_radius="facility",
    )
    base.update(overrides)
    return EnvironmentalRequest(**base)


def test_translate_purpose_for_each_kind():
    for kind in EnvironmentalActionKind:
        # disclosure requires regulatory_regime
        regime = ("SEC_CLIMATE",) if kind == EnvironmentalActionKind.DISCLOSURE_FILING else ("CAA",)
        # disclosure also requires verified
        verified = kind == EnvironmentalActionKind.DISCLOSURE_FILING
        uni = environmental_translate_to_universal(
            _request(
                kind=kind,
                regulatory_regime=regime,
                third_party_verified=verified,
            ),
        )
        assert ":" in uni.purpose_statement


def test_translate_authority_includes_officer_and_reviewers():
    uni = environmental_translate_to_universal(
        _request(reviewer_chain=("internal-audit", "sustainability")),
    )
    assert "officer:alice" in uni.authority_required
    assert "reviewer:internal-audit" in uni.authority_required
    assert "reviewer:sustainability" in uni.authority_required


def test_translate_observers_include_regulator_regime_jurisdiction():
    uni = environmental_translate_to_universal(_request())
    assert "ehs_audit" in uni.observer_required
    assert "regulator:EPA" in uni.observer_required
    assert "regime:CAA" in uni.observer_required
    assert "jurisdiction:US-FED" in uni.observer_required
    assert "operator:acme-mfg" in uni.observer_required


def test_translate_community_observers_per_community():
    uni = environmental_translate_to_universal(
        _request(affected_communities=("downwind-A", "downstream-B")),
    )
    assert "community:downwind-A" in uni.observer_required
    assert "community:downstream-B" in uni.observer_required


def test_translate_ej_oversight_when_concern_present():
    uni = environmental_translate_to_universal(
        _request(environmental_justice_concern=True),
    )
    assert "ej_oversight" in uni.observer_required


def test_translate_verifier_when_verified():
    uni = environmental_translate_to_universal(_request(third_party_verified=True))
    assert "third_party_verifier" in uni.observer_required


def test_translate_incident_command_when_emergency():
    uni = environmental_translate_to_universal(_request(is_emergency=True))
    assert "incident_command" in uni.observer_required


def test_translate_exceedance_blocks_routine():
    uni = environmental_translate_to_universal(
        _request(exceedance_present=True, is_emergency=False),
    )
    ex = [c for c in uni.constraint_set if c["domain"] == "exceedance"]
    assert len(ex) == 1
    assert ex[0]["violation_response"] == "block"


def test_translate_exceedance_escalates_under_emergency():
    uni = environmental_translate_to_universal(
        _request(exceedance_present=True, is_emergency=True),
    )
    ex = [c for c in uni.constraint_set if c["domain"] == "exceedance"]
    assert ex[0]["violation_response"] == "escalate"


def test_translate_exceedance_no_constraint_for_response_kinds():
    for kind in (
        EnvironmentalActionKind.INCIDENT_RESPONSE,
        EnvironmentalActionKind.REMEDIATION_EXECUTION,
    ):
        uni = environmental_translate_to_universal(
            _request(kind=kind, exceedance_present=True),
        )
        ex = [c for c in uni.constraint_set if c["domain"] == "exceedance"]
        assert ex == [], f"{kind.value} should not be blocked by exceedance"


def test_translate_ej_concern_escalates():
    uni = environmental_translate_to_universal(
        _request(environmental_justice_concern=True),
    )
    ej = [c for c in uni.constraint_set if c["domain"] == "environmental_justice"]
    assert len(ej) == 1
    assert ej[0]["violation_response"] == "escalate"


def test_translate_disclosure_without_verification_blocks():
    uni = environmental_translate_to_universal(
        _request(
            kind=EnvironmentalActionKind.DISCLOSURE_FILING,
            regulatory_regime=("SEC_CLIMATE",),
            third_party_verified=False,
        ),
    )
    ver = [c for c in uni.constraint_set if c["domain"] == "verification"]
    assert len(ver) == 1
    assert ver[0]["violation_response"] == "block"


def test_translate_disclosure_with_verification_no_block():
    uni = environmental_translate_to_universal(
        _request(
            kind=EnvironmentalActionKind.DISCLOSURE_FILING,
            regulatory_regime=("SEC_CLIMATE",),
            third_party_verified=True,
        ),
    )
    ver = [c for c in uni.constraint_set if c["domain"] == "verification"]
    assert ver == []


def test_translate_disclosure_without_regime_rejected():
    with pytest.raises(ValueError, match="disclosure_filing"):
        environmental_translate_to_universal(
            _request(
                kind=EnvironmentalActionKind.DISCLOSURE_FILING,
                regulatory_regime=(),
            ),
        )


def test_translate_invalid_media_rejected():
    with pytest.raises(ValueError, match="environmental media"):
        environmental_translate_to_universal(_request(affected_media=("plasma",)))


def test_translate_blast_radius_to_permeability():
    cases = {
        "facility":  "closed",
        "watershed": "selective",
        "airshed":   "selective",
        "regional":  "open",
    }
    for blast, expected in cases.items():
        uni = environmental_translate_to_universal(_request(blast_radius=blast))
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


def test_active_exceedance_routine_flagged():
    out = environmental_translate_from_universal(
        _result(),
        _request(exceedance_present=True, is_emergency=False),
    )
    assert any(
        "active_exceedance_routine_action" in f for f in out.risk_flags
    )


def test_active_exceedance_emergency_flagged_differently():
    out = environmental_translate_from_universal(
        _result(),
        _request(exceedance_present=True, is_emergency=True),
    )
    assert any(
        "active_exceedance_under_emergency" in f for f in out.risk_flags
    )


def test_response_during_exceedance_flagged():
    out = environmental_translate_from_universal(
        _result(),
        _request(
            kind=EnvironmentalActionKind.REMEDIATION_EXECUTION,
            exceedance_present=True,
        ),
    )
    assert any(
        "active_exceedance_during_remediation_execution" in f
        for f in out.risk_flags
    )


def test_ej_concern_flagged():
    out = environmental_translate_from_universal(
        _result(),
        _request(environmental_justice_concern=True),
    )
    assert any(
        "environmental_justice_concern" in f for f in out.risk_flags
    )


def test_disclosure_without_verification_flagged():
    out = environmental_translate_from_universal(
        _result(),
        _request(
            kind=EnvironmentalActionKind.DISCLOSURE_FILING,
            regulatory_regime=("SEC_CLIMATE",),
            third_party_verified=False,
        ),
    )
    assert any(
        "disclosure_without_third_party_verification" in f
        for f in out.risk_flags
    )


def test_emergency_mode_flagged():
    out = environmental_translate_from_universal(
        _result(),
        _request(is_emergency=True),
    )
    assert any("incident_response_posture" in f for f in out.risk_flags)


def test_regional_blast_flagged():
    out = environmental_translate_from_universal(
        _result(),
        _request(blast_radius="regional"),
    )
    assert any("regional_blast_radius" in f for f in out.risk_flags)


def test_irreversible_action_flagged():
    out = environmental_translate_from_universal(
        _result(),
        _request(
            kind=EnvironmentalActionKind.DISCLOSURE_FILING,
            regulatory_regime=("SEC_CLIMATE",),
            third_party_verified=True,
        ),
    )
    assert any(
        "disclosure_filing_irreversible" in f for f in out.risk_flags
    )


def test_cross_media_flagged():
    out = environmental_translate_from_universal(
        _result(),
        _request(affected_media=("air", "water")),
    )
    assert any("cross_media_impact" in f for f in out.risk_flags)


def test_emissions_without_verification_flagged():
    out = environmental_translate_from_universal(
        _result(),
        _request(
            kind=EnvironmentalActionKind.EMISSIONS_REPORTING,
            third_party_verified=False,
        ),
    )
    assert any(
        "emissions_reporting_without_third_party_verification" in f
        for f in out.risk_flags
    )


def test_protocol_includes_ej_review_step():
    out = environmental_translate_from_universal(
        _result(),
        _request(environmental_justice_concern=True),
    )
    assert any(
        "Environmental-justice review" in s for s in out.stewardship_protocol
    )


def test_protocol_response_during_exceedance():
    out = environmental_translate_from_universal(
        _result(),
        _request(
            kind=EnvironmentalActionKind.INCIDENT_RESPONSE,
            exceedance_present=True,
        ),
    )
    assert any(
        "Active exceedance" in s and "response action" in s
        for s in out.stewardship_protocol
    )


def test_protocol_disclosure_files_with_regulator():
    out = environmental_translate_from_universal(
        _result(),
        _request(
            kind=EnvironmentalActionKind.DISCLOSURE_FILING,
            regulatory_regime=("SEC_CLIMATE",),
            third_party_verified=True,
        ),
    )
    assert any(
        "File assured disclosure" in s for s in out.stewardship_protocol
    )


# ---- run_with_ucja ----


def test_run_complete_request_passes():
    out = environmental_run_with_ucja(_request())
    assert out.governance_status == "approved"
    assert "officer: alice" in out.required_signoffs


def test_run_no_acceptance_criteria_blocks_at_l9():
    out = environmental_run_with_ucja(_request(acceptance_criteria=()))
    assert "Unknown" in out.governance_status


def test_run_response_during_exceedance_passes():
    out = environmental_run_with_ucja(
        _request(
            kind=EnvironmentalActionKind.INCIDENT_RESPONSE,
            exceedance_present=True,
            is_emergency=True,
            acceptance_criteria=("incident_logged", "authorities_notified"),
        ),
    )
    assert out.governance_status == "approved"
    assert out.is_emergency is True


def test_result_carries_verification_and_emergency_flags():
    out = environmental_run_with_ucja(
        _request(third_party_verified=True, is_emergency=False),
    )
    assert out.third_party_verified is True
    assert out.is_emergency is False
