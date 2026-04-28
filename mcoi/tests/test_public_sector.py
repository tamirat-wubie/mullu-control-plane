"""Public sector / government domain adapter tests."""
from __future__ import annotations

from uuid import uuid4

import pytest

from mcoi_runtime.domain_adapters import (
    CivicActionKind,
    CivicRequest,
    UniversalResult,
    public_sector_run_with_ucja,
    public_sector_translate_from_universal,
    public_sector_translate_to_universal,
)


def _request(**overrides) -> CivicRequest:
    base = dict(
        kind=CivicActionKind.PERMIT_ISSUANCE,
        summary="construction permit",
        case_id="PERMIT-001",
        responsible_official="alice",
        reviewer_chain=("bob",),
        applicant="john-doe",
        agency="DBI-SF",
        statute_authority=("SF_BUILDING_CODE",),
        jurisdiction="US-CA-SF",
        affected_records=("parcel-123",),
        acceptance_criteria=("zoning_compliant",),
        due_process_required=True,
        due_process_completed=True,
        public_comment_required=False,
        public_comment_completed=False,
        protected_class_present=(),
        is_emergency=False,
        blast_radius="case",
    )
    base.update(overrides)
    return CivicRequest(**base)


def test_translate_purpose_for_each_kind():
    for kind in CivicActionKind:
        # rulemaking requires statute_authority
        statute = ("APA",) if kind == CivicActionKind.RULEMAKING else ()
        req = _request(kind=kind, statute_authority=statute or ("AGENCY_ACT",))
        uni = public_sector_translate_to_universal(req)
        assert ":" in uni.purpose_statement


def test_translate_authority_includes_official_and_reviewers():
    uni = public_sector_translate_to_universal(_request(reviewer_chain=("bob", "carol")))
    assert "official:alice" in uni.authority_required
    assert "reviewer:bob" in uni.authority_required
    assert "reviewer:carol" in uni.authority_required


def test_translate_observers_include_agency_jurisdiction_statute_ombudsman():
    uni = public_sector_translate_to_universal(_request())
    assert "civic_audit" in uni.observer_required
    assert "ombudsman" in uni.observer_required
    assert "agency:DBI-SF" in uni.observer_required
    assert "jurisdiction:US-CA-SF" in uni.observer_required
    assert "statute:SF_BUILDING_CODE" in uni.observer_required
    assert "applicant:john-doe" in uni.observer_required


def test_translate_due_process_required_but_incomplete_blocks():
    uni = public_sector_translate_to_universal(
        _request(due_process_required=True, due_process_completed=False),
    )
    dp = [c for c in uni.constraint_set if c["domain"] == "due_process"]
    assert len(dp) == 1
    assert dp[0]["violation_response"] == "block"


def test_translate_due_process_emergency_does_not_relax():
    # Emergency does NOT waive due process — only public comment.
    uni = public_sector_translate_to_universal(
        _request(
            due_process_required=True,
            due_process_completed=False,
            is_emergency=True,
        ),
    )
    dp = [c for c in uni.constraint_set if c["domain"] == "due_process"]
    assert len(dp) == 1
    assert dp[0]["violation_response"] == "block"


def test_translate_public_comment_blocks_unless_emergency():
    routine = public_sector_translate_to_universal(
        _request(
            kind=CivicActionKind.RULEMAKING,
            public_comment_required=True,
            public_comment_completed=False,
        ),
    )
    pc = [c for c in routine.constraint_set if c["domain"] == "public_comment"]
    assert len(pc) == 1
    assert pc[0]["violation_response"] == "block"

    emergency = public_sector_translate_to_universal(
        _request(
            kind=CivicActionKind.RULEMAKING,
            public_comment_required=True,
            public_comment_completed=False,
            is_emergency=True,
        ),
    )
    pc_e = [c for c in emergency.constraint_set if c["domain"] == "public_comment"]
    assert pc_e[0]["violation_response"] == "escalate"


def test_translate_protected_class_per_flag_escalates():
    uni = public_sector_translate_to_universal(
        _request(protected_class_present=("disability", "minor")),
    )
    pc = [c for c in uni.constraint_set if c["domain"] == "protected_class"]
    assert len(pc) == 2
    assert all(c["violation_response"] == "escalate" for c in pc)


