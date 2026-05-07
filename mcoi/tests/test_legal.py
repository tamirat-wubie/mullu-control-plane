"""Legal domain adapter tests."""
from __future__ import annotations

from uuid import uuid4

import pytest

from mcoi_runtime.domain_adapters import (
    LegalActionKind,
    LegalRequest,
    UniversalResult,
    legal_run_with_ucja,
    legal_translate_from_universal,
    legal_translate_to_universal,
)


def _request(**overrides) -> LegalRequest:
    base = dict(
        kind=LegalActionKind.CASE_FILING,
        summary="breach of contract suit",
        matter_id="M-2026-001",
        lead_counsel="alice",
        co_counsel=("bob",),
        client="acme-corp",
        opposing_party="widget-inc",
        jurisdiction="US-NY-FED",
        court="SDNY",
        bar_admissions_required=("NY",),
        privileged=False,
        acceptance_criteria=("jurisdiction_proper",),
        conflict_flags=(),
        is_emergency=False,
        statute_deadline_imminent=False,
        blast_radius="matter",
    )
    base.update(overrides)
    return LegalRequest(**base)


def test_translate_purpose_for_each_kind():
    for kind in LegalActionKind:
        # advisory kinds don't require court
        court = "" if kind in (
            LegalActionKind.CONTRACT_REVIEW,
            LegalActionKind.CONTRACT_EXECUTION,
            LegalActionKind.COMPLIANCE_REVIEW,
            LegalActionKind.OPINION,
        ) else "SDNY"
        uni = legal_translate_to_universal(_request(kind=kind, court=court))
        assert ":" in uni.purpose_statement


def test_translate_authority_includes_lead_and_co_counsel():
    uni = legal_translate_to_universal(_request(co_counsel=("bob", "carol")))
    assert "counsel:alice" in uni.authority_required
    assert "co_counsel:bob" in uni.authority_required
    assert "co_counsel:carol" in uni.authority_required


def test_translate_observers_include_jurisdiction_court_client_opposing():
    uni = legal_translate_to_universal(_request())
    assert "matter_audit" in uni.observer_required
    assert "jurisdiction:US-NY-FED" in uni.observer_required
    assert "court:SDNY" in uni.observer_required
    assert "bar:NY" in uni.observer_required
    assert "client:acme-corp" in uni.observer_required
    assert "opposing:widget-inc" in uni.observer_required


def test_translate_privilege_log_observer_when_privileged():
    uni = legal_translate_to_universal(_request(privileged=True))
    assert "privilege_log" in uni.observer_required

    uni2 = legal_translate_to_universal(_request(privileged=False))
    assert "privilege_log" not in uni2.observer_required


def test_translate_conflict_per_flag_blocks():
    uni = legal_translate_to_universal(
        _request(conflict_flags=("former_client_X", "spouse_at_Y")),
    )
    coi = [c for c in uni.constraint_set if c["domain"] == "conflict_of_interest"]
    assert len(coi) == 2
    assert all(c["violation_response"] == "block" for c in coi)


def test_translate_statute_deadline_blocks_unless_emergency():
    routine = legal_translate_to_universal(
        _request(statute_deadline_imminent=True, is_emergency=False),
    )
    sol_routine = [c for c in routine.constraint_set if c["domain"] == "deadline"]
    assert len(sol_routine) == 1
    assert sol_routine[0]["violation_response"] == "block"

    emergency = legal_translate_to_universal(
        _request(statute_deadline_imminent=True, is_emergency=True),
    )
    sol_emer = [c for c in emergency.constraint_set if c["domain"] == "deadline"]
    assert len(sol_emer) == 1
    assert sol_emer[0]["violation_response"] == "escalate"


def test_translate_bar_admission_constraint_escalates():
    uni = legal_translate_to_universal(_request(bar_admissions_required=("NY", "NJ")))
    bar = [c for c in uni.constraint_set if c["domain"] == "bar_admission"]
    assert len(bar) == 1
    assert bar[0]["violation_response"] == "escalate"
    assert "NY,NJ" in bar[0]["restriction"]


def test_translate_privileged_discovery_warns():
    uni = legal_translate_to_universal(
        _request(kind=LegalActionKind.DISCOVERY, privileged=True, court="SDNY"),
    )
    priv = [c for c in uni.constraint_set if c["domain"] == "privilege"]
    assert len(priv) == 1
    assert priv[0]["violation_response"] == "warn"

    # Privilege on advisory action does not produce a privilege constraint
    review = legal_translate_to_universal(
        _request(kind=LegalActionKind.OPINION, privileged=True, court=""),
    )
    priv_rev = [c for c in review.constraint_set if c["domain"] == "privilege"]
    assert priv_rev == []