def test_translate_public_comment_completed_records_observer():
    uni = public_sector_translate_to_universal(
        _request(
            kind=CivicActionKind.RULEMAKING,
            public_comment_required=True,
            public_comment_completed=True,
        ),
    )
    assert "public_record" in uni.observer_required


def test_translate_rulemaking_without_statute_rejected():
    with pytest.raises(ValueError, match="statute_authority"):
        public_sector_translate_to_universal(
            _request(kind=CivicActionKind.RULEMAKING, statute_authority=()),
        )


def test_translate_blast_radius_to_permeability():
    cases = {
        "case":         "closed",
        "applicant":    "selective",
        "constituency": "selective",
        "systemic":     "open",
    }
    for blast, expected in cases.items():
        uni = public_sector_translate_to_universal(_request(blast_radius=blast))
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


def test_due_process_unsatisfied_flagged():
    out = public_sector_translate_from_universal(
        _result(),
        _request(due_process_required=True, due_process_completed=False),
    )
    assert any("due_process_required_but_not_completed" in f for f in out.risk_flags)


def test_protected_class_flagged():
    out = public_sector_translate_from_universal(
        _result(),
        _request(protected_class_present=("disability",)),
    )
    assert any("protected_class_involved" in f for f in out.risk_flags)


def test_emergency_mode_flagged():
    out = public_sector_translate_from_universal(
        _result(),
        _request(is_emergency=True),
    )
    assert any("emergency_mode" in f for f in out.risk_flags)


def test_irreversible_action_flagged():
    out = public_sector_translate_from_universal(
        _result(),
        _request(kind=CivicActionKind.PERMIT_ISSUANCE),
    )
    assert any("permit_issuance_irreversible" in f for f in out.risk_flags)


def test_systemic_blast_flagged():
    out = public_sector_translate_from_universal(
        _result(),
        _request(blast_radius="systemic"),
    )
    assert any("systemic_blast_radius" in f for f in out.risk_flags)


def test_adjudicative_without_statute_flagged():
    out = public_sector_translate_from_universal(
        _result(),
        _request(
            kind=CivicActionKind.ENFORCEMENT_ACTION,
            statute_authority=(),
        ),
    )
    assert any(
        "enforcement_action_without_statute_authority" in f
        for f in out.risk_flags
    )


def test_records_request_no_records_flagged():
    out = public_sector_translate_from_universal(
        _result(),
        _request(kind=CivicActionKind.RECORDS_REQUEST, affected_records=()),
    )
    assert any(
        "records_request_without_record_set" in f for f in out.risk_flags
    )


def test_protocol_includes_notice_and_hearing_step():
    out = public_sector_translate_from_universal(
        _result(),
        _request(due_process_required=True, due_process_completed=True),
    )
    assert any("notice-and-hearing" in s for s in out.civic_protocol)


def test_protocol_emergency_rulemaking_uses_interim_final():
    out = public_sector_translate_from_universal(
        _result(),
        _request(
            kind=CivicActionKind.RULEMAKING,
            public_comment_required=True,
            public_comment_completed=False,
            is_emergency=True,
        ),
    )
    assert any("interim final rule" in s for s in out.civic_protocol)


def test_protocol_includes_protected_class_step():
    out = public_sector_translate_from_universal(
        _result(),
        _request(protected_class_present=("disability",)),
    )
    assert any("Heightened review" in s for s in out.civic_protocol)


# ---- run_with_ucja ----


def test_run_complete_request_passes():
    out = public_sector_run_with_ucja(_request())
    assert out.governance_status == "approved"
    assert "official: alice" in out.required_signoffs


def test_run_no_acceptance_criteria_blocks_at_l9():
    out = public_sector_run_with_ucja(_request(acceptance_criteria=()))
    assert "Unknown" in out.governance_status


def test_run_emergency_rulemaking_passes_with_interim_final():
    out = public_sector_run_with_ucja(
        _request(
            kind=CivicActionKind.RULEMAKING,
            statute_authority=("APA",),
            public_comment_required=True,
            public_comment_completed=False,
            is_emergency=True,
            acceptance_criteria=("statutory_authority_present",),
        ),
    )
    assert out.governance_status == "approved"
    assert out.is_emergency is True


def test_result_carries_due_process_and_emergency_flags():
    out = public_sector_run_with_ucja(
        _request(
            due_process_required=True,
            due_process_completed=True,
            is_emergency=False,
        ),
    )
    assert out.due_process_satisfied is True
    assert out.is_emergency is False