def test_translate_litigation_without_court_rejected():
    with pytest.raises(ValueError, match="court"):
        legal_translate_to_universal(
            _request(kind=LegalActionKind.MOTION, court=""),
        )


def test_translate_advisory_without_court_allowed():
    uni = legal_translate_to_universal(
        _request(kind=LegalActionKind.OPINION, court=""),
    )
    assert uni.purpose_statement.startswith("issue_legal_advice")


def test_translate_blast_radius_to_permeability():
    cases = {
        "matter":            "closed",
        "client_portfolio":  "selective",
        "firm":              "selective",
        "systemic":          "open",
    }
    for blast, expected in cases.items():
        uni = legal_translate_to_universal(_request(blast_radius=blast))
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


def test_conflict_flagged_in_risk():
    out = legal_translate_from_universal(
        _result(),
        _request(conflict_flags=("former_client_X",)),
    )
    assert any("conflicts_of_interest_present" in f for f in out.risk_flags)


def test_statute_deadline_flagged():
    out = legal_translate_from_universal(
        _result(),
        _request(statute_deadline_imminent=True),
    )
    assert any("deadline_imminent" in f for f in out.risk_flags)


def test_emergency_mode_flagged():
    out = legal_translate_from_universal(
        _result(),
        _request(is_emergency=True),
    )
    assert any("emergency_mode" in f for f in out.risk_flags)


def test_irreversible_action_flagged():
    out = legal_translate_from_universal(
        _result(),
        _request(kind=LegalActionKind.CASE_FILING),
    )
    assert any("case_filing_irreversible" in f for f in out.risk_flags)


def test_systemic_blast_flagged():
    out = legal_translate_from_universal(
        _result(),
        _request(blast_radius="systemic"),
    )
    assert any("systemic_blast_radius" in f for f in out.risk_flags)


def test_privileged_discovery_flagged():
    out = legal_translate_from_universal(
        _result(),
        _request(kind=LegalActionKind.DISCOVERY, privileged=True),
    )
    assert any("privileged_discovery" in f for f in out.risk_flags)


def test_litigation_without_opposing_flagged():
    out = legal_translate_from_universal(
        _result(),
        _request(kind=LegalActionKind.CASE_FILING, opposing_party=""),
    )
    assert any(
        "case_filing_without_opposing_party" in f for f in out.risk_flags
    )


def test_protocol_case_filing_includes_clerk_step():
    out = legal_translate_from_universal(
        _result(),
        _request(kind=LegalActionKind.CASE_FILING),
    )
    assert any("clerk" in s.lower() for s in out.case_protocol)


def test_protocol_motion_includes_serve_step():
    out = legal_translate_from_universal(
        _result(),
        _request(kind=LegalActionKind.MOTION),
    )
    assert any("Serve motion" in s for s in out.case_protocol)


def test_protocol_includes_privilege_step_when_privileged():
    out = legal_translate_from_universal(
        _result(),
        _request(privileged=True),
    )
    assert any("privilege log" in s.lower() for s in out.case_protocol)


def test_protocol_includes_conflict_step_when_flags_present():
    out = legal_translate_from_universal(
        _result(),
        _request(conflict_flags=("former_client_X",)),
    )
    assert any("Conflicts committee" in s for s in out.case_protocol)


# ---- run_with_ucja ----


def test_run_complete_request_passes():
    out = legal_run_with_ucja(_request())
    assert out.governance_status == "approved"
    assert "lead: alice" in out.required_signoffs


def test_run_no_acceptance_criteria_blocks_at_l9():
    out = legal_run_with_ucja(_request(acceptance_criteria=()))
    assert "Unknown" in out.governance_status


def test_run_advisory_opinion_no_court_passes():
    out = legal_run_with_ucja(
        _request(
            kind=LegalActionKind.OPINION,
            court="",
            opposing_party="",
            acceptance_criteria=("authorities_cited",),
        ),
    )
    assert out.governance_status == "approved"


def test_result_carries_privilege_and_emergency_flags():
    out = legal_run_with_ucja(
        _request(privileged=True, is_emergency=False),
    )
    assert out.privilege_logged is True
    assert out.is_emergency is False
